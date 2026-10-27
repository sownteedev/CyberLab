# Saved Practice

The existing architecture remains unchanged: Studio and CLI use System D-Bus,
cyberlabd owns authorization, and the engine delegates container operations to
the restricted Docker adapter. Persistence is available when the daemon has
private practice storage configured (currently alongside authoring storage).

## Operations

```sh
cyberlab save SESSION_ID
cyberlab suspend SESSION_ID
cyberlab resume SESSION_ID
cyberlab discard SESSION_ID --yes
```

- `save` captures bounded node workspaces while keeping the Session running.
- `suspend` saves first, then removes that Session's containers/networks and
  closes its tracked terminal windows. A failed save never stops the Session.
- `resume` recreates resources from the captured Lab package and restores the
  saved workspaces. CLI opens the configured terminals unless `--no-terminals`
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

Only bounded workspace files are saved, not running processes, shell history
outside the workspace, process memory, network connections or image mutations.
Writes occurring while `save` reads a workspace are not an application-level
transaction; stop editing files before saving. Unsaved work remains volatile.
At daemon startup, old managed resources are cleaned and valid saved Sessions
appear as `SUSPENDED`; resume is explicit.

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
