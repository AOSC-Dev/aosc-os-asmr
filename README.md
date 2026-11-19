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
- curated collections such as featured and essential applications.

ASMR does **not** own installed state, current versions, upgrade availability,
operation plans, progress, or logs. Those runtime facts come from `omactl` and
`oma`.

`repository.toml` contains only repository-wide compatibility policy. CI
generates the catalog index, content revision, generation timestamp, file
inventory, and digests.

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
apps/<id>/app.toml              Structured application metadata
apps/<id>/description.*.md      Localized long descriptions
apps/<id>/assets/               Icon, hero image, and screenshots
collections/*.toml              Curated lists of application IDs
taxonomy/categories.toml        Category definitions
schemas/                        JSON Schema files for editor support
tools/asmr.py                   The new/check/build maintainer tool
dist/v1/                        CI output; never edit by hand
```

Production metadata must not be duplicated into handwritten indexes.
`asmr build` generates `index.json`, application detail documents,
collections, assets, and the digest manifest.

