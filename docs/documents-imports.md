# CLI Documents and Session Imports (0.7.0)

## Scope and Status

This increment adds packaged Markdown documentation and single-file import to
the existing CLI → System D-Bus → daemon → engine → Docker architecture.
The same typed API can later serve Quickshell, but no UI, renderer, REST API,
file server, agent, assessment, or arbitrary filesystem browser is added.

The user supplied a real 0.6.0 client screenshot confirming Alice's UID/GID,
hostname, home and initial files. The new docs/import behavior has automated
tests and a MemoryRuntime smoke test, but real Docker transfer and acceptance
must still pass the administrator-run 0.7.0 verifier. Coding does not install
services, change system configuration, or operate live Sessions.

## Packaged Documentation

A Lab may declare one Markdown document in its v1 definition:

```yaml
documentation: assets/docs/README.md
```

The loader snapshots a regular UTF-8 file, at most 64 KiB, without NUL bytes.
It reuses the safe asset reader: no symlinks, file hardlinks, devices, FIFOs,
traversal, or filesystem crossings, with trusted root ownership in production.
The document has its own 64 KiB limit, separate from node initial-file quotas.
Structural validation does not read it; runtime policy requires the snapshot.
Documentation is optional, so old Labs remain compatible.

```sh
cyberlab docs demo-workspace
cyberlab docs demo-workspace --json
cyberlab docs SESSION_ID --session
```

The first command prints Markdown as readable text, not terminal-rendered HTML.
Terminal control characters are escaped except newline/tab; nothing in the
document is executed or automatically opened. JSON returns title, Lab ID,
version, format, and exact content for future clients. Those clients must treat
Markdown as untrusted text and must not enable scripts or automatic external
resource loading. PDF support is deferred.

Lab docs reflect the current installed package. Session docs use the immutable
snapshot captured at start, remain unchanged across reset, and require Session
ownership (or administrator access). A Lab without docs returns `NotFound`.
The catalog exposes only `has_documentation`, not asset paths or content.

## Import into a Running Session

```sh
cyberlab import-file SESSION_ID client ./hello.txt
cyberlab import-file SESSION_ID client './local name.bin' --name data.bin
cyberlab imports SESSION_ID
```

The CLI reads the file as the invoking Unix account before sending bytes over
D-Bus. The daemon never receives or opens the user's host source path. Import
requires a running owned Session and a declared node. The optional `--name`
is a safe basename, not a container destination: 1–64 ASCII letters, digits,
underscores, periods, or hyphens, starting with a letter, digit, or underscore.

The daemon assigns a fresh ID and creates a new file such as:

```text
/home/alice/cyberlab-import-<32-hex-id>-data.bin
```

For legacy nodes, the prefix is `/tmp/cyberlab-import-`. These are flat files
under the fixed writable home, deliberately not arbitrary paths into initial
data, image files, or hidden shell configuration. Repeated imports of the same
name create different destinations; existing entries are never overwritten.
No directory import, archive extraction, export/download, or overwrite switch
is implemented yet. An imported archive is only inert file data.

The receipt includes `id`, `node`, `name`, `path`, `size`, `sha256`, `state`, and
`error`. Only `COMPLETE` means the transfer and integrity check succeeded.
The CLI exits nonzero for `FAILED`; use `imports` after a timeout/disconnect
before retrying, because the operation may still complete. History is a bounded
record of transfer results, not a live filesystem listing: edits/deletes made
later in the shell do not update it.

### Limits and Security

- One regular file per call, at most 256 KiB; binary and empty files supported.
- At most 32 import attempts and 4 MiB declared bytes per Session, shared across
  nodes. Failed attempts also consume quota, preventing unbounded history and
  repeated failed writes. Reset/stop releases quota after resource removal.
- The engine serializes imports with reset/stop under the lifecycle lock.
  An import cannot write into a replacement container after a concurrent reset.
- A fixed non-root exec receives bytes through stdin, not shell command text.
  It creates a private mode-0600 file with shell noclobber, verifies the opened
  descriptor is a regular file at the assigned path, then checks size and
  SHA-256. The path and checksum are generated/validated by the engine.
- No root exec, host mounts, Docker socket, new capabilities, or external
  network path is introduced. The approved image must supply `/bin/sh`,
  `/bin/timeout`, `/bin/readlink`, `/bin/cat`, `/bin/wc`, `/bin/sha256sum`, and
  Linux `/proc/self/fd`. The existing BusyBox-based samples are the real-test
  targets. Other images need separate administrator review.
- Transfers have bounded socket/poll timeouts and a 15-second in-container
  timeout. Errors are sanitized, receipts retain failure status, and transport
  wrappers are closed in the tested HTTP-response-before-stream order.
- A failed/interrupted transfer can leave a partial file until reset/stop.
  Import is not atomic publication and does not promise immutability against
  another process running as the same container user. The writable tmpfs and
  existing CPU/memory/PID limits still bound the environment.
- Import never changes the Lab template or another Session. Reset restores the
  original template and clears all imported files/history; stop removes them.
  Do not import secrets or personal data into untrusted lab environments.

## D-Bus Additions

Capabilities: `documentation`, `import-file`. Existing service/interface remain
`org.ptit.CyberLab1` and the production transport remains System D-Bus.

| Method | Input | Output |
| --- | --- | --- |
| GetLabDocumentation | `s` Lab ID | `a{sv}` document |
| GetSessionDocumentation | `s` Session ID | `a{sv}` captured document |
| ImportFile | `sssay` Session ID, node ID, basename, bytes | `a{sv}` receipt |
| ListImports | `s` Session ID | `aa{sv}` receipts |

Every method uses actual D-Bus Unix credentials and the existing UID allowlist.
The daemon rejects oversized payloads before scheduling engine work. Receipt
`size` is an unsigned integer; other fields are strings. Import state/error is
independent of Session state: one failed copy does not terminate the whole lab.
MemoryRuntime stores byte snapshots in memory only; it never launches a shell
or contacts Docker in private-session-bus tests.

## Upgrade the Existing 0.6.0 VM

Developer-side build/check, without sudo:

```sh
cd /home/student/CyberLab
.venv/bin/python -m pytest -q
.venv/bin/python tools/deploy_mvp.py build dist/mvp-workspace-0.7.0
.venv/bin/python tools/deploy_mvp.py check dist/mvp-workspace-0.7.0
```

If already built, run only `check`. Use the new bundle: older bundles do not
include `demo-workspace` or its documentation. Existing Labs are not modified.

**Save needed work first. Stopping the daemon terminates every current Session
and discards temporary data.** Run this administrator action in the VM:

```sh
sudo systemctl disable --now cyberlabd.service &&
sudo /usr/bin/python3 -I tools/deploy_mvp.py repair dist/mvp-workspace-0.7.0 --uid "$(id -u)" --install-demo-workspace
```

The new opt-in installs only the reviewed `demo-workspace` sample, reusing the
already installed/allowlisted `cyberlab/demo-users:0.6.0` image. It neither builds
nor pulls images and does not edit the config/service/D-Bus policy. Customized
sample files are refused. A VM without the user-image setup requires the
separately reviewed `--install-demo-users` option from `node-environments.md`.

The administrator verifier checks docs, two 256 KiB binary imports with exact
hash/owner/mode/size inside a real node, distinct destinations, isolation,
reset, captured documentation, unchanged host sources and resource cleanup.
If verification fails, retain output/staging files for review; do not blindly
rerun or delete resources. No automatic rollback is performed.

## Manual Acceptance

After `DONE`, run on the host as the student:

```sh
cyberlab docs demo-workspace
cyberlab start demo-workspace
```

Record the Session ID. In the host terminal, create a disposable source:

```sh
testdir=$(mktemp -d)
printf 'hello from the VM\n' > "$testdir/hello.txt"
cyberlab import-file SESSION_ID client "$testdir/hello.txt"
cyberlab imports SESSION_ID
```

Replace `SESSION_ID` with the actual ID. In the client node terminal, run `cat`
and `ls -l` on the exact `path` returned in the receipt: expect the original
text, owner Alice, and mode `-rw-------`. No command requires student Docker
access. Reset from the host, reattach the client, and confirm the imported
path is gone while `~/lab/exercises/message.txt` remains `alice-original`:

```sh
cyberlab reset SESSION_ID
cyberlab imports SESSION_ID
cyberlab docs SESSION_ID --session
cyberlab terminal SESSION_ID client
```

The import list is now empty; Session documentation is unchanged. Reset does
not reopen windows automatically. Exit the node and use `cyberlab stop
SESSION_ID` on the host when finished.
