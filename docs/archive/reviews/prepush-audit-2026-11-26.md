# CyberLab pre-push audit - 2026-11-26

> **Tài liệu lịch sử.** Trạng thái và lệnh bên dưới thuộc lần ghi nhận này,
> không thay thế [hướng dẫn hiện hành](../../README.md).

Baseline: `3881f69`. No production catalog, installed runtime, desktop session,
Docker permissions or backup directories are changed by this audit. No commit
or push is performed. Test data lives in disposable directories. Raw logs are
under `/tmp/cyberlab-audit-20261126`; these logs are transient, not release assets.

## Findings and repair ledger

1. **Update ancestry (application defect).** Comparing unequal SHAs classified
   an older or divergent remote as an update. Added failing protocol tests, then
   compare installed base against the exact target commit. Only `ahead` enables
   the update notification/action. Behind, divergent and unresolved histories
   have distinct UI states; explicit CLI updates cannot replace a known install
   without a confirmed forward comparison. A local install without a receipt
   remains unknown; its explicit administrative update path is retained.
   JSON check responses add `comparison`; no D-Bus signatures change. Legacy
   responses without ancestry are treated conservatively by the new UI.
2. **First Quiz group (application defect).** Adding a group before populating
   the virtual default group serializes an extra empty group. Validation then
   fails `minItems`, blocking export/publication. Regression coverage exercises
   the actual Add Group/Add Question controls and preservation of existing
   legacy questions and explicitly created groups. Only the unsaved synthetic
   placeholder is eligible for removal; authored groups must remain intact.
3. **Account interaction test timing (harness defect).** The test clicked a
   layout-managed control after only `wait(0)`, without waiting for window
   exposure/layout polish. It failed once then passed unchanged in the previous
   audit. Use the QtTest window/layout readiness conditions and the existing
   viewport-reveal helper, not a longer arbitrary timeout or weaker assertion.
4. **Desktop test fixtures (harness defect).** Six assertions clicked a hidden
   reconnect button because the fixture omitted `gui_backends.client = xpra`.
   Production intentionally hides that button for native/unknown transports.
   Correct the fixture and explicitly test that native/unknown remain hidden.
5. **Compatibility and updater mocks (harness defects).** The historical digest
   fixture incorrectly included the subsequently added absent difficulty field.
   The native-display installer test omitted the wheelhouse/lease/verification
   callback contract and tried to retain a backup in a nonexistent fixture
   directory. Keep runtime digest behavior unchanged; correct expectations and
   isolate retention while checking the actual verification callback.
6. **Native authoring workflow (harness defects).** The old workflow omitted
   required difficulty and used installed Python modules despite testing source
   QML. Route CLI and private daemon to this checkout, stage the QML root so
   Quickshell imports remain inside its configuration, and choose difficulty.
   Preserve output when an isolated workflow times out.

## Coverage and safety classification

Every `tools/check_*.py` is classified below. Scripts requiring live Docker or
administration are not treated as unit tests and are not run against user data.

| Group | Coverage / evidence | Status |
| --- | --- | --- |
| Drafts, files and protection | `check_editing_drafts`, `check_file_editor`, `check_edit_protection`, `check_edit_access_cli`, `check_private_catalog`, `check_exchange_v3`, `check_catalog_migration` | Isolated checks; final results below |
| Authoring model and software | `check_account_passwords`, `check_machine_setup`, `check_setup_files_snapshot`, `check_difficulty`, `check_topics`, `check_software`, `check_auto_software`, `check_package_search`, `check_labtainer_compatibility` | Isolated checks; final results below |
| Assessment and persistence | `check_checkwork_regression`, `check_assessment_quiz`, `check_result_collection`, `check_session_state` | Temporary stores and MemoryRuntime, not real containers |
| Runtime arguments and display isolation | `check_workstations`, `check_desktops`, `check_native_display`, `check_terminal_apps`, `check_image_storage`, `check_x11_relay`, `check_x11_safety` | Mocks/private displays; no production Docker |
| Maintenance and distribution | `check_maintenance`, `check_system_update`, `check_update_ui`, `check_upgrade_runtime`, `check_qml_manifest`, `check_ui_diagnostics`, `check_update_window` | Isolated fixtures, fake installer, packaged smoke |
| UI | All 19 `check_notifications --suite` variants; `check_account_editor`, `check_edit_access_ui`, `check_file_picker`, `check_lab_preferences`, `check_package_import_ui` | Offscreen, disposable preferences |
| Cross-layer authoring | `check_machine_setup_workflow`, `check_startup_authoring --qml-log ...` | Real QML/CLI/private D-Bus; MemoryRuntime only |
| XWayland | `check_xwayland` | Real isolated servers/relay, no host display lease or Docker |
| Xvfb-dependent | `check_x11_security --xvfb ...`, `check_seamless_apps --xvfb ...` | Blocked: Xvfb not installed |
| Privileged acceptance | `check_gui_runtime`, `check_machine_setup_runtime`, `check_network_runtime`, `check_software_runtime`, `check_workstation_runtime`, `check_xwayland_guest` | Blocked: non-root process, NoNewPrivs=1, no Docker socket access |
| Helpers / explicit inputs | `check_software_gui` is a child of software acceptance; `check_labs` needs an explicitly supplied disposable catalog | Not standalone acceptance against the production catalog |

The initial security/guest invocations rejected missing `--xvfb`/administrative
context before performing their tests. They are recorded as blocked, not passed.

## Cross-layer workflow and remaining acceptance

The automated authoring fixture uses real controls for creation/save and app
service operations for detailed configuration. It creates two Ubuntu nodes,
a shared network, users/groups, a file, Quiz and Result/Goal declarations;
exports/imports v3 and reopens the draft. Its runtime is deliberately in-memory.
The completed run also answers the preparation Quiz incorrectly, starts the
two-node Session, checks that the wrong seeded answer is FAIL, and checks that
an unsupported Ubuntu system save leaves the Session RUNNING, unsaved and with
the same evidence before stopping it. It does not simulate a successful Ubuntu
system checkpoint just to make acceptance appear complete.
It must not be presented as a fully manual UX exercise, actual package
installation, working Linux terminals, packet forwarding or GUI acceptance.

Before calling a new-machine release fully verified, run on a disposable VM:

- Install the published snapshot without a checkout/Git; confirm receipt,
  system paths, ordinary-user access denial and desktop launch.
- Create the two-machine exercise through visible controls, including software
  and scripts. Save/reopen/discard edits, lock editing, export and import into a
  second isolated installation.
- Answer Quiz incorrectly and still enter practice after reviewing answers;
  install software, open actual terminals/GUI and test DNS/Internet/offline LAN.
- Checkwork before work, after an incorrect answer, after a correct answer and
  after capture failure; verify fresh evidence, reports and checkpoint/reset.
- Exercise graphical authentication cancellation and a successful update;
  inject daemon/QML failure to verify rollback without losing draft/checkpoint.

## Environment limits

- Native Quickshell reports Qt build 6.12.0 versus host Qt 6.12.1. The offscreen
  configurations load, but no host package upgrade/rebuild is performed.
- Editor and file tests emit the previously identified Qt WorkerScript
  `QObject::connect(QJSEngine, QtObject): invalid nullptr parameter` warning.
  The explicit existing exemption matches only that exact diagnostic; other
  warnings still fail the runner. Strict files run is retained in the logs.
- Public curl installation, real root authentication/update/rollback and
  two-machine Docker acceptance remain unverified here. No claim of complete
  security, zero bugs or compatibility across every distro follows.

## Final verification results

| Check | Result |
| --- | --- |
| 33 isolated Python unittest scripts | 586 tests passed, including 21 update protocol tests |
| `check_startup_authoring` against the final editor log | 4 tests passed |
| All 19 Qt component suites plus 5 standalone UI suites | 690 passed, 0 assertion failures; Qt totals include init/cleanup and four preference-process runs |
| Account suite repeated after readiness fix | 5 consecutive runs, 27 passed each; not counted again in the UI total |
| Native authoring workflow | PASS: source QML -> source CLI -> private source daemon, disposable catalog and MemoryRuntime |
| Native update window | PASS: fake updater, notification/state parsing, readiness handoff and cleanup |
| Isolated XWayland acceptance | PASS: private server/relay, valid/revoked credentials, unrelated client survives |
| Fresh built wheel | Required modules/assets present; install into temporary venv, `pip check`, CLI help and native packaged Studio probe passed |
| Static checks | `bash -n install.sh tools/install/system.sh` and `git diff --check` passed |
| Focused independent read-only review | No concrete introduced regression in update ancestry or first-Quiz-group fixes |

These totals use final reruns for modified suites, not their initial red runs.
The strict files suite initially returned nonzero solely for the documented
WorkerScript warning; final editor/files runs used the existing explicit warning
exemption. The native authoring save-error log is an expected negative assertion,
not a successful checkpoint or an unhandled production error.

Machine-readable test ledgers: `python-results.json`, `ui-results.json`,
`final-python-results.json`, `final-ui-results.json` in the log directory.
Screenshots of update states/themes are under its `screenshots/updates/` folder.
The baseline API/schema and catalog data remain unchanged. The source changes
are ready for review/push; the privileged/new-machine acceptance checklist above
must remain open until executed in the appropriate environment.
