import hashlib
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from tools import asmr


EXAMPLES = Path(__file__).resolve().parents[1] / "examples"
APP = "sample-repository-app"


class HomepageTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name) / "catalog"
        shutil.copytree(EXAMPLES / "manual", self.root / "manual")
        self.home = self.root / "manual/homepage"
        self.home.mkdir(exist_ok=True)
        self.hero = self.home / "hero.toml"
        self.guides = self.home / "guides.toml"
        self.output = self.root / "dist/v1"

    def build(self):
        asmr.build_catalog(self.root, self.output, generated_at="2026-11-20T00:00:00Z")
        return self.read_json("homepage.json")

    def read_json(self, filename):
        return json.loads((self.output / filename).read_text())

    def write_hero(self, target, image=None):
        fields = ["schema_version = 1", f"target = {{ {target} }}"]
        if image is not None:
            fields.append(f'image = "{image}"')
        fields.extend(['[locales."zh-CN"]', 'title = "本周推荐"'])
        self.hero.write_text("\n".join(fields))

    def test_read_homepage_through_index_and_resolve_essentials(self):
        self.write_hero(f'app = "{APP}"')
        self.build()
        homepage = self.read_json(self.read_json("index.json")["homepage"])
        collection, = self.read_json("collections.json")["collections"]
        self.assertEqual(collection["id"], homepage["essentials"])
        self.assertEqual([APP, "sample-assisted-app"], collection["apps"])
        detail = self.read_json(f"apps/{APP}.json")
        self.assertEqual({"app": APP}, homepage["hero"]["target"])
        self.assertEqual(detail["media"]["hero"], homepage["hero"]["image"])
        self.assertTrue((self.output / homepage["hero"]["image"]).is_file())
        self.assertFalse((self.output / "homepage/assets").exists())

    def test_editorial_image_is_published_hashed_and_versioned(self):
        image = self.home / "assets/features/banner.svg"
        image.parent.mkdir(parents=True)
        image.write_text("<svg/>")
        self.write_hero('collection = "essentials"', "assets/features/banner.svg")
        homepage = self.build()
        published = homepage["hero"]["image"]
        self.assertEqual("homepage/assets/features/banner.svg", published)
        self.assertEqual(image.read_bytes(), (self.output / published).read_bytes())
        manifest = self.read_json("manifest.json")
        files = {item["path"]: item for item in manifest["files"]}
        for path in [published, "homepage.json"]:
            contents = (self.output / path).read_bytes()
            self.assertEqual(hashlib.sha256(contents).hexdigest(), files[path]["sha256"])
            self.assertEqual(len(contents), files[path]["bytes"])
        image.write_text('<svg width="10"/>')
        self.build()
        self.assertNotEqual(manifest["catalog_revision"], self.read_json("manifest.json")["catalog_revision"])
        self.write_hero('url = "https://aosc.io/"', "assets/features/banner.svg")
        self.assertEqual({"url": "https://aosc.io/"}, self.build()["hero"]["target"])

    def test_guides_keep_editorial_order_locales_and_date(self):
        items = ['schema_version = 1', 'more_url = "https://wiki.aosc.io/"']
        for name, day in [("second", "01"), ("first", "02")]:
            items.extend(["[[items]]", f'id = "{name}"', f'date = 2026-03-{day}',
                          f'url = "https://wiki.aosc.io/{name}/"', '[items.locales."zh-CN"]',
                          f'title = "{name}"', 'subtitle = "指南摘要"'])
        self.guides.write_text("\n".join(items))
        guides = self.build()["guides"]
        self.assertEqual("https://wiki.aosc.io/", guides["more_url"])
        self.assertEqual(["second", "first"], [item["id"] for item in guides["items"]])
        self.assertEqual("2026-03-01", guides["items"][0]["date"])
        self.assertEqual("指南摘要", guides["items"][0]["locales"]["zh-CN"]["subtitle"])

    def test_hidden_essentials_and_empty_guide_list(self):
        self.hero.unlink(missing_ok=True)
        collection = self.root / "manual/collections/essentials.toml"
        collection.write_text(collection.read_text().replace('"listed"', '"hidden"'))
        self.guides.write_text("schema_version = 1\nitems = []\n")
        homepage = self.build()
        self.assertIsNone(homepage["essentials"])
        self.assertIsNone(homepage["hero"])
        self.assertEqual([], homepage["guides"]["items"])

    def test_invalid_targets_and_images_preserve_previous_homepage(self):
        self.write_hero(f'app = "{APP}"')
        before = self.build()
        for target, image, field in [
            ('app = "missing"', None, "target.app"),
            ('collection = "missing"', None, "target.collection"),
            ('collection = "essentials"', None, "image"),
            (f'app = "{APP}", collection = "essentials"', None, "target"),
            (f'app = "{APP}"', "assets/missing.png", "image"),
            (f'app = "{APP}"', "assets/../hero.toml", "image"),
            ('url = "http://aosc.io"', None, "target.url"),
        ]:
            with self.subTest(target=target, image=image):
                self.write_hero(target, image)
                _, problems = asmr.validate_catalog(self.root)
                self.assertIn(field, [problem.field for problem in problems])
        with self.assertRaises(ValueError):
            self.build()
        self.assertEqual(before, self.read_json("homepage.json"))

    def test_guides_report_invalid_fields(self):
        item = """
[[items]]
id = "install"
url = "http://wiki.aosc.io/"
date = "2026-02-30"
[items.locales.en]
title = "Install"
"""
        self.guides.write_text('schema_version = 1\nmore_url = "file:///guides"\n' + item * 2)
        _, problems = asmr.validate_catalog(self.root)
        fields = {problem.field for problem in problems}
        self.assertTrue({"more_url", "items[0].locales", "items[0].date", "items[0].url", "items[1].id"} <= fields)
