"""Extract literal package facts from ABBS without executing build recipes.

ABBS spec/defines use APML. This reader supports literal defaults only;
its diagnostics identify expressions requiring ACBS/Autobuild interpretation.
Source versions describe recipes, not published binary package availability.
"""
from __future__ import annotations

import re
import shlex
from pathlib import Path
from typing import Any

ASSIGNMENT = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)=(.*)$", re.S)
PACKAGE_NAME = re.compile(r"^[a-z0-9][a-z0-9+.-]*$")
FIELDS = {"PKGNAME": "name", "PKGSEC": "section", "PKGDES": "description"}
VERSION_FIELDS = {"VER": "source_version", "REL": "source_release", "EPOCH": "source_epoch"}


def _literal(raw: str) -> str | None:
    # Reject expansion even in single quotes: ambiguous shell facts stay explicit.
    if any(char in raw for char in "$`\\"):
        return None
    lexer = shlex.shlex(raw, posix=True, punctuation_chars=";&|<>()")
    lexer.whitespace_split = True
    lexer.commenters = "#"
    try:
        words = list(lexer)
    except ValueError:
        return None
    if len(words) != 1 or any(char in words[0] for char in "\x00\r\n"):
        return None
    if raw.lstrip().startswith(("'", '"')):
        return words[0]
    if any(char in words[0] for char in ";&|<>()*?[]~"):
        return None
    return words[0]


def _read(path: Path, tree: Path, fields: dict[str, str], skipped: list[dict[str, str]]) -> dict[str, str]:
    relative = path.relative_to(tree).as_posix()
    if path.is_symlink() or not path.resolve().is_relative_to(tree.resolve()):
        skipped.append({"path": relative, "reason": "symbolic-link recipe is unsupported"})
        return {}
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError) as error:
        skipped.append({"path": relative, "reason": str(error)})
        return {}
    values: dict[str, str] = {}
    seen: set[str] = set()
    known_name = None
    def report(reason: str) -> None:
        item = {"path": relative, "reason": reason}
        if known_name:
            item["package_name"] = known_name
        skipped.append(item)

    physical = iter(enumerate(lines, 1))
    for number, line in physical:
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        # ACBS recipes commonly wrap quoted dependency lists across lines.
        while line.endswith("\\"):
            following = next(physical, None)
            if following is None:
                report(f"line {number}: unfinished continuation")
                return {}
            line = line[:-1] + following[1]
        match = ASSIGNMENT.fullmatch(line)
        if not match:
            report(f"line {number}: shell statement or multiline expression is unsupported")
            return {}
        variable, raw = match.groups()
        if variable not in fields:
            base_key, separator, arch = variable.partition("__")
            if separator and base_key in fields:
                skipped.append({"path": relative, "field": fields[base_key],
                                "reason": f"line {number}: architecture override {arch} not evaluated"})
            # Consume option arrays as data, without interpreting their contents.
            if raw.strip() == "(":
                for _, element in physical:
                    if element.strip() == ")":
                        break
                else:
                    report(f"line {number}: unterminated array")
                    return {}
            continue
        field = fields[variable]
        literal = _literal(raw)
        if variable in seen or literal is None or not literal.strip():
            values.pop(field, None)
            skipped.append({"path": relative, "field": field, "reason": f"line {number}: repeated, empty, or nonliteral assignment"})
        else:
            values[field] = literal
            if field == "name":
                known_name = literal
        seen.add(variable)
    return values


def snapshot(tree: Path, revision: str) -> dict[str, Any]:
    """Return deterministic, conservative inventory from an ABBS checkout."""
    tree = Path(tree)
    if not tree.is_dir():
        raise ValueError(f"ABBS tree does not exist: {tree}")
    if not revision.strip():
        raise ValueError("ABBS source revision is required")
    packages: dict[str, dict[str, str]] = {}
    skipped: list[dict[str, str]] = []
    duplicates: set[str] = set()
    specs = sorted(tree.glob("*/*/spec"))
    if not specs:
        raise ValueError(f"no package recipes (*/*/spec) in ABBS tree: {tree}")
    for spec in specs:
        source = spec.parent
        version = _read(spec, tree, VERSION_FIELDS, skipped)
        recipes = sorted(source.glob("[0-9][0-9]*/defines"))
        ordinary = source / "autobuild" / "defines"
        if ordinary.is_file():
            recipes.append(ordinary)
        if not recipes:
            skipped.append({"path": spec.relative_to(tree).as_posix(), "reason": "no supported defines layout"})
        for defines in sorted(recipes):
            relative = defines.relative_to(tree).as_posix()
            facts = _read(defines, tree, {**FIELDS, "PKGEPOCH": "source_epoch", "EPOCH": "source_epoch"}, skipped)
            missing = sorted(set(FIELDS.values()) - facts.keys())
            if missing:
                skipped.append({"path": relative, **({"package_name": facts["name"]} if "name" in facts else {}), "reason": "missing literal fields: " + ", ".join(missing)})
                continue
            name = facts["name"]
            if not PACKAGE_NAME.fullmatch(name):
                skipped.append({"path": relative, "reason": "invalid package name"})
                continue
            if name in packages or name in duplicates:
                if name in packages:
                    skipped.append({"path": packages.pop(name)["recipe"], "package_name": name, "reason": f"duplicate package name: {name}"})
                skipped.append({"path": relative, "package_name": name, "reason": f"duplicate package name: {name}"})
                duplicates.add(name)
                continue
            packages[name] = {**version, **facts, "recipe": relative}
    return {
        "source_commit": revision,
        "packages": dict(sorted(packages.items())),
        "skipped": sorted(skipped, key=lambda item: (item["path"], item.get("field", ""), item["reason"])),
    }
