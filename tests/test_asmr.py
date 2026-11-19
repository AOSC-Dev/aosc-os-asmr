from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from tools import asmr


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
EXAMPLES_ROOT = REPOSITORY_ROOT / "examples"


class AsmrToolTests(unittest.TestCase):
    def copy_examples(self) -> tuple[tempfile.TemporaryDirectory[str], Path]:
        temporary = tempfile.TemporaryDirectory()
        root = Path(temporary.name) / "catalog"
        shutil.copytree(EXAMPLES_ROOT, root)
        return temporary, root

    def test_example_catalog_is_valid(self) -> None:
        catalog, problems = asmr.validate_catalog(EXAMPLES_ROOT)

        self.assertEqual([], problems)
        self.assertIsNotNone(catalog)
        assert catalog is not None
        self.assertEqual(
            {"sample-assisted-app", "sample-repository-app"},
            set(catalog.apps),
        )
        self.assertEqual({"essentials"}, set(catalog.collections))

    def test_build_emits_index_details_assets_and_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "dist"
            asmr.build_catalog(
                EXAMPLES_ROOT,
                output,
                generated_at="2026-07-23T00:00:00Z",
                source_commit="test-commit",
            )

            index = json.loads((output / "index.json").read_text(encoding="utf-8"))
            assisted = json.loads(
                (output / "apps" / "sample-assisted-app.json").read_text(
                    encoding="utf-8"
                )
            )
            manifest = json.loads(
                (output / "manifest.json").read_text(encoding="utf-8")
            )

            self.assertEqual(
                ["sample-assisted-app", "sample-repository-app"],
                [entry["id"] for entry in index["apps"]],
            )
            self.assertEqual(
                "browser-assisted-deb", assisted["installers"][0]["kind"]
            )
            self.assertIn(
                "user to trigger the download",
                assisted["locales"]["en"]["description_markdown"],
            )
            self.assertTrue(
                (output / "apps" / "sample-assisted-app" / "assets" / "icon.svg").is_file()
            )
            self.assertEqual("test-commit", manifest["source_commit"])
            self.assertRegex(manifest["catalog_revision"], r"^sha256:[0-9a-f]{64}$")
            self.assertNotIn("manifest.json", {item["path"] for item in manifest["files"]})
            self.assertTrue(all(len(item["sha256"]) == 64 for item in manifest["files"]))

    def test_browser_assisted_installer_requires_download_origin(self) -> None:
        temporary, root = self.copy_examples()
        self.addCleanup(temporary.cleanup)
        path = root / "apps" / "sample-assisted-app" / "app.toml"
        text = path.read_text(encoding="utf-8").replace(
            'allowed_download_origins = ["https://example.invalid"]',
            "allowed_download_origins = []",
        )
        path.write_text(text, encoding="utf-8")

        _catalog, problems = asmr.validate_catalog(root)

        self.assertTrue(
            any(
                problem.field.endswith("allowed_download_origins")
                and "must not be empty" in problem.message
                for problem in problems
            )
        )

    def test_metadata_rejects_executable_script_fields(self) -> None:
        temporary, root = self.copy_examples()
        self.addCleanup(temporary.cleanup)
        path = root / "apps" / "sample-assisted-app" / "app.toml"
        with path.open("a", encoding="utf-8") as handle:
            handle.write('\nscript = "curl https://example.invalid | sh"\n')

        _catalog, problems = asmr.validate_catalog(root)

        self.assertTrue(
            any(
                "commands and scripts are forbidden" in problem.message
                for problem in problems
            )
        )

    def test_collection_rejects_unknown_app(self) -> None:
        temporary, root = self.copy_examples()
        self.addCleanup(temporary.cleanup)
        path = root / "collections" / "essentials.toml"
        text = path.read_text(encoding="utf-8").replace(
            '"sample-assisted-app"', '"missing-app"'
        )
        path.write_text(text, encoding="utf-8")

        _catalog, problems = asmr.validate_catalog(root)

        self.assertTrue(
            any(
                problem.field == "apps"
                and "references unknown app: missing-app" in problem.message
                for problem in problems
            )
        )

    def test_scaffold_creates_expected_files_and_requires_todo_cleanup(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            shutil.copy(REPOSITORY_ROOT / "repository.toml", root / "repository.toml")
            shutil.copytree(REPOSITORY_ROOT / "taxonomy", root / "taxonomy")
            (root / "apps").mkdir()
            (root / "collections").mkdir()

            app_dir = asmr.scaffold_app(
                root,
                "new-app",
                "browser-assisted-deb",
                "communication",
            )
            _catalog, problems = asmr.validate_catalog(root)

            self.assertTrue((app_dir / "app.toml").is_file())
            self.assertTrue((app_dir / "assets" / "icon.svg").is_file())
            self.assertTrue((app_dir / "description.zh-CN.md").is_file())
            self.assertTrue(
                any("replace the scaffold placeholder" in problem.message for problem in problems)
            )

    def test_every_installer_scaffold_can_be_completed_and_validated(self) -> None:
        for kind in sorted(asmr.INSTALLER_KINDS):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                shutil.copy(REPOSITORY_ROOT / "repository.toml", root / "repository.toml")
                shutil.copytree(REPOSITORY_ROOT / "taxonomy", root / "taxonomy")
                (root / "apps").mkdir()
                (root / "collections").mkdir()

                app_dir = asmr.scaffold_app(
                    root,
                    f"sample-{kind}",
                    kind,
                    "utilities",
                )
                path = app_dir / "app.toml"
                text = (
                    path.read_text(encoding="utf-8")
                    .replace("TODO: GitHub handle", "example-maintainer")
                    .replace("TODO: application name", "Example App")
                    .replace("TODO: short summary", "Example application metadata")
                    .replace("TODO: publisher", "Example Publisher")
                )
                path.write_text(text, encoding="utf-8")

                if kind == "aosc-repository":
                    tree = root / "abbs"
                    recipe = tree / "app-test" / "source" / "autobuild"
                    recipe.mkdir(parents=True)
                    (recipe.parent / "spec").write_text("VER=1\n")
                    (recipe / "defines").write_text(
                        f'PKGNAME=sample-{kind}\nPKGSEC=utils\nPKGDES="Example package"\n'
                    )
                    for args in (["init", "-q"], ["add", "."], ["-c", "user.name=Test", "-c", "user.email=test@example.invalid", "commit", "-qm", "fixture"]):
                        subprocess.run(["git", "-C", str(tree), *args], check=True)
                    self.assertIn("external = false", text)
                    _catalog, problems = asmr.validate_catalog(root, abbs_tree=tree)
                else:
                    self.assertIn("external = true", text)
                    _catalog, problems = asmr.validate_catalog(root)

                self.assertEqual([], problems)


if __name__ == "__main__":
    unittest.main()
