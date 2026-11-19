import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

from tools import asmr

ROOT = Path(__file__).resolve().parents[1]


class OverlayTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name)
        self.root = self.base / "catalog"
        self.root.mkdir()
        self.manual = self.root / "manual"
        self.manual.mkdir()
        for name in ("repository.toml",):
            shutil.copy(ROOT / "manual" / name, self.manual / name)
        shutil.copytree(ROOT / "manual/taxonomy", self.manual / "taxonomy")
        (self.manual / "apps").mkdir()
        (self.manual / "collections").mkdir()
        self.tree = self.base / "abbs"
        recipe = self.tree / "app-test" / "source-name" / "autobuild"
        recipe.mkdir(parents=True)
        (recipe.parent / "spec").write_text("VER=1.0\nREL=2\n")
        (recipe / "defines").write_text('PKGNAME=sample-app\nPKGSEC=utils\nPKGDES="Original English description"\n')
        for args in (["init", "-q"], ["add", "."], ["-c", "user.name=Test", "-c", "user.email=test@example.invalid", "commit", "-qm", "fixture"]):
            subprocess.run(["git", "-C", str(self.tree), *args], check=True)
        self.output = self.base / "out"

    def overlay(self, app_id, text):
        directory = self.manual / "apps" / app_id
        directory.mkdir(exist_ok=True)
        (directory / "app.toml").write_text(text)

    def build(self):
        asmr.build_catalog(self.root, self.output, abbs_tree=self.tree, generated_at="2026-11-19T00:00:00Z")
        return json.loads((self.output / "index.json").read_text())

    def detail(self, app_id="sample-app"):
        return json.loads((self.output / "apps" / (app_id + ".json")).read_text())

    def test_output_cannot_overwrite_handwritten_app(self):
        self.overlay("sample-app", '[locales.en]\nsummary="Edited"\n')
        directory = self.manual / "apps" / "sample-app"
        with self.assertRaisesRegex(ValueError, "unsafe output"):
            asmr.build_catalog(self.root, directory, abbs_tree=self.tree)
        self.assertIn("Edited", (directory / "app.toml").read_text())

    def test_rebuild_preserves_manual_bytes_and_ignores_stale_generated_data(self):
        self.overlay("sample-app", '[locales.en]\nsummary="Handwritten summary"\n')
        self.output = self.root / "dist/v1"
        source_before = {path.relative_to(self.manual): path.read_bytes()
                         for path in self.manual.rglob("*") if path.is_file()}
        self.build()
        first_manifest = (self.output / "manifest.json").read_bytes()
        (self.output / "apps/sample-app.json").write_text('{"external":true,"summary":"stale"}')
        (self.output / "apps/stale.json").write_text("{}")
        self.build()
        source_after = {path.relative_to(self.manual): path.read_bytes()
                        for path in self.manual.rglob("*") if path.is_file()}
        self.assertEqual(source_before, source_after)
        self.assertEqual(first_manifest, (self.output / "manifest.json").read_bytes())
        self.assertEqual("Handwritten summary", self.detail()["locales"]["en"]["summary"])
        self.assertFalse((self.output / "apps/stale.json").exists())

    def test_output_rejects_manual_tree_and_other_source_directories(self):
        self.overlay("sample-app", '[locales.en]\nsummary="Edited"\n')
        for directory in (self.manual, self.manual / "generated", self.root / "tools", self.root / "schemas"):
            with self.subTest(directory=directory):
                directory.mkdir(parents=True, exist_ok=True)
                sentinel = directory / "preserve.txt"
                sentinel.write_text("source data")
                with self.assertRaisesRegex(ValueError, "output"):
                    asmr.build_catalog(self.root, directory, abbs_tree=self.tree)
                self.assertEqual("source data", sentinel.read_text())

    def test_examples_root_cannot_overwrite_checkout_manual_metadata(self):
        examples = self.root / "examples"
        shutil.copytree(ROOT / "examples", examples)
        sentinel = self.manual / "keep.txt"
        sentinel.write_text("handwritten data")
        # Model this temporary fixture as the checkout containing the tool.
        with patch.object(asmr, "__file__", str(self.root / "tools/asmr.py")):
            with self.assertRaisesRegex(ValueError, "unsafe output"):
                asmr.build_catalog(examples, self.manual)
        self.assertEqual("handwritten data", sentinel.read_text())
        self.assertTrue((self.manual / "repository.toml").is_file())

    def test_old_root_layout_reports_the_missing_manual_path(self):
        legacy = self.base / "legacy"
        shutil.copytree(self.manual, legacy)
        _, problems = asmr.validate_catalog(legacy)
        self.assertTrue(any("manual" in problem.path.as_posix() for problem in problems))

    def test_generated_package_is_usable_without_manual_metadata_or_media(self):
        index = self.build()
        self.assertEqual(["sample-app"], [app["id"] for app in index["apps"]])
        detail = self.detail()
        self.assertFalse(detail["external"])
        self.assertEqual("Original English description", detail["locales"]["en"]["summary"])
        self.assertEqual(["sample-app"], detail["installers"][0]["package"]["names"])
        self.assertEqual("1.0", detail["abbs"]["packages"]["sample-app"]["source_version"])

    def test_partial_locale_override_retains_sibling_fields_and_raw_facts(self):
        self.overlay("sample-app", '[locales."zh-CN"]\nsummary="人工中文简介"\n')
        self.build()
        detail = self.detail()
        self.assertEqual("人工中文简介", detail["locales"]["zh-CN"]["summary"])
        self.assertEqual("sample-app", detail["locales"]["zh-CN"]["name"])
        self.assertEqual("Original English description", detail["locales"]["en"]["summary"])
        self.assertEqual("Original English description", detail["abbs"]["packages"]["sample-app"]["description"])

    def test_name_only_translation_and_partial_publisher(self):
        self.overlay("sample-app", '[locales."zh-CN"]\nname="示例"\n[publisher]\nname="Example"\n')
        entry, = self.build()["apps"]
        self.assertEqual({"name": "示例"}, entry["locales"]["zh-CN"])
        self.assertEqual("Original English description", entry["locales"]["en"]["summary"])
        self.assertEqual({"name": "Example"}, self.detail()["publisher"])
        self.assertEqual(["uncategorized"], entry["categories"])

    def test_lists_replace_and_empty_lists_are_preserved(self):
        self.overlay("sample-app", 'categories=["games"]\nkeywords=["custom"]\naliases=[]\n[media]\nscreenshots=[]\n')
        self.build()
        detail = self.detail()
        self.assertEqual(["games"], detail["categories"])
        self.assertEqual(["custom"], detail["keywords"])
        self.assertEqual([], detail["aliases"])
        self.assertEqual([], detail["media"]["screenshots"])
        self.overlay("sample-app", 'categories=[]\n')
        with self.assertRaises(ValueError):
            self.build()

    def test_missing_package_requires_explicit_external_and_preserves_output(self):
        self.build()
        before = (self.output / "manifest.json").read_bytes()
        self.overlay("typo-app", '[locales.en]\nsummary="Missing package"\n')
        with self.assertRaises(ValueError):
            self.build()
        self.assertEqual(before, (self.output / "manifest.json").read_bytes())

    def test_external_entry_accepts_manual_acquisition(self):
        target = self.manual / "apps" / "sample-assisted-app"
        shutil.copytree(ROOT / "examples/manual/apps/sample-assisted-app", target)
        self.build()
        detail = self.detail("sample-assisted-app")
        self.assertTrue(detail["external"])
        self.assertEqual("browser-assisted-deb", detail["installers"][0]["kind"])
        self.assertNotIn("abbs", detail)

    def test_external_flag_must_be_boolean_and_cannot_conflict_with_source(self):
        for flag in ('true', '"true"', '1'):
            with self.subTest(flag=flag):
                self.overlay("sample-app", 'external=' + flag + '\n')
                with self.assertRaises(ValueError):
                    self.build()

    def test_explicit_app_id_joins_package_without_duplicate_auto_entry(self):
        shutil.copytree(ROOT / "examples/manual/apps/sample-repository-app", self.manual / "apps/sample-repository-app")
        index = self.build()
        self.assertEqual(["sample-repository-app"], [app["id"] for app in index["apps"]])
        self.assertEqual(["sample-app"], list(self.detail("sample-repository-app")["abbs"]["packages"]))

    def test_external_entry_cannot_declare_repository_installer(self):
        target = self.manual / "apps/sample-repository-app"
        shutil.copytree(ROOT / "examples/manual/apps/sample-repository-app", target)
        metadata = target / "app.toml"
        metadata.write_text("external=true\n" + metadata.read_text())
        with self.assertRaises(ValueError):
            self.build()

    def test_overlay_asset_and_unknown_field_validation_still_applies(self):
        for metadata in ('[media]\nicon="../outside.svg"\n', 'visiblity="hidden"\n'):
            with self.subTest(metadata=metadata):
                self.overlay("sample-app", metadata)
                with self.assertRaises(ValueError):
                    self.build()

    def test_generated_ids_can_be_used_in_collections(self):
        (self.manual / "collections/essentials.toml").write_text('schema_version=1\nid="essentials"\nvisibility="listed"\napps=["sample-app"]\n[locales.en]\ntitle="Essentials"\n')
        self.build()
        collections = json.loads((self.output / "collections.json").read_text())
        self.assertEqual(["sample-app"], collections["collections"][0]["apps"])

    def test_check_and_build_agree_on_merged_validation(self):
        self.overlay("sample-app", '[locales."zh-CN"]\nsummary="中文说明"\n')
        catalog, problems = asmr.validate_catalog(self.root, abbs_tree=self.tree)
        self.assertEqual([], problems)
        self.assertIn("sample-app", catalog.apps)
        self.build()
        self.overlay("sample-app", '[locales.en]\nsummary=42\n')
        _, problems = asmr.validate_catalog(self.root, abbs_tree=self.tree)
        self.assertTrue(problems)
        with self.assertRaises(ValueError):
            self.build()

    def test_external_artifact_cannot_claim_an_existing_package(self):
        target = self.manual / "apps/sample-assisted-app"
        shutil.copytree(ROOT / "examples/manual/apps/sample-assisted-app", target)
        metadata = target / "app.toml"
        metadata.write_text(metadata.read_text().replace(
            'expected_package_names = ["sample-assisted-app"]',
            'expected_package_names = ["sample-app"]',
        ))
        with self.assertRaises(ValueError):
            self.build()

    def test_skipped_known_package_cannot_be_marked_external(self):
        recipe = self.tree / "app-test/source-name/autobuild/defines"
        recipe.write_text('PKGNAME=sample-app\nPKGSEC=utils\nPKGDES="$UNRESOLVED"\n')
        subprocess.run(["git", "-C", str(self.tree), "add", "."], check=True)
        subprocess.run(["git", "-C", str(self.tree), "-c", "user.name=Test", "-c", "user.email=test@example.invalid", "commit", "-qm", "dynamic description"], check=True)
        self.overlay("sample-app", 'external=true\n')
        _, problems = asmr.validate_catalog(self.root, abbs_tree=self.tree)
        self.assertTrue(any(problem.field == "external" and "ABBS package" in problem.message for problem in problems))
        with self.assertRaises(ValueError):
            self.build()

    def test_external_link_override_keeps_source_facts(self):
        self.overlay("sample-app", '''[[installers]]
id="web"
kind="external-link"
priority=100
architectures=[]
update_policy="external"
[installers.acquisition]
landing_url="https://example.org/download"
''')
        self.build()
        detail = self.detail()
        self.assertEqual(["external-link"], [item["kind"] for item in detail["installers"]])
        self.assertFalse(detail["external"])
        self.assertEqual("Original English description", detail["abbs"]["packages"]["sample-app"]["description"])

    def test_cli_check_and_build_accept_the_same_sparse_metadata(self):
        self.overlay("sample-app", '[locales.en]\nsummary="Custom summary"\n')
        for command in ("check", "build"):
            arguments = [sys.executable, str(ROOT / "tools/asmr.py"), command,
                         "--root", str(self.root), "--abbs-tree", str(self.tree)]
            if command == "build":
                arguments += ["--output", str(self.output)]
            result = subprocess.run(arguments, text=True, capture_output=True)
            self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual("Custom summary", self.detail()["locales"]["en"]["summary"])

    def test_manual_metadata_cannot_overwrite_generated_provenance(self):
        self.overlay("sample-app", '[abbs]\nsource_commit="fake"\n')
        with self.assertRaises(ValueError):
            self.build()


if __name__ == "__main__":
    unittest.main()
