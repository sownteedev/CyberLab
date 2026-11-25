# Offline Lab Packages

CyberLab supports a bounded `.cyberlab` package for moving one declarative Lab
between isolated VM installations. New exports always use the deterministic
binary `cyberlab-lab/v3` format, with or without an editing password verifier.
It is not ZIP, TAR, an encrypted archive, or a ZIP wrapped in a custom header.
The importer also accepts legacy v1 and v2 ZIP packages; re-export upgrades them
to v3. `create_package(definition, assets, lab, edit_protection=None)` and
`read_package(data)` retain their signatures. The reader returns the existing
`(definition, assets, manifest)` tuple. `exchange.FORMAT` is `cyberlab-lab/v3`,
`IMPORT_FORMATS` contains v1/v2/v3, and `PROTECTED_FORMAT` remains the legacy v2
identifier, not an indication that all protected packages are v2.

## Binary v3 wire format

All integers are unsigned and big-endian. The header is exactly 49 bytes
(`struct.Struct(">8sBII32s")`):

| Offset | Bytes | Meaning |
| --- | --- | --- |
| 0 | 8 | Magic: `43 59 42 4c 41 42 0d 0a` (`CYBLAB\r\n`) |
| 8 | 1 | Version: `3` |
| 9 | 4 | Exact compressed payload length |
| 13 | 4 | Exact uncompressed JSON envelope length |
| 17 | 32 | SHA-256 of the compressed payload bytes |
| 49 | declared length | One raw DEFLATE stream, without zlib/gzip headers |

No prefix, trailer, concatenated stream, or padding is allowed outside the
DEFLATE stream. The decompressed envelope has exactly these keys:

```json
{"assets":{"assets/empty":null,"assets/readme.txt":"aGkK"},"definition":"...","manifest":{}}
```

The example abbreviates the definition and manifest. A directory is `null`, an
empty file is `""`, and all other asset values are standard padded base64 with
no whitespace and canonical padding bits. Paths remain under `assets/`; the
optional root directory `assets` is represented by `null`. Canonical JSON uses
sorted keys, ASCII escaping (`ensure_ascii=True`), compact `,`/`:` separators,
and no non-finite numbers. Duplicate keys at every depth, noncanonical JSON,
extra envelope keys, and invalid shapes are rejected.

The manifest records the format, Lab identity, approved image references,
asset sizes and SHA-256 digests, and the content digest used by the authoring
review flow. Its logical definition path remains `lab.yaml`, even though v3
does not contain archive members. The container contains declarative definitions and authored initial
asset files only.  The package format does not bundle Docker images, Session
checkpoints, live state, host mounts or executable build/grading scripts.  Asset
contents are authored file bytes subject to bounded size, count and path
validation; images must already be preloaded and approved by daemon policy on
the destination VM. Script-like assets remain inert bytes during decoding;
the codec never executes them or uses pickle/object deserialization.

The package is limited to a 64 KiB definition, 1 MiB per asset, 2 MiB of
decoded definition/assets, 128 asset paths (including implicit parent
directories), a 64 KiB manifest, and 4 MiB for the complete binary container.
The JSON envelope has a separate conservative cap to account for base64,
JSON escaping of the definition, metadata, and path names:

```text
MAX_ENVELOPE = 4 * ((MAX_PACKAGE + 2) // 3)
             + 6 * MAX_DEFINITION + MAX_MANIFEST + MAX_PATHS * 256 + 1024
```

These limits are independent: the larger envelope budget does not increase the
2 MiB decoded-content limit. Lengths and checksum are checked before inflation;
inflation produces at most the declared bounded envelope size plus one byte
for overflow detection. Completion, exact size and absence of unused input
are required. Definition bytes, decoded assets, paths and manifest digests
are then checked before the daemon processes the Lab. Legacy ZIP imports use
the same content/path limits and reject duplicate members, symlinks/special
files, encryption, unknown compression, prefixed/trailing data and bad digests.

An optional `manifest.edit_protection` contains only the existing validated
verifier: version `1`, algorithm `scrypt-131072-8-1`, a 16-byte salt and 32-byte
hash represented as lowercase hex. No plaintext password is included. v2 ZIP
requires this verifier; v1 ZIP cannot contain it; v3 supports either case.
This preserves the application's editing gate, not encryption or content
confidentiality. Checksums detect corruption, not authorship or malicious
tampering; anyone able to rewrite a package can recalculate them. Binary
encoding/base64 is not access control. The daemon's schema and policy checks
remain authoritative.

## Codec verification

Run `PYTHONDONTWRITEBYTECODE=1 /usr/lib/cyberlab/venv/bin/python tools/check_exchange_v3.py`
on the development host. The isolated suite tests an independently constructed
v3 encoder/decoder, legacy ZIP fixtures and verifier migration, malformed
headers/JSON/base64, content/path bounds, truncation, trailing data, corruption
and compressed bombs. Labtainer ZIP/TAR/TGZ and native packages are tested as
separate codecs; fixture scripts are never executed. Generic `file`, `unzip`
and `7z` inspection is useful to verify that a new export is not a standard
archive, but is not a security test.

## CLI

```text
cyberlab export-lab demo-basic /tmp/demo-basic.cyberlab
cyberlab export-draft DRAFT_ID --revision 3 /tmp/draft.cyberlab
cyberlab import-lab /tmp/demo-basic.cyberlab --as copied-basic --title "Copied basic"
```

Export destinations must not already exist. Native `import-lab` validates and
installs the Lab through the daemon's authoring/publication workflow, preserving
any editing verifier. A target ID or title can be supplied to avoid an identity
collision; import refuses to overwrite an installed Lab. The codec itself only
returns validated package data and does not write to the catalog.

The same operations are exposed as `ExportLabPackage`, `ExportDraftPackage`
and `ImportLabPackage` on System D-Bus.  Studio and CLI therefore share one
authoritative path and never access the catalog or Docker directly.

## Labtainer conversion

`cyberlab import-labtainer SOURCE --as new-id --title "New Lab"` accepts a
local Lab directory or ZIP, TAR, TAR.GZ/TGZ archive. The CLI serializes bounded
files, never hands the daemon a host path. `ImportLabtainer` uses the same
authoring authorization and private-draft store as native package imports.
Studio's package picker uses that API, checks the daemon capability and preserves
unsaved editor work. It does not execute source scripts, build images or publish
the imported Lab.

### Compatibility inspection (October 30, 2026)

`cyberlab inspect-labtainer SOURCE` returns a bounded JSON compatibility report
through `InspectLabtainer` on the same daemon API. It accepts the same optional
`--as` and `--title` as import, but never creates a draft, builds an image or
starts a Session. Exit status zero means the inspection completed; check
`can_import` in the JSON, not the exit status, to determine convertibility.
`runtime_ready` is always false: conversion is not runtime acceptance.

Studio checks this report before importing Labtainer packages when the daemon
advertises `labtainer-inspect`. Blockers appear in a scrollable dialog with
Vietnamese explanations and bounded source locations, not a transient generic
`Invalid request values` toast. Native `.cyberlab` imports are unchanged. Older
daemons retain their strict import path. If editing changes during inspection,
Studio cancels the pending import rather than replacing editor work.

The preflight groups X11, system provisioning, lifecycle hooks, instructor
scripts and explicit privileged-container requests. Dockerfiles remain a
runtime-review warning, not build permission. Known blockers stop conversion
before creating any draft; the report is not an exhaustive audit of all source
semantics. When preflight passes, the full existing converter, schema and package
limits are checked as well. Public reports never include script bodies or
directive values. Unexpected backend errors are still redacted.

X11 is a request for graphical applications, not another name for an Ubuntu
container or a requirement of every Labtainer exercise. This change does NOT
implement X11 forwarding, change Docker isolation, share the host display, or
silently ignore `X11 YES`. Removing that flag does not convert system setup or
grading hooks. Full graphical compatibility still requires a reviewed isolated
display design and runtime implementation.

The inspected `users` archive requests X11 and includes `_system`, `_bin`,
instructor scripts and a Dockerfile. It remains blocked, not runnable under
CyberLab. `shared` is its declared container name, not an implicit directory
whose contents should be copied to every machine. A future compatible version
needs reviewed provisioning and assessment semantics in addition to deciding
whether its actual exercise needs GUI applications. No user archive or catalog
was modified for this check.

`config/keywords.txt` is now accepted as bounded UTF-8 metadata and preserved
separately at `assets/docs/labtainer-keywords.txt`. It does not change execution,
create tags automatically, or overwrite `docs/keywords.txt`. Ordinary files
under a declared container directory still map only to that container's home.

Isolated regression commands available in this checkout:

```sh
/usr/lib/cyberlab/venv/bin/python -B tools/check_labtainer_compatibility.py
python3 -B tools/check_notifications.py --suite labtainer
```

The backend check uses a private D-Bus daemon, MemoryRuntime and temporary
catalog/draft state. The UI check runs offscreen with temporary preferences and
tracked process cleanup. Neither test uses the production catalog. Source tests
do not imply that the installed app has been updated; guarded deployment still
requires every allowed user's Sessions to be STOPPED and editor work preserved.

The archive boundary permits at most 32 MiB compressed input, 32 MiB file
content and 512 entries; the decompressed TAR stream, including metadata and
padding, is additionally bounded. Paths, links, special files, duplicate entries,
file/directory conflicts and truncated gzip streams are rejected. Config text is
bounded UTF-8. Exactly one `config/start.config` identifies the source root;
unrelated files outside that root are rejected. Empty home directories survive
both archive and folder input. The resulting draft still obeys CyberLab's stricter
64 KiB definition, 1 MiB/asset, 2 MiB/package and 128-path limits, and its runtime
seed retains the existing 1 MiB/128-entry limit.

### Supported conversion and explicit review

- Container/network identities are normalized with collision detection and a
  retained source-to-target mapping. Undefined references never become a
  reference to the first container/result. Source directory names, rather than
  normalized IDs, locate each container's home files.
- Default terminals open for every container; `TERMINALS 0` suppresses automatic
  opening without removing manual attachment. Counts 1..4 and terminal grouping
  are retained. `TERMINALS -1` cannot be represented yet and is rejected.
- Private static IPv4 subnets, gateway reservation and node addresses retain
  normal validation. `AUTO` is accepted only on an automatic network without an
  explicit subnet. No address is silently assigned to satisfy an incompatible
  configuration. `NAME_SERVER` and explicit `ADD-HOST host:IPv4` retain the
  current topology/policy validation; network-wide ADD-HOST expansion is pending.
- CHECKWORK/COLLECT_DOCS, master seed and deprecated transfer/grade metadata are
  carried explicitly. A source `CHECKWORK no` is never overwritten with `true`.
- Relative home paths stay relative; `/home/<configured-user>/file` becomes
  `file`, not `home/<user>/file`. Other absolute paths, traversal, unsupported
  filenames and system/hook directories fail rather than being sanitized or
  copied into a different location. One directory mapping seeds home contents
  directly, preserving nested and empty directories.
- Decimal random replacement (step 1), unique-random, full-length MD5 creation
  and replacement support exact source IDs and multiple targets. There are no
  invented public parameter fields or fallback bounds. Pure seed expansion
  verifies files/tokens before any draft is stored. CyberLab generates new
  instance seeds; source-run random values are not reproduced. Network targets,
  clone replacement, hexadecimal output and other step/truncation semantics
  remain explicit gaps.
- Whole-workspace-file CONTAINS/FILE_REGEX and boolean snapshot goals are
  converted. Event/archive sources, extraction-only results, temporal/count
  goals and matchany/matchlast/matchacross are rejected, not replaced with file
  existence or snapshot comparisons. These require the remaining evidence-model
  work in `docs/results-goals-parity.md`.
- All immediate `config/*.quiz` files are parsed into named groups, preserving
  multiline records, Preface, TrueFalse, right/wrong feedback and earlier-question
  prerequisites. Bounds are eight groups, 64 total items and 64 KiB combined
  input. CHOICE/MC is a compatibility extension, not an upstream-format claim.
  Filenames do not imply preparation gates. The parser was also checked against
  the user-supplied upstream iptables2, dns, dmz-lab and db-access Quiz examples.

**Imports are editable drafts, not runnable substitutes for Labtainer images.**
No BusyBox image or sleep command is silently injected. Image and startup argv
are intentionally absent until the author selects them; UID/GID 1000 and Bash
are clearly identified as editable suggestions, not discovered account facts.
Runtime-policy validation blocks publication until the runtime fields are
configured. A successful structural/policy check does not prove that an account,
shell or service exists inside an image: use the existing runtime-readiness
workflow and real-Docker acceptance.

Each converted draft includes `assets/docs/labtainer-import.json`, with source
digest, identity mappings, required runtime review and unbuilt Dockerfile source
digests. The API returns the same `import_report`; Studio explains the next
editing step. Dockerfiles are not executed and do not supply an image. Source
`docs/` is retained under `assets/docs/source/`; authors choose/adapt the manual.
Other unrecognized files/directives fail with a source location before any draft
is created. The native exchange format can carry an unfinished imported draft;
its image manifest lists only declared image references, never invented values.

This is not general Labtainer compatibility. The full remaining inventory in
`docs/labedit-parity.md` still applies. Tests use temporary catalogs, the actual
CLI/private D-Bus with the memory runtime, and offscreen Studio; this conversion
work has not updated the installed daemon or modified the production catalog.
