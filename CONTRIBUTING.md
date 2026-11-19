# Contributing

**English** | [简体中文](CONTRIBUTING.zh-CN.md)

ASMR uses ABBS-generated defaults with field-level handwritten overrides. Entries absent from ABBS require `external = true`. See [defaults and overrides](docs/abbs-overlays.md).

Read the [maintainer guide](docs/maintainer-guide.md) before adding or changing
application metadata.

Authoritative handwritten inputs live under `manual/`, with examples under
`examples/manual/`. `--root` still selects the repository root or `examples`.
CI reads ABBS `stable` and writes merged JSON and media under ignored `dist/v1/`.
Runtime state comes from the package manager. See the [build workflow](docs/abbs-overlays.md)
for input responsibilities and output restrictions.

Run at least the following commands before opening a pull request:

```bash
make check ABBS_TREE=../aosc-os-abbs
make check-examples
make test
```

Changes to `installers`, download origins, package names, publisher
relationships, or disclosures are supply-chain-sensitive. Explain the
verification evidence in the pull request and obtain maintainer review.

