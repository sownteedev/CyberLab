# System installation, update and package protection

## User workflow

After these changes are published to `master`, a new machine can run:

```sh
curl -fsSL https://raw.githubusercontent.com/sownteedev/CyberLab/master/install.sh | bash
cyberlab update --check
cyberlab update
```

No Release or Git checkout is required. The bootstrap needs Python 3, curl,
HTTPS access to GitHub, and a terminal for sudo. The existing distro adapter
checks Python 3.12+, systemd, Docker and native Quickshell requirements. It does
not add a repository or upgrade the operating system automatically. Missing
Quickshell in enabled repositories still requires an explicit administrator
decision; see `install-mvp.md`.

Checkout installation remains `bash install.sh`; options are forwarded to
`tools/install/system.sh`. For the link form, pass options with `bash -s -- ...`.
Only run scripts from a repository you trust. HTTPS plus a commit pin is not a
publisher signature or independent audit of source and dependency packages.

## Files and trust boundary

| Content | New installation |
| --- | --- |
| Runtime, CLI module and installation receipt | `/usr/lib/cyberlab/` |
| Configuration | `/etc/cyberlab/` |
| Empty private catalog | `/var/lib/cyberlab/labs/` |
| Authoring and practice state | `/var/lib/cyberlab/authoring/` |
| Launchers and application entry | Existing system locations |
| Temporary downloads/builds | Private directories under `/var/tmp/` |

Catalog directories are 0700 and internal files 0600. The daemon owns and reads
them; the desktop account uses its API. New service configuration has no home
catalog bind mount or supplementary user group. Preferences and deliberately
exported files can still be stored in home. Python and QML runtime files remain
readable installation resources: this does not encrypt or hide the application.

When initiated as root with a chosen desktop account, downloaded source remains
root-owned but permits that account's primary group to read/traverse it for
unprivileged dependency probes (0750 directories, 0640 files, never group-write).
Build directories belong to the build account; logs and rollback state remain
root-private. The sanitized build HOME is applied after `runuser` switches users.

Existing home catalogs and development repositories are never moved, removed,
or converted by an ordinary update. A migration needs separate approval.

## Install/update transaction

1. Resolve `master` to one full commit. Download the helper and snapshot for that
   same commit, not different mutable branch URLs. Reject unsafe archive paths,
   links, duplicates, special files and excessive compressed/expanded sizes.
2. Extract into private system temporary storage. Escalate from a real script
   file, not `/dev/fd`. Build in an isolated temporary venv as the desktop user;
   pip home, cache and temporary paths stay outside home.
3. Hold `/run/cyberlab-installer.lock` for installation/replacement. Build all
   dependency wheels before changing the installed application. Updates never
   call the host package manager.
4. Require Studio to be closed and every authorized user's Session to be
   STOPPED. Hold an exclusive maintenance lease while daemon mutation requests
   take shared leases. This prevents a new unsaved Session starting between the
   last check and shutdown. Recheck around shutdown; never stop labs or close
   windows automatically. Refuse replacement while background software
   preparation is active. Reserve space for backups, pip and recovery.
5. Preserve the runtime, authoring state, receipt and narrowly changed service
   settings. Install Python dependencies offline from the staged wheelhouse.
6. Verify pip, daemon/CLI, catalog identity, saved-checkpoint identity and native
   QML compilation of the installed Studio. The QML check is isolated/offscreen,
   does not instantiate the application backend, and is not live GUI acceptance.
7. Write the installed commit, package version and SHA-256 artifact digest only
   after successful verification. An unverified/dirty local checkout records an
   unknown commit rather than claiming to be the newest upstream build.
8. Remove temporary source/build data and staged wheels. Keep restricted logs
   and rollback material. The next successful update can remove only the prior
   backup marked as successful by this new manager. Historical/unmanaged backups
   and failed-update evidence are left alone.

`--check` does not require sudo or contact the daemon. A matching installed
commit is a no-op. Missing/old receipt data reports an unknown commit. GitHub
rate limiting or network errors do not alter the installation.

### First migration from a legacy daemon

An older daemon has no request lease (`maintenance-lock-v1`). The new updater
refuses to stop such a running daemon: polling alone cannot eliminate the risk
of a student starting an unsaved Session between the last check and shutdown.
This is an intentional fail-closed safety change, not a missing commit receipt.

For this one-time administrator migration, first save/stop all Sessions through
the old application and close Studio. Verify **every allowed account** has only
STOPPED Sessions. Only then, explicitly stop the daemon and use the offline
installer mode from this updated checkout:

```sh
sudo systemctl stop cyberlabd.service
bash install.sh --update --offline
```

Do not run the first command as a way to stop a student's active lab. The
installer does not execute it for you. Offline migration accepts only an
already inactive daemon, no remaining managed containers and STOPPED stored
Sessions. It reads the old catalog through the installed library, backs up
state/runtime, and verifies the new daemon normally. On replacement failure it
restores the old files and leaves the daemon stopped, matching the initial state.
Subsequent updates use ordinary `cyberlab update`; no migration option is needed.
This migration path still needs privileged VM acceptance before deployment.

## Failure and recovery

### Explicit migration of an existing home catalog

After updating to a daemon advertising `maintenance-lock-v1`, an administrator
can move the active catalog location to `/var/lib/cyberlab/labs`. Save/stop all
Sessions and close Studio first, then run from the updated checkout:

```sh
sudo /usr/bin/python3 -E tools/migrate_catalog.py --uid "$(id -u)"
```

This is a separate opt-in operation, not part of ordinary updates. It shares
the installer/maintenance locks, rejects active Sessions, Studio and background
software preparation, and refuses to overwrite an existing destination. It
copies regular files and empty directories with root-private permissions,
verifies content hashes, updates the catalog setting and removes the old home
catalog systemd exception. Additional/custom service overrides require manual
review instead of being overwritten. Drafts and practice data are not moved.

Configuration backups go into a private `/var/tmp/cyberlab-catalog-migration-*`
directory. The tool checks the restarted daemon, lab identities, saved Sessions
and ordinary-user read denial; activation errors restore the old configuration
and restart against the original catalog. Failed copies/targets are retained
for diagnosis; do not repeatedly rerun after failure or delete them blindly.

The original home catalog is deliberately **not deleted**. It remains readable
under its old permissions, is no longer the active catalog after success, and
must be removed separately after acceptance if no readable home copy is wanted.
Do not edit it expecting changes to appear in the migrated library.

`python3 tools/check_catalog_migration.py` uses temporary fixtures only, including
injected restart/write/verification failures. These checks do not establish that
the privileged migration has run successfully on a user's machine.

Download/build failure leaves the installed runtime untouched. Dependency,
daemon, catalog/checkpoint or QML verification failure during replacement
restores the previous venv, authoring state and receipt, and restarts the old
daemon. Do not blindly rerun after a reported failure. Save the printed private
staging/backup path and inspect its `install.log` and verification records as an
administrator, plus `journalctl -u cyberlabd`.

Backups contain private lab state. Do not chmod them for the student or publish
them in a bug report. A machine crash, SIGKILL, full disk during recovery, or a
failed system service restart can still require administrator recovery; this is
not a filesystem-wide atomic deployment. Do not manually combine a newer
database with an older venv. The retained backup is the paired recovery source.
After cancellation starts recovery, additional SIGINT/SIGTERM requests are
ignored until recovery/child completion; temporary sources are not removed while
the privileged installer is still running. SIGKILL and power loss are not covered.

## Lab exchange

New exports always use binary `cyberlab-lab/v3`. Ordinary ZIP/TAR extraction does
not expose a tree of files. Native imports go straight into the library and
preserve the author's edit-password verifier. Import, practice and re-export do
not ask for that password; authoring operations and editing clones do. Legacy
v1/v2 ZIP imports remain supported, and Labtainer conversion remains a distinct
draft workflow. Duplicate IDs stop without overwriting installed labs.

This format is **not encryption**. There is no secret key, signature, server or
recipient binding. A knowledgeable recipient can implement a decoder and alter
a package; a root administrator can read installed state. Checksums detect
corruption, not malicious changes. Author-selected files placed in practice
nodes are intentionally readable there. See `lab-packages.md` for the wire format.

## Verification and remaining acceptance

Isolated tests cover framing/limits/corruption, legacy import, private catalog
permissions, password guards and public DTO redaction, UI import completion,
download cleanup, commit handling, update locks, stopped-session checks,
dependency validation and injected rollback failures. The tools live in
`tools/check_exchange_v3.py`, `check_private_catalog.py`, `check_edit_protection.py`,
`check_package_import_ui.py`, `check_system_update.py`, `check_maintenance.py`
and `check_upgrade_runtime.py`.

Still required before advertising a verified public installer:

- Publish these changes to GitHub and run the literal curl command in a clean
  supported VM with no Git/checkout; verify menu/CLI launch and file locations.
- Run a real privileged install/update and verify sudo cancellation, active
  Studio/labs, lost network and rollback on that VM.
- Use two isolated machines: author/lock/export, import/practice/Quiz/Checkwork,
  password-gated edit and re-export with the lock retained.
- Check actual non-root filesystem denial and real Docker/GUI behavior on the
  new private catalog. Fixture permission checks are not that acceptance test.

No production catalog, draft, password or live Session is a test fixture.
