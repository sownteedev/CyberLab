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

## Account editor UX revision, November 25, 2026

- Replace the disclosure checkbox with an account/group count and a Manage
  button. Keep main login/sudo controls in place; align Terminal to the top.
- A bounded MD3-style dialog separates Accounts and Groups, keeps add controls
  and tabs outside the scrolling list, and expands one account at a time.
- Keep IDs visible in account details instead of displaying provisioning limits
  in the default form. Use explicit empty states and show limits only when full.
- Enter adds an entry; Escape closes the dialog without discarding draft edits.
  Deletion requires confirmation and still respects referenced users/groups.
  Node/draft changes close the dialog and clear unsubmitted names/secrets.
- No schema, runtime account setup or host account changes in this revision.
- Account UI: 24 passed; editor UI: 152 passed; password pipeline: 13 passed;
  account model checks and QML manifest passed. Checks use disposable fixtures.
- Reviewed offscreen light/dark, 360px-wide, 360x520, long-list and nested-dialog
  captures in `/tmp/cyberlab-accounts-redesign` and full editor captures in
  `/tmp/cyberlab-accounts-editor`. Native Quickshell compiled the full Studio
  from a newly built wheel, including the new dialog and both icons.
- Broader machine setup suite: 13 passed, one pre-existing digest expectation
  failed (`test_old_lab_digest_stays_compatible`). The expected document retains
  `metadata.difficulty: null`, whereas the existing compatibility hash omits it;
  dropping that unset field reproduces the actual hash. Neither that backend
  implementation nor its test was changed by this UI work.
- System deployment remains blocked by `NoNewPrivs=1`; no service was stopped,
  no production draft/catalog was modified, and real Docker setup was not run.

### Main-account password actions in Manage

- Move Set password / Lock password into the Accounts tab's main-account card;
  keep the main login name and sudo selector on the machine form. Tab counts
  include the main account; supplementary-account controls remain unchanged.
- Preserve the existing password API, dirty-state guard and secret clearing.
  Closing Manage, changing node or switching to Groups dismisses the nested
  password dialog. Escape dismisses only the top dialog.
- Account UI: 27 passed; editor UI: 152 passed; password pipeline: 13 passed; account model and QML
  manifest checks passed. A newly built wheel loads full Studio QML offscreen.
- Reviewed narrow light and nested dark password screenshots under
  `/tmp/cyberlab-account-manager-password`. Installed runtime remains unchanged;
  this process still has `NoNewPrivs=1`.
