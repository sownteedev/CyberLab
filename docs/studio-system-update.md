# Studio system updates

Implemented November 25, 2026. Source changes are not a deployment or publication
to GitHub. Bootstrap this feature with the checkout's `bash install.sh --update`,
after saving edits, stopping Sessions and closing Studio. Do not use a remote
update to install unpublished working-tree changes.

## User flow

- The account-management card is now below Terminal in the right column. The
  main login name and sudo selection stay on the left. Narrow forms stack.
- Studio makes one read-only GitHub check seven seconds after opening. Demo and
  smoke modes do not check. There is no background installation or periodic job.
- A newly observed commit triggers one notification per user/commit and a badge
  on Settings. A failed automatic check is quiet; a manual failure opens the
  normal Vietnamese error popup.
- Settings has an Update section with the installed/remote commit and manual
  check/install buttons. Narrow settings windows use a section selector rather
  than overlapping tab labels.
- Installation requires explicit confirmation. Dirty editor/files, foreground
  work, startup and known non-stopped Sessions block handoff. The root installer
  independently checks all users/Sessions and all Studio processes as before.
- Studio calls `cyberlab update --window` with the checked commit and its PID.
  It closes only after the independent window acknowledges readiness. The
  updater waits for that exact process identity to exit; it never kills Studio.
- Download percentage uses Content-Length when supplied. Otherwise the view
  shows downloaded MB and an indeterminate bar. Build/install/verification are
  indeterminate; there is no invented overall percentage.
- Authentication uses the system polkit agent via pkexec. No password is read,
  stored or requested by Studio. Missing pkexec keeps Studio open; canceled or
  failed authentication is reported in the updater.
- Successful exit and matching installed commit are both required for success.
  Only then does the view offer Restart CyberLab. Failure exposes a bounded
  diagnostic tail and Open CyberLab; no automatic retry or data reset occurs.

## Implementation boundaries

`cyberlab update --check --json` is a read-only structured interface. Normal CLI
update still uses the existing implementation. The graphical runner calls that
same engine with a pinned commit, JSON events and graphical authentication;
it does not replace maintenance checks or add daemon/Docker APIs.

`ui/update_window.py` stages the QML resources and stdlib runner under a private
`/var/tmp/cl-updater-*` directory, then starts a detached unprivileged supervisor
with system Python. The copied QML remains available while the installed venv
is replaced. A worker lock prevents cleanup during installation/rollback, even
if its window disappears. Restart uses the installed launcher, not the snapshot.
Snapshot files are removed after the updater exits. Existing system-managed
failure/rollback backups remain under the installer's existing retention policy.

No new Studio exclusion was added to the installer guard. The updater is an
independent process/configuration, not an editable Studio instance.

## Verification

An installation with no recorded commit is unknown, not an available update or
proof of being current. Checks must not notify, badge Settings or offer the GUI
install action for this state. The CLI returns `installed: null, available: false`;
Studio also rejects update availability from older CLI responses with a null
installed commit. Explicit administrative `cyberlab update` remains available.
This does not change or invent the installation receipt for local builds.

- `tools/check_update_ui.py`: 16 protocol/lifecycle/auth-command tests, isolated
  fixtures. Includes unknown receipts, offline checks, pinned commits, truncated
  downloads, real versus unknown percentage, cancellation, receipt mismatch,
  restart failure and preservation of the Studio process guard.
- `tools/check_update_window.py`: native offscreen Quickshell with a fake engine;
  checks NDJSON progress, process exit, deduplicated notifications, actual CLI
  process parsing, quiet automatic errors, manual errors, supervisor cleanup and
  the actual staged-window handshake before a disposable simulated Studio exits.
- QML update suite: 16 tests; checks unknown/current version states, controls, progress, failure and responsive light/dark
  layouts; screenshots: `/tmp/cyberlab-update-ui`.
- Existing regressions: account UI 27; editor UI 152; navigation 26; dialogs 39;
  system updater 19; guarded runtime updater 31; password pipeline 13; QML manifest 1 passed.
- A built wheel contains the helper and new QML; full packaged Studio compiles
  under native Quickshell offscreen.

Known verification limits (not introduced/fixed by this change):

- No root install or live authentication was executed: this process has
  `NoNewPrivs=1`. Real GitHub download/install/restart acceptance remains to run
  after publishing and installing this version. No production data was touched.
- Native Quickshell reports that it was built against Qt 6.12.0 while this host
  has Qt 6.12.1. The offscreen probes load, but this is not proof of live stability;
  no OS packages were upgraded or rebuilt.
- The editor runner emits the previously recognized WorkerScript null-connect
  warning; its 152 assertions pass with `--allow-worker-init-warning`.
- The unrelated isolated-desktop suite has six failures, reproduced unchanged
  from a clean `git archive HEAD`: `test_install_then_open_only_on_success`
  (success/failed), `test_missing_viewer_does_not_install_guest_packages`,
  `test_missing_wayland_display_does_not_install_guest_packages`,
  `test_ready_machine_does_not_reinstall`, and
  `test_requires_confirmation_before_installing`. They are not counted as passing.
