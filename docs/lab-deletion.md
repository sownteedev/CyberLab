# Installed Lab deletion

Approved by the user on 2026-10-22. Every allowed CyberLab user may explicitly
delete a Lab in this VM through the existing System D-Bus daemon. No separate
author role or direct filesystem access is introduced.

## Workflow

- Studio: select a Lab in Library, choose `Xóa bài lab`, review the Lab name/ID
  and permanent-deletion warning, then confirm. Cancel does not send a request.
- CLI: `cyberlab delete-lab LAB_ID --yes`. Missing confirmation fails before
  connecting to D-Bus. The result is a JSON boolean.
- Transport: `DeleteLab(s lab_id) -> b deleted`, advertised by `delete-lab` in
  `GetCapabilities`. The caller UID comes from the bus, not request arguments.
- An older daemon without the capability leaves the Studio action disabled and
  displays a runtime-update message. Updating the source shortcut alone does
  not update the privileged daemon.

## Safety and scope

The engine serializes deletion with start/reset/stop and draft publication using
the lifecycle lock. Any non-STOPPED Session of the selected Lab blocks deletion,
including another user's Session and FAILED Sessions. Stop them first; deletion
does not force-stop workloads. The daemon enforces this even when UI state is
stale or another user's Sessions are not visible to the caller.

The catalog is validated before deletion. Lab IDs are looked up as metadata,
never joined to a filesystem path. Invalid catalogs, symlink entries and
duplicate identities are rejected. Only the selected template directory and its
stopped Session history/import receipts are removed. Other Labs, private drafts,
Docker images and unrelated files remain untouched. There is no undo.

After a confirmed success, Studio removes stale Lab/Session state and refreshes
the library through the daemon. On rejection it retains the existing selection
and displays the API error. A timeout is ambiguous: inspect the library before
retrying, rather than assuming nothing was deleted.

## Validation and deployment status

- Full regression: **819 passed** (32.20 seconds), recorded in
  `dist/validation-delete-lab/pytest.txt`.
- Actual private-D-Bus/MemoryRuntime smoke checks active-session rejection,
  successful deletion, preservation of other Labs, stopped-history removal and
  repeat-deletion `NotFound`, using only temporary copies of test fixtures.
- UI checks cover capability gating, busy/running/failed-session rejection,
  successful state cleanup and preservation of state after an API rejection.
- Built wheel: `dist/validation-delete-lab/cyberlab_engine-0.9.0-py3-none-any.whl`.
  All 79 checked Python/QML/JS/XML/module-registry files match source; hash and
  verification details are in `dist/validation-delete-lab/wheel-verification.json`.
- Deployed on 2026-10-22 at 08:06 UTC using the guarded updater after the user
  authorized automatic development builds, runtime updates and restarts. All
  three existing Sessions were STOPPED before deployment; the updater also
  checked every allowed UID before stopping the service.
- The installed daemon is active with `runtime:docker` and `delete-lab`.
  Both installed and source CLI report the new capability; live System D-Bus
  introspection exposes `DeleteLab(s) -> b`. Installed dependency checks pass.
- All 81 packaged files (including schema/package data) match the wheel, source
  and installed runtime. The updater verified unchanged configuration bytes and
  catalog identities. No production Lab was deleted or real-Docker Session
  created to verify the upgrade. Quickshell/Qt were not upgraded.
- Runtime/configuration/authoring backup: `/var/tmp/cyberlab-runtime-backup-kdtt7gej`.
  Deployment evidence: `dist/validation-delete-lab/deployment.json`.

The command used for this deployment was:

```sh
sudo /usr/bin/python3 -I tools/upgrade_runtime.py \
  dist/validation-delete-lab/cyberlab_engine-0.9.0-py3-none-any.whl \
  --sha256 962e18c9ab8d58172c64eae3adf62e8664b380137fdb6b04aba888f8724661b4 \
  --uid "$(id -u)"
```

The user's standing development approval now covers build/install/restart for
the existing runtime; it does not authorize deleting production data to test.
Future updates must still use a freshly verified wheel/checksum, refuse active
Sessions and preserve unsaved Studio work rather than force-close its windows.

This update changes the installed package, not the catalog or Quickshell/Qt.
Restarting the daemon clears volatile Session history: the three stopped entries
are no longer listed, but Lab templates and private drafts remain. Existing
Studio windows cache capabilities until refreshed; a freshly opened window
loads the updated capability automatically. Manual deletion acceptance remains
with the user; no production Lab was deleted just to check the upgrade.
