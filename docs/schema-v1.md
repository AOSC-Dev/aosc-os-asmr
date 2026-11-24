# ASMR Metadata Schema v1

**English** | [简体中文](schema-v1.zh-CN.md)

With an ABBS input, handwritten files are partial overlays. The complete field constraints below apply after merging; see [ABBS defaults and overrides](abbs-overlays.md) for optional defaults. External entries require `external = true`.

This document defines the ASMR v1 source and generated-artifact contract.
`tools/asmr.py` is the normative implementation. The JSON Schema documents
under `schemas/` provide editor completion.

Authoritative handwritten inputs live under `manual/`, with examples under
`examples/manual/`. `--root` still selects the repository root or `examples`.
CI reads ABBS `stable` and writes merged JSON and media under ignored `dist/v1/`.
Runtime state comes from the package manager. See the [build workflow](abbs-overlays.md)
for input responsibilities and output restrictions.

## 1. Authority boundaries

| Information | Authority |
| --- | --- |
| Names, descriptions, categories, media, and links | ASMR |
| Publisher relationships and editorial disclosures | ASMR |
| Installation entry points available in the catalog | ASMR |
| AOSC package names or expected external DEB package names | ASMR |
| Package state and installed and candidate versions | amo |
| Actual version, architecture, and digest of an external DEB | Downloaded artifact |
| Transaction plans, progress, and results | amo |

An application ID is a stable catalog identity and is not required to equal a
DEB package name.

## 2. Application documents

Each application lives at `manual/apps/<id>/app.toml`. The `id` must match the
directory name and may contain lowercase ASCII letters, digits, periods,
underscores, plus signs, and hyphens.

Required top-level fields for a standalone, fully authored entry (including external entries):

- `schema_version = 1`
- `id`
- `visibility`: `listed`, `unlisted`, or `hidden`
- `lifecycle`: `active`, `deprecated`, or `blocked`
- `default_locale`
- `categories`
- `maintainers`
- `reviewed_at`
- `locales`
- `media`
- `publisher`
- `disclosures`
- `installers`

Only applications with `visibility = "listed"` and `lifecycle = "active"`
appear in the generated search index.

### 2.1 Localized content

```toml
[locales."en"]
name = "Example App"
summary = "A short application summary"
description = "description.en.md"
```

`description` must refer to a Markdown file inside the application directory.
The build embeds the Markdown content in the application detail JSON and does
not expose the local source path.

### 2.2 Media

```toml
[media]
icon = "assets/icon.svg"
hero = "assets/hero.webp"
hero_focal_point = [0.7, 0.5]

[[media.screenshots]]
path = "assets/screenshots/main.webp"
alt = { zh-CN = "软件主界面", en = "Main window" }
```

- Standalone entries require `icon` and `hero`. ABBS-generated entries may omit either.
- AVIF, JPEG, PNG, SVG, and WebP are supported.
- A source media file must not exceed 10 MiB.
- A path must not escape the application directory.
- Screenshot alternative text must include the default locale.
- `hero_focal_point` is an `[x, y]` coordinate from the top-left corner, with
  each value ranging from 0 to 1.

### 2.3 Editorial disclosures

```toml
[disclosures]
availability = "verified"
runtime = "native"
telemetry = "unknown"
service = "limited"
support = "upstream"
reviewed_at = 2026-07-23
notes = []
```

Enums are used instead of booleans so that absence can be distinguished from
unknown state.

## 3. Installer types

For both DEB download types, the catalog describes how to obtain the file and
which package names and architectures to expect in its control fields.

### 3.1 `aosc-repository`

Aoska passes the AOSC repository package names to amo for installation and updates.

```toml
[[installers]]
id = "aosc"
kind = "aosc-repository"
priority = 100
architectures = ["amd64", "arm64"]
update_policy = "managed"

[installers.package]
backend = "amo"
names = ["example-app"]
```

The repository supplies the package, so omit `acquisition` and `artifact`.

### 3.2 `direct-deb`

Use this only when upstream permits direct client access to a stable DEB URL.

- `policy.automation` must be `automatic`.
- `allowed_download_origins` must constrain accepted downloads.
- The final URL must not be persisted.
- DEB control fields must still be validated after download.

### 3.3 `browser-assisted-deb`

Use this when upstream requires the user to open the website and trigger the
download.

```toml
[[installers]]
id = "upstream-deb"
kind = "browser-assisted-deb"
priority = 100
architectures = ["amd64"]
update_policy = "repeat-acquisition"

[installers.policy]
redistribution = "forbidden"
automation = "user-mediated"
license_acceptance = "upstream-page"

[installers.acquisition]
landing_url = "https://vendor.example/download"
user_interaction = "required"
allowed_download_origins = ["https://download.vendor.example"]
persist_final_url = false

[installers.artifact]
format = "deb"
expected_package_names = ["example-app"]
architectures = ["amd64"]
version_source = "deb-control"
```

Metadata must not contain page selectors, scraping rules, cookies, temporary
tokens, shell commands, or automatic-click scripts.

### 3.4 `external-link`

This kind opens an external page. AOSKA does not acquire or install an
artifact.

```toml
[[installers]]
id = "upstream"
kind = "external-link"
priority = 100
architectures = []
update_policy = "external"

[installers.acquisition]
landing_url = "https://vendor.example/download"
```

This kind uses a landing page and omits `package` and `artifact`.

## 4. Collections

`manual/collections/<id>.toml` contains application IDs only and does not duplicate
names, summaries, or media:

```toml
schema_version = 1
id = "essentials"
visibility = "listed"
apps = ["firefox", "vlc"]

[locales.en]
title = "Essentials"
```

The builder rejects duplicate IDs and references to unknown applications.

## 5. Homepage

The homepage has an ordered banner carousel, an Essentials collection, and an
ordered list of tips and guides. Their sources are maintained independently.

| Source | Fields |
| --- | --- |
| `manual/homepage/hero.toml` | `schema_version = 1` and an ordered array of `[[banners]]`. Each entry has `target`, `locales`, and `image`. Use `banners = []` for an empty carousel. |
| `manual/collections/essentials.toml` | The collection defined in section 4. Its `apps` list sets display order. A listed collection with ID `essentials` appears on the homepage. |
| `manual/homepage/guides.toml` | `schema_version = 1`, an ordered `items` array, and optional `more_url` for the guide directory. Each `[[items]]` entry has a unique `id`, `date`, `url`, and `locales`. An empty list is written as `items = []`. |

Each banner's `target` table takes exactly one key. Use `app` for a catalog app ID,
`collection` for a collection ID, or `url` for an HTTPS page. The builder checks
IDs against the merged catalog. Supply `image = "assets/<filename>"` for
dedicated artwork under `manual/homepage/assets/`. Section 2.2 lists supported
image formats and the file size limit. An app target may omit `image` if the app
already has a published `media.hero`. The original single-banner format with
top-level `target`, `locales`, and optional `image` is also accepted.

Each banner and guide requires `locales.<locale>.title` for the repository's
default locale. Each translation includes a title and may include a `subtitle`.
Guide IDs use the same characters as app IDs. The `date` field records the day
ASMR added the guide, in `YYYY-MM-DD` format. The builder preserves the order
in the file. Both the guide's `url` and the directory's `more_url` use HTTPS.
See the [hero](../manual/homepage/hero.toml) and [guide list](../manual/homepage/guides.toml)
for complete source examples.

## 6. Generated artifacts

`asmr build` generates:

```text
dist/v1/index.json
dist/v1/collections.json
dist/v1/homepage.json
dist/v1/homepage/assets/
dist/v1/apps/<id>.json
dist/v1/apps/<id>/assets/
dist/v1/manifest.json
```

Clients follow the `homepage` path in `index.json` to `homepage.json` from
the same build. The file is generated even when the homepage has no content:

```json
{"schema_version": 1, "hero": null, "banners": [], "essentials": null, "guides": {"items": []}}
```

`banners` preserves the order in `hero.toml`. Each item contains `target`,
`locales`, and an `image` path relative to `dist/v1/`. The legacy `hero` field
contains the first banner, or `null` when the array is empty. Dedicated
artwork uses `homepage/assets/…`.
An app's existing hero keeps its `apps/<id>/assets/…` path. The `essentials`
value is the collection ID to look up in `collections.json`, or `null` for a
hidden or absent collection. Guide entries retain their source fields and order,
with dates serialized as strings. The optional directory link is emitted as
`guides.more_url`. The manifest includes the homepage JSON and published images.

`manifest.json` records the automatically computed `catalog_revision`, minimum
client version, source Git commit, generation timestamp, and SHA-256 digest and
byte size for every generated file. Generated artifacts must not be edited by
hand or treated as source metadata.

Production publication additionally requires a fixed-public-key signature over
the manifest. Signing and stable publication are outside the current
validation CI.

