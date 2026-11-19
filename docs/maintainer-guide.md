# ASMR Maintainer Guide

**English** | [简体中文](maintainer-guide.zh-CN.md)

With an ABBS input, handwritten files are partial overlays. The complete field constraints below apply after merging; see [ABBS defaults and overrides](abbs-overlays.md) for optional defaults. External entries require `external = true`.

This guide is for maintainers who add software to AOSKA search, application
detail pages, and curated collections.

Authoritative handwritten inputs live under `manual/`, with examples under
`examples/manual/`. `--root` still selects the repository root or `examples`.
CI reads ABBS `stable` and writes merged JSON and media under ignored `dist/v1/`.
Runtime state comes from the package manager. See the [build workflow](abbs-overlays.md)
for input responsibilities and output restrictions.

## 1. Core rules

1. Maintain one `manual/apps/<id>/app.toml` source file for each application.
2. Never maintain search indexes, application detail JSON, or duplicated
   collection copy and icons by hand.
3. Keep the application ID separate from DEB package names and connect them
   through `installers`.
4. Do not store installed state, current versions, or upgrade state in ASMR.
5. Do not store scripts, cookies, temporary download URLs, or scraping rules in
   metadata.
6. Use `unknown` for uncertain disclosures. Unknown is not the same as false.

## 2. Prepare the environment

The maintainer tool depends only on Python 3.11 and the standard library:

```bash
python3 --version
python3 tools/asmr.py check --abbs-tree ../aosc-os-abbs
```

An editor with Taplo or Even Better TOML support is recommended. `taplo.toml`
and the files under `schemas/` provide completion and enum hints.

## 3. Add an application

### 3.1 Application from the AOSC repository

```bash
python3 tools/asmr.py new firefox \
  --kind aosc-repository \
  --category office
```

### 3.2 DEB that requires a user-initiated download

```bash
python3 tools/asmr.py new vendor-app \
  --kind browser-assisted-deb \
  --category communication
```

The tool creates:

```text
manual/apps/<id>/app.toml
manual/apps/<id>/description.zh-CN.md
manual/apps/<id>/assets/icon.svg
manual/apps/<id>/assets/hero.svg
```

Replace every `TODO:` value before committing. CI rejects incomplete
scaffolds.

## 4. Write the metadata

### Identity and search

- Do not change an `id` after publication.
- Names, aliases, and keywords should include the Chinese and English forms
  that users are likely to search for.
- `summary` should be a single sentence and must not include installation
  state or a version number.
- An application may belong to multiple categories.

### Media

- Use a square SVG, PNG, or WebP icon.
- A hero image near 1280×480 is recommended. Set a focal point suitable for
  responsive cropping.
- Screenshots should show the real application interface.
- Verify copyright and redistribution permission for every media asset.
- Do not use a download page screenshot as an application screenshot.

### Publisher and disclosures

- `relationship = "upstream"` means the source is provided by the software
  publisher.
- An AOSC package does not automatically imply official upstream support.
- `availability = "verified"` requires actual test evidence.
- Use `unknown` when telemetry or service availability is uncertain.
- Put regional restrictions and compatibility-layer requirements in `notes`.

## 5. Choose an installer

### Package available from the AOSC repository

Use `aosc-repository`. Package names must be stable identifiers recognized by
omactl and oma:

```toml
[installers.package]
backend = "omactl"
names = ["firefox"]
```

### Upstream permits direct downloads

Use `direct-deb`. Confirm that:

- upstream permits automated client access;
- the URL is not temporary or single-use;
- every download origin is allow-listed;
- package-name and architecture constraints are correct.

### The user must click on the upstream website

Use `browser-assisted-deb`. Metadata describes only:

- the official landing page;
- the HTTPS origins from which a download may be accepted;
- expected DEB package names and architectures;
- redistribution, automation, and license-acceptance policy.

Do not add CSS selectors or attempt to bypass authentication, captchas, license
confirmation, or upstream access controls. AOSKA should receive the file
created by the browser instead of recording a temporary URL and scraping it
again.

### AOSKA cannot install the software

Use `external-link`. The UI may only offer actions such as “Visit website” or
“Open download page.”

## 6. Add the application to a collection

Edit `manual/collections/<collection>.toml` and add only the application ID:

```toml
apps = ["firefox", "vendor-app"]
```

Do not duplicate names, summaries, or images. The generated search index
already contains every `listed + active` application; there is no handwritten
`index.toml`.

### Edit the homepage

| Change | Where to edit |
| --- | --- |
| Feature an app, a collection, or a web page | Set the destination and localized headline in [hero.toml](../manual/homepage/hero.toml). Place dedicated artwork in `manual/homepage/assets/`, or omit `image` to use the target app's existing hero. |
| Change Essentials recommendations | Edit the `apps` list in [essentials.toml](../manual/collections/essentials.toml). The homepage follows its order. |
| Add or reorder a tip | Edit the `[[items]]` entries in [guides.toml](../manual/homepage/guides.toml). Set `more_url` at the top of the file to link to a guide directory. |

Use the repository's default language for every headline and add translations in
the same file. Application badges such as verified availability, compatibility
layer use and telemetry belong in the application's `disclosures` table.
See the [homepage field definitions](schema-v1.md#5-homepage).

## 7. Run local checks

Before submitting:

```bash
make check ABBS_TREE=../aosc-os-abbs
make check-examples
make test
```

To inspect generated output:

```bash
python3 tools/asmr.py build --abbs-tree ../aosc-os-abbs
python3 -m json.tool dist/v1/homepage.json
```

The production Essentials list references ABBS packages, so use the same
`--abbs-tree` input for production checks and builds. To preview the sample
homepage offline, run `python3 tools/asmr.py build --root examples` and open
`examples/dist/v1/homepage.json`.

Common validation failures include:

- the application ID differs from the directory name;
- an undefined category is used;
- an image is missing or escapes the application directory;
- the default locale lacks a name, summary, or screenshot alternative text;
- a collection references an unknown application;
- a browser-assisted installer has no allowed download origin;
- metadata contains a script or an unresolved `TODO:`.

## 8. Pull request review

The pull request description should provide:

- the official website and publisher;
- the reason for the selected installer type;
- AOSC package names or external DEB control information;
- evidence for availability, compatibility, and service restrictions;
- media sources and licensing;
- any change to download or installation policy.

Treat changes to the following fields as supply-chain-sensitive:

- `installers`
- `publisher.relationship`
- navigation and download origins
- `expected_package_names`
- `processor` or `capability`

Passing CI proves only that the metadata is structurally valid and satisfies
static safety constraints. It does not establish that the software is
trustworthy and does not replace human review.

## 9. Periodic maintenance

- Update metadata immediately when a source or download origin changes.
- Update the application and disclosure `reviewed_at` values after review.
- Use `lifecycle = "blocked"` when an application is no longer usable.
- Use `visibility = "unlisted"` to remove it temporarily from search.
- Never reuse a published ID for unrelated software.
- For external DEBs, recheck package names, architectures, download policy, and
  service availability on every upstream change.

