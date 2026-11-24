# Backend audit - 2026-11-20

## Scope and baseline

This pass follows the initial UI audit. It changes backend behavior, not the
application architecture, public D-Bus contract, schema versions or host policy.
The full application audit is not complete.

- Checkout: `/home/nguyenthanhson/CyberLab`.
- Pre-existing edits are preserved. This pass is compared with
  `/tmp/cyberlab-backend-audit-jP02qK/baseline`, not with repository HEAD.
- Evidence: `/tmp/cyberlab-backend-audit-jP02qK` (copy to the handoff before delivery).
- Fixtures use temporary catalogs/databases and MemoryRuntime or mocked adapters.
  No production catalog, draft or practice data is a test fixture.

## Confirmed defects and changes

| ID | User impact / reproduction | Fix | Regression evidence |
| --- | --- | --- | --- |
| B1 | Reset a saved Session; fail software preparation or stop while preparation waits. The deleted checkpoint is still advertised as resumable. | Publish the checkpoint-free Session before starting preparation. | Two failing tests in `reset-red.log`, then passing session tests; checks status during preparation and after cancellation. |
| B2 | Reset deletes a checkpoint, then SQLite rejects Quiz deletion. Saved work is lost despite reset failing; Session stays RESETTING. | Delete checkpoint and Quiz in one transaction. On storage failure retain both and expose FAILED, allowing stop/resume or retry. | SQLite trigger reproducer in `reset-storage-red.log`; checks preserved workspace and Quiz and successful stop/resume. |
| B3 | Update a Lab; saving the draft origin fails after the catalog exchange. The call fails but the catalog has changed and retry conflicts. | Save the origin inside the rollback-protected exchange. Detect concurrent edits before rollback, keep recovery directories rather than deleting potentially edited data. | `update-red.log`, `review-update-red.log`; real SQLite origin-trigger failure, retry, external edits before/during update, invalid concurrent content. |
| B4 | Software worker cannot save its final status. Dead worker blocks preparation, and persisted active status can keep Studio busy indefinitely. | Release the reservation in finally; under the manager lock, expose orphaned active jobs as FAILED through status/latest/cancel. | `worker-red.log`, `review-worker-red.log`; final-write failure, owner checks, status/latest/cancel/plan recovery and retry. SoftwareEditor test verifies the translated error and enabled retry. |
| B5 | Checkpoint commit succeeds, but the later garbage-collection reference read fails. Save/reset falsely fails and leaves memory behind persisted state. | Skip image collection when SQLite references cannot be read; retain images rather than guessing. | `cleanup-red.log`; save/reset succeed with consistent metadata and no image collection/release. |

The new reset failure message is translated into Vietnamese through the existing
Studio error-message path. `messages-red.log` reproduces the missing translation;
`messages-green.log` verifies it alongside existing translation coverage.

## Coverage and limits

| Area | Work in this pass | Limit |
| --- | --- | --- |
| Session lifecycle | Read lifecycle, cancellation, checkpoint and reservation paths; added reset, storage fault and cancellation tests. | MemoryRuntime is not live Docker acceptance. |
| Authoring/catalog update | Read draft transactions, revision/origin checks and exchange rollback; added real temporary-filesystem rollback tests. | Process/power loss between filesystem and SQLite commits is not crash-atomic; no recovery journal is introduced. |
| Software preparation | Read manual/automatic preparation, cancellation and shutdown; added worker-release/status recovery regression. | Status recovery requires readable storage. Persistent database unavailability still prevents requests; the backend cannot repair storage hardware/permissions. |
| Assessment/submission | Read capture locks, ownership, stale-session/Quiz/workspace checks and finalize flow; run existing regressions. | No new real-container grading or visible Quiz-to-terminal end-to-end acceptance in this pass. |
| Daemon/CLI | Read request limits, caller authorization, error mapping and shutdown; existing private-bus round trips run in the suites. | Not a complete independent security audit or saturation/load test. |
| Files/import/network/desktop | Existing regression suites check fixtures and mocks. | Live GUI, real Docker networks and transport interruption are not revalidated by these unit suites. |

## Verification ledger

- B1: RED -> GREEN; session suite initially 20 tests, automatic software 25 tests.
- B2: RED -> GREEN; session suite then 21 tests.
- B3: RED -> GREEN; initial editing suite 14 tests including private-bus CLI round trip.
- B4: RED -> GREEN; software suite 20 tests, automatic software inherits this regression.
- B5: RED -> GREEN; session suite 22 tests.
- Final review: one independent read-only review identified a concurrent-edit
  rollback issue (P1) and incomplete Studio recovery for orphaned jobs (P2).
  Both entered one fix pass, with failing regressions before implementation.
- Final: fixed concurrent-edit rollback -- two callback-window tests RED -> GREEN;
  editing suite expanded to 16 tests, and the storage test now uses a real SQLite trigger.
- Final: fixed orphaned UI job -- final-write/status regression RED -> GREEN;
  status/latest/cancel/plan and SoftwareEditor retry eligibility covered.
- Final source regression: 338 Python test executions across 16 suites, all pass
  (inherited cases are counted each time they execute). Four offscreen UI suites
  report 117 QtTest results including init/cleanup, all pass. Message checks cover
  276 static backend strings plus explicit new dynamic errors. `git diff --check` passes.
- Final wheel: 333 packaged files match the source snapshot; 84 Python test
  executions run against extracted wheel modules and 25 software-editor QtTest
  results pass. These are artifact checks, not installed/live-Docker acceptance.
- Wheel SHA-256: `d3cfa343bc3d073d3314d45c0ae4b3813ce9cfba5b0eb2f489a8d292e3637ba1`.
- Handoff: `/home/nguyenthanhson/Documents/ChatGPT/CyberLab/backend-audit-2026-11-20`.
  The initial handoff was source-only. On the subsequent installation request,
  the guarded updater succeeded with backup `/var/tmp/cyberlab-runtime-backup-hxv341xl`.
  All 333 installed files matched; 84 installed Python executions and 60 QtTest
  results passed. A tracked native Studio window loaded without QML errors and
  was then closed. The manifest now records `installed: true`.

## Review rulings and deferred checks

- Ruling: keep recovery directories after rollback, even if their content appeared
  unchanged. This avoids deleting a late edit through an already-open filesystem
  handle. Cost: an administrator may need to inspect and clean hidden
  `.cyberlab-update-*` directories after failures; their paths are logged.
- Ruling: no durable cross-store journal in this bounded fix. Power/process loss
  or failed rollback I/O can still require manual recovery; no crash-atomicity claim.
- Ruling: live Docker/network/GUI and visible Studio acceptance remain unverified
  by this pass. Unit/private-bus checks do not establish real-container behavior.
- Ruling: whole-product security, saturation and unrelated dirty-worktree changes
  are not certified by this delta review. Existing edits remain untouched.
- Ruling: do not replace the installed runtime while the user's Studio is open
  with unknown unsaved state. At the preflight, Session list was empty but Studio
  PID 39790 remained open; it was not closed and the updater was not invoked then.
  On the later installation request, Studio was closed and guarded deployment
  proceeded safely; see the verification results above.
- Final: minor (deferred): extend B5 fault injection to nonempty workstation image
  references plus a later successful collection. Current regression verifies the
  fail-closed behavior with an empty capture; existing workstation tests still run.
- Existing ResourceWarnings were retained in logs: updater SQLite connections
  in `preserve_stopped_checkpoints` are not explicitly closed, and software
  private-bus tests leave socket warnings. These are separate follow-ups, not
  silently counted as warning-free validation. See `resource-diagnostics.log`.

## Remaining work

Continue the comprehensive audit with real isolated end-to-end runs, interrupted
daemon/transport operations and resource-pressure tests. In particular, the
filesystem/SQLite crash window for installed-Lab updates needs a separate durable
recovery design; this patch covers reported storage exceptions and normal rollback,
not sudden power loss. Do not claim that every backend defect has been eliminated.
