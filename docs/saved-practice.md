# Saved Practice

The existing architecture remains unchanged: Studio and CLI use System D-Bus,
cyberlabd owns authorization, and the engine delegates container operations to
the restricted Docker adapter. Persistence is available when the daemon has
private practice storage configured (currently alongside authoring storage).

## Operations

The practice toolbar keeps submission (when supported), pause, and an overflow
menu visible. Saved stopped/suspended Sessions show resume instead. Reports
sit beside the Session title. Save, Quiz, restart from the template, stop without
saving new changes, and checkpoint deletion live in the popup menu; reset, stop
and deletion still use the existing confirmation dialogs. The menu closes before
dispatch and cancels pending actions when the selected Session changes. This is
a UI-only rearrangement; the shared D-Bus API and checkpoint semantics are unchanged.
The practice overflow menu has a bordered surface with a drop shadow, without
dimming the window. Confirmation dialogs retain their shadows and dimmed backdrop.
Run `python3 -B tools/check_notifications.py --suite practice --native` for
isolated offscreen interaction, state, keyboard, responsive-layout checks and
native Quickshell component loading with the packaged `qmldir` registry.

Lifecycle success messages require a response for the requested Session in the
expected state; save/suspend also require a confirmed checkpoint. Missing or
inconsistent replies produce an error and refresh the Session list instead of
claiming success. Delayed replies do not navigate away from another selected
Session or the editor. Run `python3 -B tools/check_notifications.py --suite lifecycle`
for isolated response/error/navigation regression checks.

Studio distinguishes a suspended Session from a stopped Session with an older
checkpoint. The Library displays "Da tam dung" only for `SUSPENDED`; `STOPPED`
with saved progress displays "Da dung - Co ban luu" and offers continuation from
that saved checkpoint. Stop does not automatically save the latest changes or
delete an earlier checkpoint. This label correction does not change lifecycle
or checkpoint contents.

Runtime transitions now persist lifecycle state separately from the checkpoint
contents and capture time. A stopped saved Session stays `STOPPED` after daemon
restart; a suspended checkpoint stays `SUSPENDED`. Older `SAVED` records still
restore as suspended, never as a running container. Resume records the new
runtime state so a previous stopped marker cannot survive a later running
Session. The guarded updater preserves verified pre-upgrade stopped checkpoint
states after backing up private storage, with exact owner/ID/capture-time
matching; it does not guess whether older suspended records were once stopped.

```sh
cyberlab save SESSION_ID
cyberlab suspend SESSION_ID
cyberlab resume SESSION_ID
cyberlab discard SESSION_ID --yes
```

- `save` captures bounded node workspaces while keeping the Session running.
  Administrator-enabled Ubuntu workstations additionally save their writable
  system filesystem, including installed packages, as private checkpoint images.
- `suspend` saves first, then removes that Session's containers/networks and
  closes its tracked terminal windows. A failed save never stops the Session.
- `resume` recreates resources from the captured Lab package and restores the
  saved workspaces and any Ubuntu system checkpoint images. CLI opens the configured terminals unless `--no-terminals`
  is passed. No current-catalog substitution is performed.
- `stop` removes live resources but preserves an existing checkpoint. Changes
  made after the last successful save are lost.
- `reset` deletes the checkpoint and recreates the original captured template,
  including its initial files. It is not resume.
- `discard --yes` deletes only the selected checkpoint. A running Session and
  its current files remain untouched; a suspended Session becomes `STOPPED`.
  Studio asks for confirmation with **Xoa ban luu** before calling the same API.
  This does not delete a Lab, draft, image or another user's progress.

The D-Bus methods are `SaveSession`, `SuspendSession`, `ResumeSession` and
`DiscardSessionCheckpoint`. Responses include `saved` and `checkpoint_at`.
Capabilities `session-persistence` and `discard-checkpoint` are advertised only
when storage exists. Owner checks also apply to deletion; root may administer
all Sessions. There are 10 saved Sessions per user and 50 globally. Stopping a
Session does not free this quota; explicitly discard an unwanted checkpoint.
Ordinary stopped-history pruning never evicts saved progress.

## Snapshot and Recovery

The private database `/var/lib/cyberlab/authoring/practice.sqlite3` uses mode
`0600`. The systemd authoring drop-in uses `UMask=0077`. Schema version 2 stores
the captured definition and bounded package assets as JSON/base64, including
empty directories and binary files, plus workspace archives. Packages are
materialized in a temporary private directory and validated with the normal
Lab loader. Seeds, documentation, accounts and network declarations therefore
survive a daemon restart even if the catalog template later changes.

Schema version 1 is migrated transactionally without deleting saved work.
Legacy checkpoints without files/docs can still resume. Checkpoints needing
missing package assets remain visible with an explanatory error: resume/reset
are refused instead of using potentially changed catalog data. Explicit discard
is still available. Corrupt rows are retained for administrator recovery.

Restricted nodes save only bounded workspace files, not changes elsewhere in
their container filesystem. Administrator-enabled Ubuntu workstations save the
writable system filesystem as well; `/tmp` and `/run` remain ephemeral. See
`docs/ubuntu-workstations.md` for image limits, recovery and administrator opt-in.
Neither mode preserves process memory, running processes or network connections.
Suspend is save-and-remove, not a live VM freeze. Writes occurring while `save`
reads a workspace are not an application-level transaction; stop editing files
and wait for package installation to finish before saving. Unsaved work remains volatile.
At daemon startup, old managed resources are cleaned and valid saved Sessions
appear as `STOPPED` if explicitly stopped, otherwise `SUSPENDED`; resume is
explicit in both cases.

## Development Deployment

`tools/upgrade_runtime.py --repair-service-policy` applies only the reviewed
private-umask repair and the daemon's minimal `CAP_CHOWN` capability, needed to
preserve catalog ownership during an installed-Lab update. Container
capabilities and Docker socket permissions remain unchanged. Custom capability
policies are rejected rather than overwritten.
Retired update trees and explicitly deleted templates are removed through
directory descriptors without following links. The daemon reclaims ownership
only of those directories so it can clean user-owned `0755` trees using
`CAP_CHOWN`, without granting DAC-override or broad filesystem capabilities.

The updater verifies all allowed users' Sessions are `STOPPED`, backs up the
runtime, private databases and changed service files, fixes the legacy practice
database mode, and restarts the existing service. On failure it restores the
runtime, pre-migration databases and service files while retaining failed
artifacts. `verification.json` records the installed wheel digest and result.
No production Lab or draft is modified to verify this feature.

If a VM has already failed to boot the old daemon because its empty practice
database has mode `0644`, the updater's explicit `--recover-private-state`
option checks that the service failed, no saved checkpoints exist, and no
managed Docker containers/networks remain. It backs up that database, repairs
only its mode, starts the old daemon, then performs the normal all-user Session
checks before upgrading. It refuses recovery that could remove active work.

Regression coverage includes restart with files/users/docs, catalog removal,
legacy migration, permission safety, discard ownership/quota, failed cleanup,
D-Bus/CLI dispatch and offscreen Studio layout/state checks.
Run `python3 -B tools/check_session_state.py` for isolated lifecycle persistence
and guarded-upgrade checks, including preservation of checkpoint contents and
rollback on mismatched checkpoint identity, submission export/review/finalization,
changed-work rejection, and failed-save preservation. Use a Python environment
with the project dependencies (on an installed host,
`/usr/lib/cyberlab/venv/bin/python -B tools/check_session_state.py`). These checks
use temporary stores, MemoryRuntime and a private test bus; no Docker or system
bus is used. They do not replace real-Docker/manual acceptance.

Submit-and-finish exports a local evidence package and stops only after the CLI
successfully writes that new file. It does not upload to an instructor server.
The resumable checkpoint stays on this host; private Ubuntu system images are
not included in the exported evidence package.
