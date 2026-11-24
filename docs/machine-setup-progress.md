# Linux machine setup: implementation ledger

Approved scope: configure Ubuntu accounts, groups, lab passwords, Home/System
author assets and Unix permissions in Studio. Keep QML -> CLI -> daemon -> engine.
No arbitrary root scripts, host changes, new image variants or production fixtures.

## Tasks

- [x] Schema, immutable setup models, validation and asset snapshots.
- [x] Trusted container setup before startup; resume skips setup; reset reapplies.
- [x] Revision-guarded password operation and accounts UI.
- [x] Home/System author tree and properties popup.
- [x] Regression, isolated UI workflow, package and handoff.
- [ ] Administrator-run real Docker acceptance.

## Rulings and environment

- Existing checkout contains 318 modified/untracked paths. Work incrementally in
  place, preserve prior work; do not commit or create branches automatically.
- Parallel work uses disjoint runtime, account/API and file-editor write scopes.
- Optional `node.setup` is versioned by capability `machine-setup-v1`.
- User/group IDs are stored explicitly, 3000..59999; runtime rejects collisions.
- Passwords use the system OpenSSL SHA-512 crypt implementation, stdin only.
- Software image fingerprint excludes setup; setup runs on a fresh container.
- UID 1000, NoNewPrivs=1, Docker socket not readable at baseline. No privilege
  bypass; real Docker and installed-runtime acceptance must be reported separately.
- Preserve all existing deployment backups.

## Evidence

Implementation started November 22, 2026. Isolated acceptance is recorded below; real Docker acceptance remains explicitly unverified.

## Verification on November 22, 2026

- `check_machine_setup.py`: 14 tests passed.
- Password API: 13 tests passed; account QML: 17 passed; file editor: 18 passed.
- Studio editor: 150 passed; Home/System file suite: 39 passed; native editor/file
  smoke suites: 150/39 passed.
- Workstation regression: 33 passed; Session lifecycle: 23 passed; software: 38
  passed; draft editing: 16 passed; Labtainer compatibility: 14 passed.
- `check_machine_setup_workflow.py`: private D-Bus + real Quickshell controls created,
  saved, exported, imported and reopened a disposable draft; marker passed.
- Real Docker acceptance is blocked in this process by `NoNewPrivs: 1` and an
  unreadable Docker socket. The administrator-only script is retained at
  `tools/check_machine_setup_runtime.py`; no production catalog was used.
- Wheel built at `/tmp/cyberlab-machine-setup-wheel-laHJny/`; SHA-256 is
  `a4b58883322488a57943436ccdf3bbfb6d01a898bb7abd02ae4eb46ab12219da`.
