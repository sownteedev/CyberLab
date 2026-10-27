# Offline Lab Packages

CyberLab supports a bounded `.cyberlab` package for moving one declarative Lab
between isolated VM installations.  The package is a deterministic ZIP archive
with this format:

```text
manifest.json
lab.yaml
assets/...
```

`manifest.json` records the format, Lab identity, approved image references,
asset sizes and SHA-256 digests, and the content digest used by the authoring
review flow.  The archive contains declarative definitions and authored initial
asset files only.  The package format does not bundle Docker images, Session
checkpoints, live state, host mounts or executable build/grading scripts.  Asset
contents are authored file bytes subject to bounded size, count and path
validation; images must already be preloaded and approved by daemon policy on
the destination VM.

The package is limited to a 64 KiB definition, 1 MiB per asset, 2 MiB of
uncompressed definition/assets, 128 paths, and a 4 MiB ZIP archive.  Imports
reject traversal paths, links/special files, duplicate or undeclared members,
encrypted entries, changed content and digest mismatches before creating a
private draft.

## CLI

```text
cyberlab export-lab demo-basic /tmp/demo-basic.cyberlab
cyberlab export-draft DRAFT_ID --revision 3 /tmp/draft.cyberlab
cyberlab import-lab /tmp/demo-basic.cyberlab --as copied-basic --title "Copied basic"
cyberlab draft check IMPORTED_DRAFT_ID --revision 1
cyberlab draft publish IMPORTED_DRAFT_ID --revision 1 --digest REVIEWED_DIGEST
```

Export destinations must not already exist.  `import-lab` never writes the
production catalog; it creates a private draft owned by the calling Unix UID.
The imported Lab must be validated and reviewed through the normal authoring
workflow before publication.  A target ID or title can be supplied to avoid an
identity collision, but publication still refuses to overwrite an installed
Lab.

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
