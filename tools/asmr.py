#!/usr/bin/env python3
"""Validate and build the AOSC Software Manager Metadata Repository."""

from __future__ import annotations

import argparse
import copy
import datetime as dt
import hashlib
import json
import os
import re
import shutil
import sys
import subprocess
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


APP_ID_RE = re.compile(r"^[a-z0-9][a-z0-9+._-]*$")
PACKAGE_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9+.-]*$")
ARCH_RE = re.compile(r"^[a-z0-9][a-z0-9_-]*$")
MEDIA_SUFFIXES = {".avif", ".jpeg", ".jpg", ".png", ".svg", ".webp"}
VISIBILITIES = {"listed", "unlisted", "hidden"}
LIFECYCLES = {"active", "deprecated", "blocked"}
INSTALLER_KINDS = {
    "aosc-repository",
    "direct-deb",
    "browser-assisted-deb",
    "external-link",
}
DISCLOSURE_VALUES = {
    "availability": {"verified", "unverified", "broken", "unknown"},
    "runtime": {"native", "compatibility-layer", "windows", "unknown"},
    "telemetry": {"present", "absent", "unknown"},
    "service": {"full", "limited", "unavailable", "unknown"},
    "support": {"aosc", "upstream", "community", "none", "unknown"},
}
FORBIDDEN_METADATA_KEYS = {
    "command",
    "commands",
    "exec",
    "post_install",
    "pre_install",
    "script",
    "scripts",
    "shell",
}
APP_KEYS = {
    "external",
    "schema_version",
    "id",
    "visibility",
    "lifecycle",
    "default_locale",
    "categories",
    "aliases",
    "keywords",
    "maintainers",
    "reviewed_at",
    "locales",
    "media",
    "publisher",
    "links",
    "disclosures",
    "installers",
}


@dataclass(frozen=True)
class Problem:
    path: Path
    field: str
    message: str

    def display(self, root: Path) -> str:
        try:
            path = self.path.relative_to(root)
        except ValueError:
            path = self.path
        location = f"{path}:{self.field}" if self.field else str(path)
        return f"{location}: {self.message}"


@dataclass
class Catalog:
    root: Path
    config: dict[str, Any]
    categories: dict[str, Any]
    apps: dict[str, dict[str, Any]]
    app_dirs: dict[str, Path]
    collections: dict[str, dict[str, Any]]
    homepage: dict[str, Any]
    abbs_inventory: dict[str, Any] | None = None


def _load_toml(path: Path, problems: list[Problem]) -> dict[str, Any] | None:
    try:
        with path.open("rb") as handle:
            value = tomllib.load(handle)
    except FileNotFoundError:
        problems.append(Problem(path, "", "required file does not exist"))
        return None
    except tomllib.TOMLDecodeError as error:
        problems.append(Problem(path, "", f"invalid TOML: {error}"))
        return None
    except OSError as error:
        problems.append(Problem(path, "", f"cannot read file: {error}"))
        return None
    if not isinstance(value, dict):
        problems.append(Problem(path, "", "TOML root must be a table"))
        return None
    return value


def _is_nonempty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _string(
    data: dict[str, Any],
    key: str,
    path: Path,
    field: str,
    problems: list[Problem],
) -> str | None:
    value = data.get(key)
    if not _is_nonempty_string(value):
        problems.append(Problem(path, field, "must be a non-empty string"))
        return None
    return value.strip()


def _string_list(
    data: dict[str, Any],
    key: str,
    path: Path,
    field: str,
    problems: list[Problem],
    *,
    required: bool = True,
) -> list[str]:
    value = data.get(key)
    if value is None and not required:
        return []
    if not isinstance(value, list) or any(not _is_nonempty_string(item) for item in value):
        problems.append(Problem(path, field, "must be a list of non-empty strings"))
        return []
    if required and not value:
        problems.append(Problem(path, field, "must not be empty"))
    return [item.strip() for item in value]


def _table(
    data: dict[str, Any],
    key: str,
    path: Path,
    field: str,
    problems: list[Problem],
    *,
    required: bool = True,
) -> dict[str, Any]:
    value = data.get(key)
    if value is None and not required:
        return {}
    if not isinstance(value, dict):
        problems.append(Problem(path, field, "must be a table"))
        return {}
    return value


def _list_of_tables(
    data: dict[str, Any],
    key: str,
    path: Path,
    field: str,
    problems: list[Problem],
    *,
    required: bool = True,
) -> list[dict[str, Any]]:
    value = data.get(key)
    if value is None and not required:
        return []
    if not isinstance(value, list) or any(not isinstance(item, dict) for item in value):
        problems.append(Problem(path, field, "must be an array of tables"))
        return []
    if required and not value:
        problems.append(Problem(path, field, "must not be empty"))
    return value


def _enum(
    data: dict[str, Any],
    key: str,
    allowed: set[str],
    path: Path,
    field: str,
    problems: list[Problem],
) -> str | None:
    value = _string(data, key, path, field, problems)
    if value is not None and value not in allowed:
        choices = ", ".join(sorted(allowed))
        problems.append(Problem(path, field, f"must be one of: {choices}"))
        return None
    return value


def _date(
    data: dict[str, Any],
    key: str,
    path: Path,
    field: str,
    problems: list[Problem],
) -> dt.date | str | None:
    value = data.get(key)
    if isinstance(value, dt.datetime):
        return value.date()
    if isinstance(value, dt.date):
        return value
    if isinstance(value, str):
        try:
            dt.date.fromisoformat(value)
        except ValueError:
            problems.append(Problem(path, field, "must be an ISO 8601 date (YYYY-MM-DD)"))
            return None
        return value
    problems.append(Problem(path, field, "must be an ISO 8601 date (YYYY-MM-DD)"))
    return None


def _https_url(
    value: Any,
    path: Path,
    field: str,
    problems: list[Problem],
    *,
    origin_only: bool = False,
) -> str | None:
    if not _is_nonempty_string(value):
        problems.append(Problem(path, field, "must be a non-empty HTTPS URL"))
        return None
    parsed = urlparse(value)
    if parsed.scheme != "https" or not parsed.hostname:
        problems.append(Problem(path, field, "must use HTTPS and include a host"))
        return None
    if parsed.username or parsed.password:
        problems.append(Problem(path, field, "must not contain credentials"))
    if origin_only and (
        parsed.path not in {"", "/"} or parsed.params or parsed.query or parsed.fragment
    ):
        problems.append(Problem(path, field, "must be an origin without path, query, or fragment"))
    return value


def _reject_unknown_keys(
    data: dict[str, Any],
    allowed: set[str],
    path: Path,
    field: str,
    problems: list[Problem],
) -> None:
    for key in sorted(set(data) - allowed):
        problems.append(Problem(path, f"{field}.{key}".strip("."), "unknown field"))


def _reject_unsafe_or_placeholder_values(
    value: Any,
    path: Path,
    field: str,
    problems: list[Problem],
) -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            child = f"{field}.{key}".strip(".")
            if key.lower() in FORBIDDEN_METADATA_KEYS:
                problems.append(
                    Problem(path, child, "executable commands and scripts are forbidden in metadata")
                )
            _reject_unsafe_or_placeholder_values(item, path, child, problems)
    elif isinstance(value, list):
        for index, item in enumerate(value):
            _reject_unsafe_or_placeholder_values(item, path, f"{field}[{index}]", problems)
    elif isinstance(value, str) and value.strip().upper().startswith("TODO:"):
        problems.append(Problem(path, field, "replace the scaffold placeholder before committing"))


def _asset_path(
    app_dir: Path,
    relative: Any,
    source_path: Path,
    field: str,
    problems: list[Problem],
) -> Path | None:
    if not _is_nonempty_string(relative):
        problems.append(Problem(source_path, field, "must be a non-empty relative asset path"))
        return None
    candidate = Path(relative)
    if candidate.is_absolute():
        problems.append(Problem(source_path, field, "must be relative to the app directory"))
        return None
    resolved = (app_dir / candidate).resolve()
    try:
        resolved.relative_to(app_dir.resolve())
    except ValueError:
        problems.append(Problem(source_path, field, "must not leave the app directory"))
        return None
    if not resolved.is_file():
        problems.append(Problem(source_path, field, f"asset does not exist: {relative}"))
        return None
    if resolved.suffix.lower() not in MEDIA_SUFFIXES:
        choices = ", ".join(sorted(MEDIA_SUFFIXES))
        problems.append(Problem(source_path, field, f"unsupported media type; expected: {choices}"))
    if resolved.stat().st_size > 10 * 1024 * 1024:
        problems.append(Problem(source_path, field, "asset exceeds the 10 MiB source limit"))
    return resolved


def _validate_artifact(
    artifact: dict[str, Any],
    path: Path,
    field: str,
    problems: list[Problem],
) -> None:
    _reject_unknown_keys(
        artifact,
        {
            "format",
            "expected_package_names",
            "architectures",
            "version_source",
            "min_bytes",
            "max_bytes",
            "mime_types",
        },
        path,
        field,
        problems,
    )
    if _enum(artifact, "format", {"deb"}, path, f"{field}.format", problems) is None:
        return
    packages = _string_list(
        artifact,
        "expected_package_names",
        path,
        f"{field}.expected_package_names",
        problems,
    )
    for package in packages:
        if not PACKAGE_NAME_RE.fullmatch(package):
            problems.append(Problem(path, f"{field}.expected_package_names", f"invalid package name: {package}"))
    architectures = _string_list(
        artifact, "architectures", path, f"{field}.architectures", problems
    )
    for architecture in architectures:
        if not ARCH_RE.fullmatch(architecture):
            problems.append(Problem(path, f"{field}.architectures", f"invalid architecture: {architecture}"))
    _enum(
        artifact,
        "version_source",
        {"deb-control"},
        path,
        f"{field}.version_source",
        problems,
    )
    min_bytes = artifact.get("min_bytes")
    max_bytes = artifact.get("max_bytes")
    if min_bytes is not None and (not isinstance(min_bytes, int) or min_bytes <= 0):
        problems.append(Problem(path, f"{field}.min_bytes", "must be a positive integer"))
    if max_bytes is not None and (not isinstance(max_bytes, int) or max_bytes <= 0):
        problems.append(Problem(path, f"{field}.max_bytes", "must be a positive integer"))
    if isinstance(min_bytes, int) and isinstance(max_bytes, int) and min_bytes > max_bytes:
        problems.append(Problem(path, field, "min_bytes must not exceed max_bytes"))
    _string_list(artifact, "mime_types", path, f"{field}.mime_types", problems, required=False)


def _validate_installer(
    installer: dict[str, Any],
    path: Path,
    index: int,
    problems: list[Problem],
) -> tuple[str | None, str | None]:
    field = f"installers[{index}]"
    _reject_unknown_keys(
        installer,
        {
            "id",
            "kind",
            "priority",
            "architectures",
            "update_policy",
            "package",
            "policy",
            "acquisition",
            "artifact",
        },
        path,
        field,
        problems,
    )
    installer_id = _string(installer, "id", path, f"{field}.id", problems)
    kind = _enum(installer, "kind", INSTALLER_KINDS, path, f"{field}.kind", problems)
    priority = installer.get("priority")
    if priority is not None and not isinstance(priority, int):
        problems.append(Problem(path, f"{field}.priority", "must be an integer"))
    architectures = _string_list(
        installer, "architectures", path, f"{field}.architectures", problems, required=False
    )
    for architecture in architectures:
        if not ARCH_RE.fullmatch(architecture):
            problems.append(Problem(path, f"{field}.architectures", f"invalid architecture: {architecture}"))
    update_policy = _enum(
        installer,
        "update_policy",
        {"managed", "repeat-acquisition", "external"},
        path,
        f"{field}.update_policy",
        problems,
    )

    if kind == "aosc-repository":
        if update_policy != "managed":
            problems.append(
                Problem(path, f"{field}.update_policy", "aosc-repository requires managed")
            )
        package = _table(installer, "package", path, f"{field}.package", problems)
        _reject_unknown_keys(package, {"backend", "names"}, path, f"{field}.package", problems)
        _enum(package, "backend", {"amo"}, path, f"{field}.package.backend", problems)
        names = _string_list(package, "names", path, f"{field}.package.names", problems)
        for name in names:
            if not PACKAGE_NAME_RE.fullmatch(name):
                problems.append(Problem(path, f"{field}.package.names", f"invalid package name: {name}"))
        if "acquisition" in installer or "artifact" in installer:
            problems.append(
                Problem(path, field, "aosc-repository must not define acquisition or artifact")
            )
    elif kind in {"direct-deb", "browser-assisted-deb"}:
        if update_policy != "repeat-acquisition":
            problems.append(
                Problem(
                    path,
                    f"{field}.update_policy",
                    f"{kind} requires repeat-acquisition",
                )
            )
        policy = _table(installer, "policy", path, f"{field}.policy", problems)
        _reject_unknown_keys(
            policy,
            {"redistribution", "automation", "license_acceptance"},
            path,
            f"{field}.policy",
            problems,
        )
        _enum(
            policy,
            "redistribution",
            {"allowed", "forbidden", "unknown"},
            path,
            f"{field}.policy.redistribution",
            problems,
        )
        automation = _enum(
            policy,
            "automation",
            {"automatic", "user-mediated"},
            path,
            f"{field}.policy.automation",
            problems,
        )
        _enum(
            policy,
            "license_acceptance",
            {"none", "upstream-page", "before-install"},
            path,
            f"{field}.policy.license_acceptance",
            problems,
        )
        acquisition = _table(installer, "acquisition", path, f"{field}.acquisition", problems)
        _reject_unknown_keys(
            acquisition,
            {
                "url",
                "landing_url",
                "user_interaction",
                "allowed_download_origins",
                "persist_final_url",
            },
            path,
            f"{field}.acquisition",
            problems,
        )
        if kind == "direct-deb":
            _https_url(acquisition.get("url"), path, f"{field}.acquisition.url", problems)
            if automation != "automatic":
                problems.append(
                    Problem(path, f"{field}.policy.automation", "direct-deb requires automatic")
                )
        else:
            _https_url(
                acquisition.get("landing_url"),
                path,
                f"{field}.acquisition.landing_url",
                problems,
            )
            _enum(
                acquisition,
                "user_interaction",
                {"required"},
                path,
                f"{field}.acquisition.user_interaction",
                problems,
            )
            if automation != "user-mediated":
                problems.append(
                    Problem(
                        path,
                        f"{field}.policy.automation",
                        "browser-assisted-deb requires user-mediated",
                    )
                )
        origins = _string_list(
            acquisition,
            "allowed_download_origins",
            path,
            f"{field}.acquisition.allowed_download_origins",
            problems,
        )
        for origin_index, origin in enumerate(origins):
            _https_url(
                origin,
                path,
                f"{field}.acquisition.allowed_download_origins[{origin_index}]",
                problems,
                origin_only=True,
            )
        if acquisition.get("persist_final_url") is not False:
            problems.append(
                Problem(path, f"{field}.acquisition.persist_final_url", "must be false")
            )
        artifact = _table(installer, "artifact", path, f"{field}.artifact", problems)
        _validate_artifact(artifact, path, f"{field}.artifact", problems)
        if "package" in installer:
            problems.append(Problem(path, f"{field}.package", f"{kind} must not define a repository package"))
    elif kind == "external-link":
        if update_policy != "external":
            problems.append(
                Problem(path, f"{field}.update_policy", "external-link requires external")
            )
        acquisition = _table(installer, "acquisition", path, f"{field}.acquisition", problems)
        _reject_unknown_keys(
            acquisition, {"landing_url"}, path, f"{field}.acquisition", problems
        )
        _https_url(
            acquisition.get("landing_url"),
            path,
            f"{field}.acquisition.landing_url",
            problems,
        )
        if "artifact" in installer or "package" in installer:
            problems.append(
                Problem(path, field, "external-link must not define package or artifact")
            )
    return installer_id, kind


def _validate_app(
    root: Path,
    app_dir: Path,
    path: Path,
    categories: set[str],
    problems: list[Problem],
    data: dict[str, Any] | None = None,
    generated: bool = False,
) -> dict[str, Any] | None:
    if data is None:
        data = _load_toml(path, problems)
    if data is None:
        return None
    _reject_unknown_keys(data, APP_KEYS, path, "", problems)
    if "external" in data and not isinstance(data["external"], bool):
        problems.append(Problem(path, "external", "must be a boolean"))
    _reject_unsafe_or_placeholder_values(data, path, "", problems)
    if data.get("schema_version") != 1:
        problems.append(Problem(path, "schema_version", "must equal 1"))
    app_id = _string(data, "id", path, "id", problems)
    if app_id is not None:
        if not APP_ID_RE.fullmatch(app_id):
            problems.append(Problem(path, "id", "must match [a-z0-9][a-z0-9+._-]*"))
        if app_id != app_dir.name:
            problems.append(Problem(path, "id", f"must match directory name {app_dir.name!r}"))
    _enum(data, "visibility", VISIBILITIES, path, "visibility", problems)
    _enum(data, "lifecycle", LIFECYCLES, path, "lifecycle", problems)
    default_locale = _string(data, "default_locale", path, "default_locale", problems)
    app_categories = _string_list(data, "categories", path, "categories", problems)
    for category in app_categories:
        if category not in categories:
            problems.append(Problem(path, "categories", f"unknown category: {category}"))
    _string_list(data, "aliases", path, "aliases", problems, required=False)
    _string_list(data, "keywords", path, "keywords", problems, required=False)
    _string_list(data, "maintainers", path, "maintainers", problems, required=not generated or "maintainers" in data)
    if not generated or "reviewed_at" in data:
        _date(data, "reviewed_at", path, "reviewed_at", problems)

    locales = _table(data, "locales", path, "locales", problems)
    if default_locale is not None and default_locale not in locales:
        problems.append(Problem(path, "locales", f"must contain default locale {default_locale!r}"))
    for locale, translation in locales.items():
        field = f"locales.{locale}"
        if not isinstance(translation, dict):
            problems.append(Problem(path, field, "must be a table"))
            continue
        _reject_unknown_keys(
            translation, {"name", "summary", "description"}, path, field, problems
        )
        _string(translation, "name", path, f"{field}.name", problems)
        if not generated or locale == default_locale or "summary" in translation:
            _string(translation, "summary", path, f"{field}.summary", problems)
        description = None
        if not generated or "description" in translation:
            description = _string(translation, "description", path, f"{field}.description", problems)
        if description is not None:
            description_path = app_dir / description
            resolved = description_path.resolve()
            try:
                resolved.relative_to(app_dir.resolve())
            except ValueError:
                problems.append(Problem(path, f"{field}.description", "must not leave the app directory"))
            else:
                if not resolved.is_file():
                    problems.append(
                        Problem(path, f"{field}.description", f"file does not exist: {description}")
                    )

    media = _table(data, "media", path, "media", problems)
    _reject_unknown_keys(
        media, {"icon", "hero", "hero_focal_point", "screenshots"}, path, "media", problems
    )
    for asset in ("icon", "hero"):
        if not generated or asset in media:
            _asset_path(app_dir, media.get(asset), path, f"media.{asset}", problems)
    focal_point = media.get("hero_focal_point")
    if focal_point is not None and (
        not isinstance(focal_point, list)
        or len(focal_point) != 2
        or any(not isinstance(item, (int, float)) or not 0 <= item <= 1 for item in focal_point)
    ):
        problems.append(Problem(path, "media.hero_focal_point", "must contain two numbers from 0 to 1"))
    screenshots = _list_of_tables(
        media, "screenshots", path, "media.screenshots", problems, required=False
    )
    for index, screenshot in enumerate(screenshots):
        field = f"media.screenshots[{index}]"
        _reject_unknown_keys(screenshot, {"path", "alt"}, path, field, problems)
        _asset_path(app_dir, screenshot.get("path"), path, f"{field}.path", problems)
        alt = _table(screenshot, "alt", path, f"{field}.alt", problems)
        if default_locale is not None and not _is_nonempty_string(alt.get(default_locale)):
            problems.append(
                Problem(path, f"{field}.alt", f"must contain default locale {default_locale!r}")
            )

    if not generated or "publisher" in data:
        publisher = _table(data, "publisher", path, "publisher", problems)
        _reject_unknown_keys(
            publisher, {"name", "relationship", "homepage"}, path, "publisher", problems
        )
        if not generated or "name" in publisher:
            _string(publisher, "name", path, "publisher.name", problems)
        if not generated or "relationship" in publisher:
            _enum(publisher, "relationship", {"upstream", "aosc", "third-party", "community"},
                  path, "publisher.relationship", problems)
        if not generated or "homepage" in publisher:
            _https_url(publisher.get("homepage"), path, "publisher.homepage", problems)

    links = _table(data, "links", path, "links", problems, required=False)
    _reject_unknown_keys(
        links, {"homepage", "support", "privacy", "license", "issues"}, path, "links", problems
    )
    for key, value in links.items():
        _https_url(value, path, f"links.{key}", problems)

    disclosures = _table(data, "disclosures", path, "disclosures", problems)
    _reject_unknown_keys(
        disclosures,
        set(DISCLOSURE_VALUES) | {"reviewed_at", "notes"},
        path,
        "disclosures",
        problems,
    )
    for key, allowed in DISCLOSURE_VALUES.items():
        _enum(disclosures, key, allowed, path, f"disclosures.{key}", problems)
    if not generated or "reviewed_at" in disclosures:
        _date(disclosures, "reviewed_at", path, "disclosures.reviewed_at", problems)
    _string_list(disclosures, "notes", path, "disclosures.notes", problems, required=False)

    installers = _list_of_tables(data, "installers", path, "installers", problems)
    installer_ids: set[str] = set()
    for index, installer in enumerate(installers):
        installer_id, _kind = _validate_installer(installer, path, index, problems)
        if installer_id is not None:
            if installer_id in installer_ids:
                problems.append(Problem(path, f"installers[{index}].id", "must be unique within the app"))
            installer_ids.add(installer_id)
    return data


def _validate_collection(
    path: Path,
    app_ids: set[str],
    problems: list[Problem],
) -> dict[str, Any] | None:
    data = _load_toml(path, problems)
    if data is None:
        return None
    _reject_unknown_keys(
        data,
        {"schema_version", "id", "visibility", "locales", "apps"},
        path,
        "",
        problems,
    )
    _reject_unsafe_or_placeholder_values(data, path, "", problems)
    if data.get("schema_version") != 1:
        problems.append(Problem(path, "schema_version", "must equal 1"))
    collection_id = _string(data, "id", path, "id", problems)
    if collection_id is not None:
        if not APP_ID_RE.fullmatch(collection_id):
            problems.append(Problem(path, "id", "must match [a-z0-9][a-z0-9+._-]*"))
        if collection_id != path.stem:
            problems.append(Problem(path, "id", f"must match file name {path.stem!r}"))
    _enum(data, "visibility", {"listed", "hidden"}, path, "visibility", problems)
    locales = _table(data, "locales", path, "locales", problems)
    for locale, translation in locales.items():
        if not isinstance(translation, dict) or not _is_nonempty_string(translation.get("title")):
            problems.append(Problem(path, f"locales.{locale}.title", "must be a non-empty string"))
    apps = _string_list(data, "apps", path, "apps", problems, required=False)
    if len(apps) != len(set(apps)):
        problems.append(Problem(path, "apps", "must not contain duplicate app IDs"))
    for app_id in apps:
        if app_id not in app_ids:
            problems.append(Problem(path, "apps", f"references unknown app: {app_id}"))
    return data


def _homepage_file(path: Path, fields: set[str], problems: list[Problem]) -> dict[str, Any] | None:
    if not path.exists():
        return None
    data = _load_toml(path, problems)
    if data is not None:
        _reject_unknown_keys(data, fields | {"schema_version"}, path, "", problems)
        _reject_unsafe_or_placeholder_values(data, path, "", problems)
        if type(data.get("schema_version")) is not int or data["schema_version"] != 1:
            problems.append(Problem(path, "schema_version", "must equal 1"))
    return data


def _homepage_locales(
    data: dict[str, Any], default_locale: str, path: Path, field: str, problems: list[Problem]
) -> dict[str, Any]:
    locales = _table(data, "locales", path, field, problems)
    if isinstance(default_locale, str) and default_locale not in locales:
        problems.append(Problem(path, field, f"must contain default locale {default_locale!r}"))
    for locale in locales:
        prefix = f"{field}.{locale}"
        translation = _table(locales, locale, path, prefix, problems)
        _reject_unknown_keys(translation, {"title", "subtitle"}, path, prefix, problems)
        _string(translation, "title", path, f"{prefix}.title", problems)
        if "subtitle" in translation:
            _string(translation, "subtitle", path, f"{prefix}.subtitle", problems)
    return locales


def _validate_banner(
    data: dict[str, Any], path: Path, apps: dict[str, Any], collections: dict[str, Any],
    default_locale: str, problems: list[Problem], prefix: str = "",
) -> dict[str, Any]:
    target_field = f"{prefix}target"
    image_field = f"{prefix}image"
    target = _table(data, "target", path, target_field, problems)
    _reject_unknown_keys(target, {"app", "collection", "url"}, path, target_field, problems)
    if len(target) != 1:
        problems.append(Problem(path, target_field, "specify exactly one of app, collection, or url"))
    if "url" in target:
        _https_url(target["url"], path, f"{target_field}.url", problems)
    for key, catalog in (("app", apps), ("collection", collections)):
        if key in target:
            value = target[key]
            if not isinstance(value, str) or value not in catalog:
                problems.append(Problem(path, f"{target_field}.{key}", f"references unknown {key}: {value}"))

    app_id = target.get("app")
    relative = data.get("image")
    asset_dir = path.parent
    output_dir = "homepage"
    if "image" not in data and isinstance(app_id, str) and app_id in apps:
        media = apps[app_id].get("media")
        relative = media.get("hero") if isinstance(media, dict) else None
        asset_dir = path.parents[1] / "apps" / app_id
        output_dir = f"apps/{app_id}"
    image = None
    if relative is None:
        problems.append(Problem(path, image_field, "required unless the target app supplies media.hero"))
    elif not isinstance(relative, str) or (
        not Path(relative).is_relative_to("assets") or ".." in Path(relative).parts
    ):
        problems.append(Problem(path, image_field, "must be a relative path under assets/"))
    else:
        asset = Path(relative).relative_to("assets")
        if _asset_path(asset_dir / "assets", asset.as_posix(), path, image_field, problems):
            image = f"{output_dir}/assets/{asset.as_posix()}"
    locales = _homepage_locales(data, default_locale, path, f"{prefix}locales", problems)
    return {"target": target, "image": image, "locales": locales}


def _read_banners(
    path: Path, apps: dict[str, Any], collections: dict[str, Any], default_locale: str,
    problems: list[Problem],
) -> list[dict[str, Any]]:
    fields = {"target", "image", "locales"}
    data = _homepage_file(path, fields | {"banners"}, problems)
    if data is None:
        return []
    if "banners" not in data:
        return [_validate_banner(data, path, apps, collections, default_locale, problems)]

    if fields.intersection(data):
        problems.append(Problem(path, "banners", "cannot combine banners with top-level target, image, or locales"))
    banners = _list_of_tables(data, "banners", path, "banners", problems, required=False)
    result = []
    for index, banner in enumerate(banners):
        field = f"banners[{index}]"
        _reject_unknown_keys(banner, fields, path, field, problems)
        result.append(_validate_banner(banner, path, apps, collections, default_locale, problems, field + "."))
    return result


def _read_guides(path: Path, default_locale: str, problems: list[Problem]) -> dict[str, Any]:
    data = _homepage_file(path, {"items", "more_url"}, problems)
    guides: dict[str, Any] = {"items": []}
    if data is None:
        return guides
    if "more_url" in data:
        guides["more_url"] = _https_url(data["more_url"], path, "more_url", problems)
    if "items" not in data:
        problems.append(Problem(path, "items", "must be an array of tables (which may be empty)"))
    items = _list_of_tables(data, "items", path, "items", problems, required=False)
    ids: set[str] = set()
    for index, item in enumerate(items):
        prefix = f"items[{index}]"
        _reject_unknown_keys(item, {"id", "url", "date", "locales"}, path, prefix, problems)
        guide_id = item.get("id")
        if not isinstance(guide_id, str) or not APP_ID_RE.fullmatch(guide_id):
            problems.append(Problem(path, f"{prefix}.id", "must match [a-z0-9][a-z0-9+._-]*"))
        elif guide_id in ids:
            problems.append(Problem(path, f"{prefix}.id", f"duplicate guide ID: {guide_id}"))
        else:
            ids.add(guide_id)
        _https_url(item.get("url"), path, f"{prefix}.url", problems)
        date = item.get("date")
        if isinstance(date, dt.datetime) or (
            isinstance(date, str) and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", date)
        ):
            problems.append(Problem(path, f"{prefix}.date", "must be a calendar date (YYYY-MM-DD)"))
        else:
            _date(item, "date", path, f"{prefix}.date", problems)
        _homepage_locales(item, default_locale, path, f"{prefix}.locales", problems)
    guides["items"] = items
    return guides


def _read_homepage(
    manual_root: Path, apps: dict[str, Any], collections: dict[str, Any], default_locale: str,
    problems: list[Problem],
) -> dict[str, Any]:
    directory = manual_root / "homepage"
    banners = _read_banners(directory / "hero.toml", apps, collections, default_locale, problems)
    return {
        "schema_version": 1,
        "hero": banners[0] if banners else None,
        "banners": banners,
        "essentials": "essentials" if collections.get("essentials", {}).get("visibility") == "listed" else None,
        "guides": _read_guides(directory / "guides.toml", default_locale, problems),
    }


def _read_abbs(tree: Path | None, commit: str | None) -> dict[str, Any] | None:
    if tree is None:
        if commit:
            raise ValueError("--abbs-commit requires --abbs-tree")
        return None
    if __package__:
        from .abbs import snapshot
    else:
        from abbs import snapshot
    try:
        revision = subprocess.check_output(["git", "-C", str(tree), "rev-parse", "HEAD"], text=True, stderr=subprocess.PIPE).strip()
        dirty = subprocess.check_output(["git", "-C", str(tree), "status", "--porcelain"], text=True, stderr=subprocess.PIPE).strip()
    except (OSError, subprocess.CalledProcessError) as error:
        raise ValueError("ABBS tree must be a readable Git checkout") from error
    if commit and commit != revision:
        raise ValueError("--abbs-commit must equal the ABBS checkout HEAD")
    if dirty:
        raise ValueError("ABBS checkout must be clean so its commit identifies the input")
    return snapshot(tree.resolve(), revision)


def _merge_metadata(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    result = copy.deepcopy(base)
    for key, value in overlay.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _merge_metadata(result[key], value)
        else:
            result[key] = copy.deepcopy(value)
    return result


def _generated_app(name: str, facts: dict[str, Any], categories: dict[str, Any]) -> dict[str, Any]:
    category = facts["section"] if facts["section"] in categories else "uncategorized"
    return {
        "schema_version": 1, "id": name, "external": False,
        "visibility": "listed", "lifecycle": "active", "default_locale": "en",
        "categories": [category], "locales": {"en": {"name": name, "summary": facts["description"]}},
        "media": {}, "disclosures": {key: "unknown" for key in DISCLOSURE_VALUES},
        "installers": [{"id": "aosc", "kind": "aosc-repository", "priority": 100,
                        "architectures": [], "update_policy": "managed",
                        "package": {"backend": "amo", "names": [name]}}],
    }


def _resolve_apps(manual: dict[str, Any], inventory: dict[str, Any], categories: dict[str, Any], root: Path, problems: list[Problem]) -> dict[str, Any]:
    packages = inventory["packages"]
    unresolved = {item["package_name"] for item in inventory.get("skipped", []) if isinstance(item.get("package_name"), str)}
    result = {}
    claimed = set()
    for directory, overlay in manual.items():
        path = root / "apps" / directory / "app.toml"
        external = overlay.get("external", False)
        if not isinstance(external, bool):
            problems.append(Problem(path, "external", "must be a boolean"))
            continue
        installers = overlay.get("installers", [])
        refs = []
        if isinstance(installers, list):
            for installer in installers:
                if isinstance(installer, dict) and installer.get("kind") == "aosc-repository":
                    names = installer.get("package", {}).get("names", []) if isinstance(installer.get("package"), dict) else []
                    if isinstance(names, list):
                        refs.extend(name for name in names if isinstance(name, str))
        if external:
            expected = set()
            if isinstance(installers, list):
                for installer in installers:
                    artifact = installer.get("artifact") if isinstance(installer, dict) else None
                    if isinstance(artifact, dict) and isinstance(artifact.get("expected_package_names"), list):
                        expected.update(name for name in artifact["expected_package_names"] if isinstance(name, str))
            if directory in packages or directory in unresolved or expected.intersection(set(packages) | unresolved) or refs:
                problems.append(Problem(path, "external", "external=true cannot match an ABBS package or declare a repository installer"))
            result[directory] = copy.deepcopy(overlay)
            continue
        refs = refs or [directory]
        if directory in packages and directory not in refs:
            problems.append(Problem(path, "id", "application ID conflicts with another ABBS package"))
        missing = [name for name in refs if name not in packages]
        if missing:
            problems.append(Problem(path, "installers.package.names", f"ABBS package {missing[0]!r} is missing or ambiguous; declare external=true for an external app"))
            continue
        if claimed.intersection(refs):
            problems.append(Problem(path, "installers.package.names", "package is already claimed by another application"))
        claimed.update(refs)
        base = _generated_app(refs[0], packages[refs[0]], categories)
        base["id"] = directory
        locales = overlay.get("locales", {})
        if isinstance(locales, dict):
            for locale in locales:
                if locale not in base["locales"]:
                    base["locales"][locale] = {"name": refs[0]}
        result[directory] = _merge_metadata(base, overlay)
    for name, facts in sorted(packages.items()):
        if name not in claimed and name not in result:
            result[name] = _generated_app(name, facts, categories)
    return result


def validate_catalog(root: Path, *, abbs_tree: Path | None = None, abbs_commit: str | None = None) -> tuple[Catalog | None, list[Problem]]:
    root = root.resolve()
    manual_root = root / "manual"
    problems: list[Problem] = []
    config_path = manual_root / "repository.toml"
    config = _load_toml(config_path, problems)
    taxonomy_path = manual_root / "taxonomy" / "categories.toml"
    taxonomy = _load_toml(taxonomy_path, problems)
    if config is None or taxonomy is None:
        return None, problems

    _reject_unknown_keys(
        config,
        {
            "schema_version",
            "repository_id",
            "default_locale",
            "minimum_client_version",
        },
        config_path,
        "",
        problems,
    )
    if config.get("schema_version") != 1:
        problems.append(Problem(config_path, "schema_version", "must equal 1"))
    _string(config, "repository_id", config_path, "repository_id", problems)
    _string(config, "default_locale", config_path, "default_locale", problems)
    _string(
        config,
        "minimum_client_version",
        config_path,
        "minimum_client_version",
        problems,
    )

    categories_value = taxonomy.get("categories")
    if not isinstance(categories_value, dict) or not categories_value:
        problems.append(Problem(taxonomy_path, "categories", "must be a non-empty table"))
        categories: dict[str, Any] = {}
    else:
        categories = categories_value
        for category_id, category in categories.items():
            if not APP_ID_RE.fullmatch(category_id):
                problems.append(Problem(taxonomy_path, f"categories.{category_id}", "invalid category ID"))
            if not isinstance(category, dict) or not isinstance(category.get("name"), dict):
                problems.append(
                    Problem(taxonomy_path, f"categories.{category_id}.name", "must be a localized table")
                )

    inventory = _read_abbs(abbs_tree, abbs_commit)
    if inventory is not None:
        categories.setdefault("uncategorized", {"name": {"en": "Uncategorized", "zh-CN": "未分类"}})
    apps: dict[str, dict[str, Any]] = {}
    app_dirs: dict[str, Path] = {}
    apps_root = manual_root / "apps"
    if not apps_root.is_dir():
        problems.append(Problem(apps_root, "", "apps directory does not exist"))
    manual = {}
    for app_dir in sorted(path for path in apps_root.iterdir() if path.is_dir()) if apps_root.is_dir() else []:
        data = _load_toml(app_dir / "app.toml", problems)
        if data is not None:
            manual[app_dir.name] = data
    if inventory is None:
        resolved = manual
    else:
        resolved = _resolve_apps(manual, inventory, categories, manual_root, problems)
    for app_id, data in sorted(resolved.items()):
        app_dir = apps_root / app_id
        app = _validate_app(root, app_dir, app_dir / "app.toml", set(categories), problems,
                            data=data, generated=inventory is not None and data.get("external") is False)
        if app is not None:
            apps[app_id] = app
            app_dirs[app_id] = app_dir

    collections: dict[str, dict[str, Any]] = {}
    collections_root = manual_root / "collections"
    if not collections_root.is_dir():
        problems.append(Problem(collections_root, "", "collections directory does not exist"))
    else:
        for path in sorted(collections_root.glob("*.toml")):
            collection = _validate_collection(path, set(apps), problems)
            if collection is not None and _is_nonempty_string(collection.get("id")):
                collection_id = collection["id"]
                if collection_id in collections:
                    problems.append(Problem(path, "id", f"duplicate collection ID: {collection_id}"))
                collections[collection_id] = collection

    homepage = _read_homepage(manual_root, apps, collections, config.get("default_locale"), problems)
    return Catalog(root, config, categories, apps, app_dirs, collections, homepage, inventory), problems


def _json_ready(value: Any) -> Any:
    if isinstance(value, (dt.date, dt.datetime)):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: _json_ready(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_ready(item) for item in value]
    return value


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_json_ready(value), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _catalog_asset_path(app_id: str, relative: str) -> str:
    return f"apps/{app_id}/{relative}"


def _compile_app(app_id: str, app: dict[str, Any], app_dir: Path) -> dict[str, Any]:
    compiled = _json_ready(copy.deepcopy(app))
    for locale, translation in compiled["locales"].items():
        if "description" in translation:
            description_path = app_dir / translation.pop("description")
            translation["description_markdown"] = description_path.read_text(encoding="utf-8")
    media = compiled["media"]
    for asset in ("icon", "hero"):
        if asset in media:
            media[asset] = _catalog_asset_path(app_id, media[asset])
    for screenshot in media.get("screenshots", []):
        screenshot["path"] = _catalog_asset_path(app_id, screenshot["path"])
    return compiled


def _package_refs(app: dict[str, Any]) -> list[str]:
    refs: set[str] = set()
    for installer in app.get("installers", []):
        if installer.get("kind") == "aosc-repository":
            for name in installer.get("package", {}).get("names", []):
                refs.add(name)
        else:
            for name in installer.get("artifact", {}).get("expected_package_names", []):
                refs.add(name)
    return sorted(refs)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _catalog_revision(root: Path, abbs_inventory: dict[str, Any] | None = None) -> str:
    digest = hashlib.sha256()
    sources = [root / "repository.toml"]
    for directory in ("taxonomy", "apps", "collections", "homepage"):
        base = root / directory
        if base.is_dir():
            sources.extend(path for path in base.rglob("*") if path.is_file())
    for path in sorted(sources):
        relative = path.relative_to(root).as_posix().encode("utf-8")
        digest.update(len(relative).to_bytes(8, "big"))
        digest.update(relative)
        content = path.read_bytes()
        digest.update(len(content).to_bytes(8, "big"))
        digest.update(content)
    if abbs_inventory is not None:
        digest.update(json.dumps(abbs_inventory, sort_keys=True, ensure_ascii=False).encode("utf-8"))
    return f"sha256:{digest.hexdigest()}"


def build_catalog(
    root: Path,
    output: Path,
    *,
    generated_at: str | None = None,
    source_commit: str | None = None,
    abbs_tree: Path | None = None,
    abbs_commit: str | None = None,
) -> Path:
    catalog, problems = validate_catalog(root, abbs_tree=abbs_tree, abbs_commit=abbs_commit)
    if catalog is None or problems:
        for problem in problems:
            print(problem.display(root.resolve()), file=sys.stderr)
        raise ValueError(f"catalog validation failed with {len(problems)} error(s)")

    inventory = catalog.abbs_inventory

    root = root.resolve()
    output = output if output.is_absolute() else root / output
    output = output.resolve()
    if abbs_tree is not None:
        abbs_root = abbs_tree.resolve()
        if output == abbs_root or output in abbs_root.parents or abbs_root in output.parents:
            raise ValueError("output directory must be outside the ABBS checkout")
    # A catalog root (including examples/) owns only its dist/ build directory.
    # Also protect this checkout when a fixture builds to an absolute path.
    checkout = Path(__file__).resolve().parents[1]
    inside_sources = output.is_relative_to(root) or output.is_relative_to(checkout)
    if output in root.parents or output in checkout.parents or (
        inside_sources and not output.is_relative_to(root / "dist")
    ):
        raise ValueError(f"refusing to replace unsafe output directory: {output}")
    if output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True)
    if inventory is not None:
        _write_json(output / "abbs-packages.json", inventory)

    entries: list[dict[str, Any]] = []
    for app_id in sorted(catalog.apps):
        app = catalog.apps[app_id]
        app_dir = catalog.app_dirs[app_id]
        compiled = _compile_app(app_id, app, app_dir)
        if inventory is not None:
            refs = sorted({
                name for installer in app["installers"]
                if installer["kind"] == "aosc-repository"
                for name in installer["package"]["names"]
            })
            if not refs and not app.get("external") and app_id in inventory["packages"]:
                refs = [app_id]
            if refs:
                compiled["abbs"] = {
                    "source_commit": inventory["source_commit"],
                    "packages": {name: inventory["packages"][name] for name in refs},
                }
        _write_json(output / "apps" / f"{app_id}.json", compiled)
        assets = app_dir / "assets"
        if assets.is_dir():
            shutil.copytree(assets, output / "apps" / app_id / "assets")
        if app["visibility"] == "listed" and app["lifecycle"] == "active":
            entries.append(
                {
                    "id": app_id,
                    "external": app.get("external", False),
                    "default_locale": app["default_locale"],
                    "locales": {
                        locale: {
                            "name": translation["name"],
                            **({"summary": translation["summary"]} if "summary" in translation else {}),
                        }
                        for locale, translation in app["locales"].items()
                    },
                    "categories": app["categories"],
                    "aliases": app.get("aliases", []),
                    "keywords": app.get("keywords", []),
                    "icon": _catalog_asset_path(app_id, app["media"]["icon"]) if "icon" in app["media"] else None,
                    "hero": _catalog_asset_path(app_id, app["media"]["hero"]) if "hero" in app["media"] else None,
                    "installer_kinds": sorted(
                        {installer["kind"] for installer in app["installers"]}
                    ),
                    "package_refs": _package_refs(app),
                }
            )

    index = {
        "schema_version": 1,
        "catalog_id": catalog.config["repository_id"],
        "default_locale": catalog.config["default_locale"],
        "categories": _json_ready(catalog.categories),
        "homepage": "homepage.json",
        "apps": entries,
    }
    if inventory is not None:
        index["abbs_inventory"] = "abbs-packages.json"
    _write_json(output / "index.json", index)
    _write_json(output / "homepage.json", catalog.homepage)
    banner_images = {banner["image"] for banner in catalog.homepage["banners"]}
    for image in sorted(banner_images):
        if not image.startswith("homepage/assets/"):
            continue
        image_path = Path(image)
        (output / image_path).parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(root / "manual" / image_path, output / image_path)
    _write_json(
        output / "collections.json",
        {
            "schema_version": 1,
            "collections": [
                _json_ready(catalog.collections[key]) for key in sorted(catalog.collections)
            ],
        },
    )

    if generated_at is None:
        generated_at = dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")
    else:
        try:
            dt.datetime.fromisoformat(generated_at.replace("Z", "+00:00"))
        except ValueError as error:
            raise ValueError("--generated-at must be an ISO 8601 timestamp") from error
    source_commit = source_commit or os.environ.get("GITHUB_SHA")
    files = []
    for path in sorted(item for item in output.rglob("*") if item.is_file()):
        relative = path.relative_to(output).as_posix()
        files.append(
            {
                "path": relative,
                "sha256": _sha256(path),
                "bytes": path.stat().st_size,
            }
        )
    manifest = {
        "schema_version": 1,
        "catalog_id": catalog.config["repository_id"],
        "catalog_revision": _catalog_revision(root / "manual", inventory),
        "minimum_client_version": catalog.config["minimum_client_version"],
        "generated_at": generated_at,
        "source_commit": source_commit,
        "files": files,
    }
    if inventory is not None:
        manifest["abbs_source_commit"] = inventory["source_commit"]
        manifest["abbs_inventory"] = "abbs-packages.json"
    _write_json(output / "manifest.json", manifest)
    return output


def _placeholder_svg(label: str, width: int, height: int) -> str:
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">
  <rect width="100%" height="100%" fill="#202326"/>
  <text x="50%" y="50%" dominant-baseline="middle" text-anchor="middle" fill="#f4f7f4" font-family="sans-serif" font-size="24">{label}</text>
</svg>
"""


def scaffold_app(root: Path, app_id: str, kind: str, category: str | None = None) -> Path:
    manual_root = root.resolve() / "manual"
    if not APP_ID_RE.fullmatch(app_id):
        raise ValueError("app ID must match [a-z0-9][a-z0-9+._-]*")
    if kind not in INSTALLER_KINDS:
        raise ValueError(f"unsupported installer kind: {kind}")
    problems: list[Problem] = []
    config = _load_toml(manual_root / "repository.toml", problems)
    taxonomy = _load_toml(manual_root / "taxonomy" / "categories.toml", problems)
    if problems or config is None or taxonomy is None:
        raise ValueError("manual/repository.toml and manual/taxonomy/categories.toml must be valid first")
    categories = taxonomy.get("categories", {})
    if not isinstance(categories, dict) or not categories:
        raise ValueError("taxonomy must define at least one category")
    if category is not None and category not in categories:
        raise ValueError(f"unknown category: {category}")
    app_dir = manual_root / "apps" / app_id
    if app_dir.exists():
        raise FileExistsError(f"app already exists: {app_dir}")
    if kind == "aosc-repository":
        app_dir.mkdir(parents=True)
        (app_dir / "app.toml").write_text(
            "external = false\n" + (f'categories = ["{category}"]\n' if category else "")
            + '# Other fields inherit from ABBS. Validate with --abbs-tree.\n',
            encoding="utf-8",
        )
        return app_dir
    assets = app_dir / "assets"
    assets.mkdir(parents=True)
    default_locale = config.get("default_locale", "zh-CN")
    (app_dir / f"description.{default_locale}.md").write_text(
        "# TODO: application description\n", encoding="utf-8"
    )
    (assets / "icon.svg").write_text(_placeholder_svg(app_id, 256, 256), encoding="utf-8")
    (assets / "hero.svg").write_text(_placeholder_svg(app_id, 1280, 480), encoding="utf-8")

    category = category or sorted(categories)[0]
    common = f"""schema_version = 1
external = true
id = "{app_id}"
visibility = "listed"
lifecycle = "active"
default_locale = "{default_locale}"
categories = ["{category}"]
aliases = []
keywords = []
maintainers = ["TODO: GitHub handle"]
reviewed_at = {dt.date.today().isoformat()}

[locales."{default_locale}"]
name = "TODO: application name"
summary = "TODO: short summary"
description = "description.{default_locale}.md"

[media]
icon = "assets/icon.svg"
hero = "assets/hero.svg"
hero_focal_point = [0.5, 0.5]
screenshots = []

[publisher]
name = "TODO: publisher"
relationship = "upstream"
homepage = "https://example.invalid/"

[disclosures]
availability = "unknown"
runtime = "unknown"
telemetry = "unknown"
service = "unknown"
support = "unknown"
reviewed_at = {dt.date.today().isoformat()}
notes = []

"""
    if kind in {"direct-deb", "browser-assisted-deb"}:
        acquisition = (
            'url = "https://example.invalid/download.deb"\n'
            if kind == "direct-deb"
            else 'landing_url = "https://example.invalid/download"\nuser_interaction = "required"\n'
        )
        automation = "automatic" if kind == "direct-deb" else "user-mediated"
        installer = f"""[[installers]]
id = "upstream-deb"
kind = "{kind}"
priority = 100
architectures = ["amd64"]
update_policy = "repeat-acquisition"

[installers.policy]
redistribution = "unknown"
automation = "{automation}"
license_acceptance = "upstream-page"

[installers.acquisition]
{acquisition}allowed_download_origins = ["https://example.invalid"]
persist_final_url = false

[installers.artifact]
format = "deb"
expected_package_names = ["{app_id}"]
architectures = ["amd64"]
version_source = "deb-control"
"""
    else:
        installer = """[[installers]]
id = "upstream"
kind = "external-link"
priority = 100
architectures = []
update_policy = "external"

[installers.acquisition]
landing_url = "https://example.invalid/download"
"""
    (app_dir / "app.toml").write_text(common + installer, encoding="utf-8")
    return app_dir


def _print_problems(root: Path, problems: list[Problem]) -> None:
    for problem in problems:
        print(problem.display(root.resolve()), file=sys.stderr)


def _command_check(args: argparse.Namespace) -> int:
    root = Path(args.root)
    try:
        catalog, problems = validate_catalog(root, abbs_tree=Path(args.abbs_tree) if args.abbs_tree else None, abbs_commit=args.abbs_commit)
    except ValueError as error:
        print(str(error), file=sys.stderr)
        return 1
    if problems:
        _print_problems(root, problems)
        print(f"ASMR validation failed: {len(problems)} error(s)", file=sys.stderr)
        return 1
    assert catalog is not None
    print(
        f"ASMR validation passed: {len(catalog.apps)} app(s), "
        f"{len(catalog.collections)} collection(s), {len(catalog.categories)} category(s)"
    )
    return 0


def _command_build(args: argparse.Namespace) -> int:
    root = Path(args.root)
    try:
        output = build_catalog(
            root,
            Path(args.output),
            generated_at=args.generated_at,
            source_commit=args.source_commit,
            abbs_tree=Path(args.abbs_tree) if args.abbs_tree else None,
            abbs_commit=args.abbs_commit,
        )
    except ValueError as error:
        print(str(error), file=sys.stderr)
        return 1
    files = sum(1 for path in output.rglob("*") if path.is_file())
    print(f"Built ASMR catalog: {output} ({files} file(s))")
    return 0


def _command_new(args: argparse.Namespace) -> int:
    try:
        path = scaffold_app(Path(args.root), args.app_id, args.kind, args.category)
    except (FileExistsError, ValueError) as error:
        print(str(error), file=sys.stderr)
        return 1
    print(f"Created app scaffold: {path}")
    print("Replace every TODO value, add production media, then run `asmr check`.")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="asmr",
        description="Maintain and compile AOSC Software Manager metadata.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    check = subparsers.add_parser("check", help="validate all source metadata")
    check.add_argument("--root", default=".", help="repository root")
    check.add_argument("--abbs-tree")
    check.add_argument("--abbs-commit")
    check.set_defaults(handler=_command_check)

    build = subparsers.add_parser("build", help="validate and compile the JSON catalog")
    build.add_argument("--root", default=".", help="repository root")
    build.add_argument("--output", default="dist/v1", help="output directory")
    build.add_argument("--generated-at", help="override generated timestamp for reproducible builds")
    build.add_argument("--source-commit", help="source commit recorded in manifest.json")
    build.add_argument("--abbs-tree", help="clean ABBS Git checkout to generate package facts from")
    build.add_argument("--abbs-commit", help="expected full ABBS commit ID")
    build.set_defaults(handler=_command_build)

    new = subparsers.add_parser("new", help="create a new app metadata scaffold")
    new.add_argument("app_id", help="stable application ID")
    new.add_argument(
        "--kind",
        choices=sorted(INSTALLER_KINDS),
        default="aosc-repository",
        help="initial installer kind",
    )
    new.add_argument("--category", help="initial category ID")
    new.add_argument("--root", default=".", help="repository root")
    new.set_defaults(handler=_command_new)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.handler(args)


if __name__ == "__main__":
    raise SystemExit(main())
