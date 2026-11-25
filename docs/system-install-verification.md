# System install / v3 verification - 2026-11-25

## Scope and decisions

- Implemented in the existing checkout; no commit, push, system installation,
  service restart, real-lab mutation or catalog migration was performed.
- Kept Python/QML and the existing CLI -> daemon -> engine boundary. System
  maintenance is an explicit administrative path, not a Docker API in the CLI.
- Native CyberLab packages now install directly into the library, protected or
  not. Labtainer conversion still creates a draft.
- Added an exclusive updater/shared daemon request lease after review exposed
  an unsaved-Session race between polling and daemon shutdown. An active legacy
  daemon without that capability fails closed. Explicit `--update --offline`
  is an administrator-only first-migration path, not automatic lab shutdown.
- Signal recovery now ignores repeat cancellation while restoring or waiting
  for the installer. Root-started source snapshots are read-only to the selected
  desktop group for probes; build HOME is applied after dropping privileges.
- No claim of strong encryption, tamper-proof grading, live GUI correctness or
  clean-machine deployment follows from these tests.

## Executed checks

Python checks used `/usr/lib/cyberlab/venv/bin/python` as an interpreter only;
the production venv was not modified. All data came from temporary fixtures.

| Script | Passing checks |
| --- | ---: |
| `check_system_update.py` | 19 |
| `check_upgrade_runtime.py` | 31 |
| `check_maintenance.py` | 4 |
| `check_exchange_v3.py` | 12 |
| `check_private_catalog.py` | 11 |
| `check_edit_protection.py` | 10 |
| `check_difficulty.py` | 5 |
| `check_topics.py` | 7 |
| `check_editing_drafts.py` | 16 |
| `check_edit_access_cli.py` | 3 |
| `check_qml_manifest.py` | 1 |
| `check_x11_safety.py` | 12 |
| `check_auto_software.py` | 38 |
| **Python total** | **169** |
| `check_notifications.py --suite library` (offscreen) | 62 |
| `check_package_import_ui.py` (packaged QML, offscreen) | 8 |

The private-bus workflow exercises real D-Bus messages with an in-memory
runtime: import without a password, edit/clone rejected, locked re-export,
maintenance refusing StartLab, then start/stop after releasing the lease. It is
not a real-Docker or two-machine acceptance run.
Background software workers/image leases are also advertised as maintenance-busy;
the updater refuses to stop the daemon while preparation is still active.

The codec tests include `file`, `unzip` and `7z` on this Linux host: v3 is reported
as data and archive extraction is rejected. This says nothing about custom
decoders or other archive products/platforms. The binary codec is documented.

A disposable system-temporary build produced the wheel and dependency
wheelhouse as the current non-root account. Installation into a separate temp
venv succeeded with `--no-index`, `pip check` passed, the installed new modules
and `cyberlab update --help` loaded, native Quickshell compiled the packaged
Studio QML, and all 8 package-import UI checks passed against that wheel.
Temporary source, build and test-runtime directories were removed afterward.

`bash -n install.sh tools/install/system.sh` and `git diff --check` passed.

## Not executed / blocked acceptance

| Area | Status / reason |
| --- | --- |
| Literal public curl installation | Not published to GitHub; cannot validate local edits through the public URL |
| Fresh supported VM without Git | No disposable clean VM prepared in this task |
| Privileged install/update/rollback | Not executed; current process has `NoNewPrivs: 1`; no password requested |
| Actual sudo cancellation / root-started probe | Command/permission and signal tests only; requires privileged VM acceptance |
| Ordinary account denied catalog reads | Mode/owner logic and fixture tests only; separate Unix-account acceptance outstanding |
| Two-machine Quiz/Checkwork/GUI workflow | Codec/authoring/private-bus checks only; real Docker, network and display acceptance outstanding |

Per-suite logs were written to `/tmp/cyberlab-check_*.log`; the packaged-artifact
log is `/tmp/cyberlab-artifact-verification.log`. Library UI evidence is under
`/tmp/cyberlab-plan-library-check`. These are local transient diagnostics, not
installation receipts or a published release.

See `system-install-update.md` for installation, first-migration precautions,
backup policy, failure handling and the remaining VM acceptance checklist.
