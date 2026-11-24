# Maintained Tools

The normal entry point is `bash install.sh` at the repository root.

`bash install.sh --update` also applies the guarded updater's reviewed service
policy migration (native-X11 socket bind, private runtime directory and helper
capabilities). It preserves `PrivateTmp`, refuses custom conflicting policy,
and backs up the previous unit for rollback. It does not start a Lab or verify
native GUI on the user's display; all users' Sessions must be STOPPED first.

| File | Purpose |
| --- | --- |
| `install/packages.sh` | Native package-manager adapters for Arch, Debian/Ubuntu, Fedora and openSUSE. |
| `install/docker.sh` | Detect and preserve the existing system Docker provider; reject conflicting/shim/custom setups. |
| `install/repositories.sh` | Explicit opt-in native Quickshell sources with pinned signing-key fingerprints; never overwrite another repository configuration. |
| `install/transactions.sh` | Resolve/review dependency changes, require upgrade approval and retain transaction receipts. |
| `install/apt-transaction-guard.sh` | Reject unreviewed .deb versions immediately before dpkg installs them. |
| `install/probe.qml` | Offscreen native Qt/QML and SVG icon-decoding probe, also used by `--check`; no catalog access. |
| `runtime_admin.py` | Safe account/path checks, unprivileged builds, configuration generation and installation verification. |
| `upgrade_runtime.py` | All-users Session guard, private backup/rollback and runtime update. |
| `run_studio.sh` | Launch the source UI using the local editable venv; never sudo. |
| `run_studio.py` | Small compatibility entry point for existing desktop shortcuts. |
| `check_labs.py` | Validate an explicitly supplied catalog without installing it. |
| `check_terminal_apps.py` | Isolated terminal selection, launch/cleanup and mocked distro package-plan regressions; no Docker or production data. |
| `check_file_picker.py` | Offscreen Qt 6 file/folder picker regressions, including asynchronous navigation without false error popups and real invalid-folder errors. Disposable metadata fixtures and process-group cleanup; no daemon or production data. |
| `check_notifications.py` | Offscreen notifications, modal dimming/shadows and nested dialogs; `--suite navigation` checks the responsive header, sliding indicator and keyboard routing; `--suite landing` checks draft creation/list layout; `--suite editor` checks all draft sections, toolbar actions and unsaved-work guards; `--suite zoom` checks whole-app zoom and isolated preferences. Synthetic fixtures only; no daemon or user data. |
| `check_notifications.py --suite components` | Shared control variants, contrast, keyboard focus, switch/checkbox states, busy button and screenshots in both themes. |
| `check_notifications.py --suite assessment` | Delayed report selection/history, superseded loading, Checkwork errors and malformed export responses using a fake backend. |
| `check_notifications.py --suite markdown` | Screenshot comparisons after scrolling long guides down and back up, with tables, selection, both themes, narrow layouts and zoom. Synthetic documents only. |
| `check_ui_diagnostics.py` | Strict-by-default warning detection; the explicit WorkerScript exemption recognizes plain and ANSI-colored logs without hiding other warnings. |
| `prepare_lab_images.py` | Explicit administrator workflow for bounded, reviewed image recipes. |
| `prepare_ubuntu_workstation.py` | Fixed Ubuntu/student/sudo image build and guarded opt-in activation; never rewrites Labs. See `docs/ubuntu-workstations.md`. |
| `check_workstations.py` | Isolated workstation policy, Docker argument and full-system checkpoint checks; no real Docker or user data. |
| `check_image_storage.py` | Shared-layer quota accounting, conservative metadata fallback and immutable history cache; no Docker connection. |
| `check_lab_preferences.py` | Offscreen username save/restart/invalid-config/recovery checks using disposable Qt preferences. |
| `check_editing_drafts.py` | Draft reuse, explicit selection/new copy, ownership, concurrency and private-bus CLI/daemon round trip; only temporary catalogs/stores and MemoryRuntime. |
| `check_startup_authoring.py` | Validate/publish/export/import the package emitted by the editor QML startup test; temporary stores/catalogs only, no Docker or production Labs. Requires `--qml-log` from the editor suite. |
| `check_session_state.py` | Save/stop/suspend/resume/reset, submission export/review/finalization, failed-capture preservation, private-bus restart and guarded-updater checkpoint regressions. Temporary stores and MemoryRuntime only. |
| `check_workstation_runtime.py` | Explicit administrator acceptance on disposable Docker fixtures: sudo/apt, full-system suspend/resume and reset. Uses its own checkpoint scope and never the production catalog/database. |
| `check_network_runtime.py` | Explicit administrator acceptance: single-interface DNS/TCP and apt installation, offline LAN, separate Session bridges and declared second interfaces. Removes only its disposable Sessions; never uses the production catalog. |
| `check_desktops.py` | Seamless application attachment, owner/session cleanup, bounded relay, fixed guest commands, authenticated readiness and private Xpra transport; no Docker or host display. |
| `check_x11_safety.py` | Fail-closed native-X11 quarantine checks; no host display, Docker or user credentials. |
| `check_native_display.py` | Unfinished native context/lifecycle unit checks with mocked display operations, plus preferences and relay checks. Not native acceptance. |
| `check_x11_security.py` | Explicit Xvfb-only authorization diagnostics using `disposable_x11.py`; dynamic display and process/socket ownership checks. See `docs/native-x11-safety.md` before running. |
| `check_seamless_apps.py` | Real native Xpra handshake, two separate application windows, detach and reconnect on temporary displays; requires system Xpra/GTK3 and an explicit `--xvfb /absolute/path/to/Xvfb`. No Docker or production data. |

Python remains the implementation language of the application and of the
security-sensitive helpers. Package installation, venv installation, service
registration and the normal deployment sequence are orchestrated by Bash.
Do not replace structured manifest checks or backup/rollback with unchecked
shell text processing just to remove `.py` files.

## Isolated lifecycle checks

Run engine checks with a Python environment containing the project dependencies.
On an installed host, the existing private runtime environment can run the source
checks without installing packages or changing the daemon:

```sh
/usr/lib/cyberlab/venv/bin/python -B tools/check_session_state.py
/usr/lib/cyberlab/venv/bin/python -B tools/check_workstations.py
python3 -B tools/check_notifications.py --suite lifecycle
python3 -B tools/check_notifications.py --suite practice --native
/usr/lib/cyberlab/venv/bin/python -B tools/check_desktops.py
python3 -B tools/check_notifications.py --suite desktop
```

The lifecycle UI suite uses synthetic CLI replies to test successful, failed,
missing and mismatched responses, checkpoint confirmation and navigation during
an outstanding request. The practice suite checks the controls themselves.
Both run offscreen with temporary preferences and exact process-group cleanup.
These checks do not create real Docker Sessions or certify real-Docker behavior.
Historical `tests/test_*.py` references in feature documents describe older
coverage, not files present in this checkout.

The Markdown reader keeps its selectable rich text inside a document-sized
clipping item. This gives Qt's text renderer a stable viewport while the outer
Flickable handles scrolling. Without that boundary, Qt 6.12 can omit previously
visible paragraphs when scrolling backwards through a long document with
tables. Keep the boundary when changing the reader; the Markdown suite compares
rendered pixels, not just the text property. This renders the whole bounded guide
rather than rebuilding text or allocating a document-sized texture per scroll.

The obsolete MVP, OVA, AppImage-download, migration and fixture-preview scripts
were moved outside this checkout to the local user's
`~/.local/state/cyberlab/development-archives/` directory. They are not required
on a new machine. Historical documents mentioning them are not current setup
instructions; use `docs/install-mvp.md` and the root README instead.
