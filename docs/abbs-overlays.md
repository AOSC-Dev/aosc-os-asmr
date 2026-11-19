# ABBS defaults and handwritten overrides

ASMR generates a default catalog from ABBS and merges fields supplied in
`manual/apps/<id>/app.toml`. Maintainers can supply only the description or media they
want to change. Omitted fields keep their generated values.

| Inputs | Result |
| --- | --- |
| ABBS package without handwritten metadata | Generated catalog entry |
| ABBS package with handwritten metadata | Supplied fields override defaults |
| Missing ABBS package with `external = true` | Validated external entry |
| Missing ABBS package without the external marker | Validation error; check package names and extraction diagnostics |

All authoritative handwritten inputs live under `manual/`. External apps and
repository-package overrides both use `manual/apps/<id>/app.toml`. CI obtains
generated inputs from ABBS `stable` and uploads the result as an artifact. Local builds write JSON and copied media to
the Git-ignored `dist/v1/` tree. Clients query the package manager for installed state,
candidate versions, and operation results.

`--root` selects the repository root; `--root examples` reads `examples/manual/`.
Inside that root, `--output` must point to `dist` or a descendant. A temporary
output outside the root is also supported. Clients continue to consume
`dist/v1/index.json`, `apps/<id>.json`, collections, and the manifest, so the
source layout change preserves the published layout.

## Merge rules

Tables merge recursively by field. Lists replace the entire previous list,
including `keywords = []` and `media.screenshots = []`. The merged result must
still pass type, category, media-path, and installer validation. `external` is a
boolean. A true value conflicts with an ABBS package or repository installer.

For example, `manual/apps/firefox/app.toml` can contain only:

```toml
[locales."zh-CN"]
summary = "网页浏览器"
```

An application ID can differ from its package name. Use an `aosc-repository`
installer's `package.names` to bind those identities. The `installers` list is
replaced as a whole, so supplied installers must be complete. External entries
require `external = true` and an appropriate installation or website entry point.
The marker itself grants no automatic download or installation behavior.

## Generated facts

The extractor reads actual `PKGNAME`, `PKGDES`, and `PKGSEC` from ordinary
`autobuild/defines` and split-package `NN-name/defines`, recording recipe paths
and the ABBS commit. Literal versions and revisions from `spec` remain in the
raw package facts. A section matching a taxonomy ID supplies the default category. Other sections use `uncategorized`. Clients fall back to the default English summary when a new locale supplies just a name. Media,
long descriptions, and review information may be omitted from defaults.
Generated entries make no claims of testing or upstream support.

The current extractor supports literal assignments. Complex expressions,
architecture overrides, duplicate package names, and unreadable recipes produce
extraction diagnostics. `abbs-packages.json` retains those diagnostics; a catalog
reference to an unresolved package fails the build. Recipe versions describe the
source tree. The package manager determines published versions for an architecture.

## Build and provenance

```bash
python3 tools/asmr.py check --abbs-tree ../aosc-os-abbs
python3 tools/asmr.py build --abbs-tree ../aosc-os-abbs --output dist/v1
```

CI checks out ABBS `stable` and records its actual commit as
`manifest.abbs_source_commit`. `abbs_inventory` points to `abbs-packages.json`,
which is included in the file digest list. Application details retain raw facts
under `abbs`; handwritten display fields cannot overwrite that provenance.
The catalog revision includes the ABBS input. Pushes, pull requests, manual runs,
and scheduled CI runs produce artifacts. Production signing and publishing need
separate configuration.

## Official references

- [Package maintenance basics](https://wiki.aosc.io/developer/packaging/basics/)
- [Package styling manual](https://wiki.aosc.io/developer/packaging/package-styling-manual/)
- [APML](https://wiki.aosc.io/developer/automation/apml/)
- [FAIL_ARCH](https://wiki.aosc.io/zh/developer/packaging/fail-arch/)
