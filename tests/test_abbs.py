from pathlib import Path
import tempfile
import unittest

from tools.abbs import snapshot


class AbbsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def recipe(self, directory, name, extra="", spec="VER=1.2\nREL=3\n"):
        source = self.root / "app-test" / directory
        source.mkdir(parents=True, exist_ok=True)
        (source / "spec").write_text(spec)
        output = source / "autobuild"
        output.mkdir(exist_ok=True)
        (output / "defines").write_text(f'PKGNAME={name}\nPKGSEC=utils\nPKGDES="Example application"\n{extra}')
        return source

    def test_wrong_input_tree_is_not_an_empty_inventory(self):
        with self.assertRaisesRegex(ValueError, "no package recipes"):
            snapshot(self.root, "revision")

    def test_standard_recipe_and_deterministic_order(self):
        self.recipe("z-source", "a-package")
        self.recipe("a-source", "z-package")
        result = snapshot(self.root, "abc123")
        self.assertEqual(list(result["packages"]), ["a-package", "z-package"])
        self.assertEqual(result["source_commit"], "abc123")
        package = result["packages"]["a-package"]
        self.assertEqual(package["description"], "Example application")
        self.assertEqual(package["source_version"], "1.2")
        self.assertEqual(package["source_release"], "3")
        self.assertNotIn("architectures", package)
        self.assertEqual(snapshot(self.root, "abc123"), result)

    def test_numbered_subpackages_use_package_names(self):
        source = self.root / "app-editors" / "vim"
        source.mkdir(parents=True)
        (source / "spec").write_text("VER=9.1\n")
        # Layout matches AOSC-Dev/aosc-os-abbs/app-editors/vim.
        for directory, name in [("01-vim", "vim"), ("02-gvim", "gvim")]:
            output = source / directory
            output.mkdir()
            (output / "defines").write_text(f'PKGNAME={name}\nPKGSEC=editors\nPKGDES="Editor"\n')
        result = snapshot(self.root, "revision")
        self.assertEqual(set(result["packages"]), {"vim", "gvim"})
        self.assertIn("02-gvim/defines", result["packages"]["gvim"]["recipe"])

    def test_dynamic_values_are_never_executed(self):
        marker = self.root / "executed"
        self.recipe("dynamic", "dynamic", f'PKGDES="$(touch {marker})"\n')
        self.recipe("version", "version", spec='VER="${OTHER}"\n')
        result = snapshot(self.root, "revision")
        self.assertNotIn("dynamic", result["packages"])
        self.assertNotIn("source_version", result["packages"]["version"])
        self.assertTrue(result["skipped"])
        self.assertFalse(marker.exists())

    def test_wrapped_dependencies_and_build_option_arrays(self):
        source = self.recipe("player", "player")
        defines = source / "autobuild/defines"
        defines.write_text(
            "PKGNAME=player\nPKGSEC=video\n"
            + 'PKGDEP="first ' + chr(92) + '\n second"\n'
            + "CONFIGURE_OPTIONS=(\n  '--enable-player'\n  'PKGDES=not-an-assignment'\n)\n"
            + 'PKGDES="Media player"\nPKGDES__ARM64="Alternative description"\n'
        )
        result = snapshot(self.root, "rev")
        self.assertEqual("Media player", result["packages"]["player"]["description"])
        self.assertTrue(any("ARM64" in issue["reason"] for issue in result["skipped"]))

    def test_control_flow_and_command_suffix_are_not_partial_facts(self):
        self.recipe("conditional", "conditional", 'if true; then\nPKGNAME=other\nfi\n')
        self.recipe("suffix", "suffix; echo wrong")
        self.assertEqual(snapshot(self.root, "revision")["packages"], {})

    def test_duplicate_names_exclude_both_outputs(self):
        self.recipe("one", "duplicate")
        self.recipe("two", "duplicate")
        result = snapshot(self.root, "revision")
        self.assertEqual(result["packages"], {})
        self.assertEqual(len(result["skipped"]), 2)

    def test_symlink_and_repeated_assignment_are_explicit(self):
        source = self.recipe("one", "one", 'PKGDES="changed"\n')
        source2 = self.recipe("two", "two")
        (source2 / "autobuild" / "defines").unlink()
        (source2 / "autobuild" / "defines").symlink_to(source / "autobuild" / "defines")
        result = snapshot(self.root, "revision")
        self.assertEqual(result["packages"], {})
        self.assertTrue(any("symbolic" in item["reason"] for item in result["skipped"]))


if __name__ == "__main__":
    unittest.main()
