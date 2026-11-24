# AOSC Software Manager Metadata Repository

**English** | [简体中文](README.zh-CN.md)

ASMR uses ABBS-generated defaults with field-level handwritten overrides. Entries absent from ABBS require `external = true`. See [defaults and overrides](docs/abbs-overlays.md).

Maintainers supply TOML, Markdown, and media assets to supplement the ABBS
defaults. CI merges and validates both inputs to generate a read-only JSON catalog.

ASMR owns:

- application names, summaries, categories, search terms, and localized copy;
- icons, hero images, and screenshots;
- publisher relationships, support, availability, privacy, and compatibility
  disclosures;
- AOSC repository package bindings or external acquisition entry points;
- the homepage hero, ordered Essentials collection, and Tips & Guides links.

Aoska queries amo, oma’s D-Bus service (`io.aosc.Amo`), for package state,
installed and candidate versions, transaction plans, progress, and results.

`manual/repository.toml` contains only repository-wide compatibility policy. CI
generates the catalog index, content revision, generation timestamp, file
inventory, and digests.

Authoritative handwritten inputs live under `manual/`, with examples under
`examples/manual/`. `--root` still selects the repository root or `examples`.
Local builds write to the ignored `dist/v1/` directory. CI reads ABBS `stable`
and uploads the same layout from its temporary build directory.
Runtime state comes from the package manager. See the [build workflow](docs/abbs-overlays.md)
for input responsibilities and output restrictions.

## Catalog channels

| Channel | Base URL | Publication |
| --- | --- | --- |
| dev | `https://aosc-dev.github.io/aosc-os-asmr/v1/` | GitHub Pages serves the ABBS catalog after successful pushes, scheduled builds and manual runs on `main`. |
| stable | `https://repo.aosc.io/asmr/v1/` | Planned location on the AOSC repository. Stable publication is pending. |

For the first dev deployment, select **Settings → Pages → Build and deployment → Source → GitHub Actions** in this repository. Run the CI workflow on `main` and check `v1/index.json` on the published site. Pull requests and other branches produce test artifacts only. The example catalog stays in the regular CI artifact.

## Quick start

Python 3.11 or newer is required. The maintainer tool has no third-party Python
dependencies.

```bash
# Create an application scaffold.
python3 tools/asmr.py new example-app \
  --kind aosc-repository \
  --category utilities

# Validate all source metadata.
python3 tools/asmr.py check --abbs-tree ../aosc-os-abbs

# Build the dist/v1 JSON catalog.
python3 tools/asmr.py build --abbs-tree ../aosc-os-abbs

# Run the test suite.
python3 -m unittest discover -s tests -v
```

Equivalent Make targets are available:

```bash
make check ABBS_TREE=../aosc-os-abbs
make test
make build ABBS_TREE=../aosc-os-abbs
```

See the [maintainer guide](docs/maintainer-guide.md) for the complete workflow
and [Metadata Schema v1](docs/schema-v1.md) for the field contract.

## Repository layout

```text
manual/repository.toml          Repository compatibility policy
manual/apps/<id>/app.toml       Handwritten overrides and external apps
manual/apps/<id>/description.*.md  Localized descriptions
manual/apps/<id>/assets/        Icons, hero images, and screenshots
manual/collections/*.toml       Ordered app lists, including essentials.toml
manual/homepage/hero.toml       Homepage banners in display order
manual/homepage/assets/         Artwork for the homepage banner
manual/homepage/guides.toml     Ordered Tips & Guides links
manual/taxonomy/categories.toml Category definitions
examples/manual/               Example inputs with the same layout
schemas/                       JSON Schema files for editor support
tools/asmr.py                   The new/check/build maintainer tool
dist/v1/                       Generated JSON and copied media
```

Production metadata must not be duplicated into handwritten indexes.
`asmr build` generates `index.json`, application detail documents,
collections, `homepage.json`, assets, and the digest manifest.

