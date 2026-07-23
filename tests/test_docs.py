from __future__ import annotations

import re
import unittest
from pathlib import Path
from urllib.parse import unquote


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
MARKDOWN_LINK_RE = re.compile(r"\[[^\]]+\]\(([^)]+)\)")


class DocumentationTests(unittest.TestCase):
    def test_required_english_and_chinese_documents_exist(self) -> None:
        required = (
            "README.md",
            "README.zh-CN.md",
            "CONTRIBUTING.md",
            "CONTRIBUTING.zh-CN.md",
            "docs/maintainer-guide.md",
            "docs/maintainer-guide.zh-CN.md",
            "docs/schema-v1.md",
            "docs/schema-v1.zh-CN.md",
        )

        missing = [path for path in required if not (REPOSITORY_ROOT / path).is_file()]

        self.assertEqual([], missing)

    def test_relative_markdown_links_resolve(self) -> None:
        failures: list[str] = []
        for document in sorted(REPOSITORY_ROOT.rglob("*.md")):
            if ".git" in document.parts:
                continue
            text = document.read_text(encoding="utf-8")
            for target in MARKDOWN_LINK_RE.findall(text):
                target = target.strip().split(maxsplit=1)[0].strip("<>")
                if (
                    not target
                    or target.startswith(("#", "http://", "https://", "mailto:"))
                ):
                    continue
                path_text = unquote(target.split("#", 1)[0])
                resolved = (document.parent / path_text).resolve()
                if not resolved.exists():
                    failures.append(
                        f"{document.relative_to(REPOSITORY_ROOT)} -> {target}"
                    )

        self.assertEqual([], failures)


if __name__ == "__main__":
    unittest.main()
