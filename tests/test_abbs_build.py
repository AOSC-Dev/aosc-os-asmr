import hashlib
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from tools import asmr

ROOT = Path(__file__).resolve().parents[1]


class AbbsBuildTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.tree = self.base / "abbs"
        recipe = self.tree / "app-test" / "different-recipe" / "autobuild"
        recipe.mkdir(parents=True)
        (recipe.parent / "spec").write_text("VER=1.0\nREL=2\n")
        (recipe / "defines").write_text('PKGNAME=sample-app\nPKGSEC=utils\nPKGDES="Generated description"\n')
        for args in [["init", "-q"], ["add", "."], ["-c", "user.name=Test", "-c", "user.email=test@example.invalid", "commit", "-qm", "fixture"]]:
            subprocess.run(["git", "-C", str(self.tree), *args], check=True)
        self.commit = subprocess.check_output(["git", "-C", str(self.tree), "rev-parse", "HEAD"], text=True).strip()

    def build(self, output, **kwargs):
        return asmr.build_catalog(ROOT / "examples", output, generated_at="2026-11-19T00:00:00Z", abbs_tree=self.tree, **kwargs)

    def test_inventory_joins_package_reference_and_preserves_manual_content(self):
        output = self.base / "out"
        self.build(output, abbs_commit=self.commit)
        detail = json.loads((output / "apps/sample-repository-app.json").read_text())
        self.assertEqual(["sample-app"], list(detail["abbs"]["packages"]))
        self.assertEqual("Repository App Example", detail["locales"]["en"]["name"])
        external = json.loads((output / "apps/sample-assisted-app.json").read_text())
        self.assertNotIn("abbs", external)
        manifest = json.loads((output / "manifest.json").read_text())
        self.assertEqual(self.commit, manifest["abbs_source_commit"])
        entry = next(item for item in manifest["files"] if item["path"] == "abbs-packages.json")
        self.assertEqual(hashlib.sha256((output / entry["path"]).read_bytes()).hexdigest(), entry["sha256"])
        self.build(self.base / "again")
        self.assertEqual(manifest, json.loads((self.base / "again/manifest.json").read_text()))

    def test_invalid_provenance_preserves_existing_output(self):
        output = self.base / "out"
        output.mkdir()
        sentinel = output / "keep"
        sentinel.write_text("original")
        with self.assertRaisesRegex(ValueError, "HEAD"):
            self.build(output, abbs_commit="0" * 40)
        self.assertEqual("original", sentinel.read_text())
        (self.tree / "untracked").write_text("dirty")
        with self.assertRaisesRegex(ValueError, "clean"):
            self.build(output)
        self.assertEqual("original", sentinel.read_text())

    def test_output_cannot_replace_or_enter_abbs_tree(self):
        for output in [self.tree, self.tree / "dist", self.base]:
            with self.assertRaisesRegex(ValueError, "outside"):
                self.build(output)
        self.assertTrue((self.tree / ".git").is_dir())

    def test_missing_reference_is_reported_before_output_replacement(self):
        recipe = self.tree / "app-test/different-recipe/autobuild/defines"
        recipe.write_text('PKGNAME=other\nPKGSEC=utils\nPKGDES="Other package"\n')
        subprocess.run(["git", "-C", str(self.tree), "add", "."], check=True)
        subprocess.run(["git", "-C", str(self.tree), "-c", "user.name=Test", "-c", "user.email=test@example.invalid", "commit", "-qm", "rename"], check=True)
        with self.assertRaises(ValueError):
            self.build(self.base / "out")

    def test_empty_manual_catalog_still_has_generated_inventory(self):
        output = self.base / "out"
        asmr.build_catalog(ROOT, output, abbs_tree=self.tree)
        inventory = json.loads((output / "abbs-packages.json").read_text())
        self.assertIn("sample-app", inventory["packages"])
        self.assertEqual(["sample-app"], [app["id"] for app in json.loads((output / "index.json").read_text())["apps"]])


if __name__ == "__main__":
    unittest.main()
