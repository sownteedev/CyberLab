# Software Image Lifecycle Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Reuse prepared software images for identical Lab revisions, clean up only unreferenced images, and keep Session startup from creating image copies.

**Architecture:** A prepared software image remains immutable and is keyed by the exact software specification and Ubuntu base. Sessions use that image directly and create only temporary containers. The authoring store supplies protected image references so garbage collection can remove stale cache entries without touching saved Labs, drafts, active Sessions, or running preparation jobs.

**Tech Stack:** Python engine/daemon, Docker SDK, SQLite preparation store, isolated unittest fixtures.

## Global Constraints

- Keep the Quickshell -> CLI -> cyberlabd -> engine -> Docker architecture.
- Never mutate or delete an image referenced by a saved Lab, draft, active Session, or active preparation.
- Never run Lab containers as `privileged` and never expose the Docker socket to Labs.
- Do not modify the production catalog or user drafts as test fixtures.
- Preserve exact software fingerprint and revision validation.

## Review Focus

- Identical software specs reuse one verified image instead of rebuilding it.
- Changed specs create one new image while the old one remains protected only when referenced.
- Stopped/failed Sessions release runtime references and their temporary containers are removed.
- Garbage collection is bounded, idempotent, and never deletes protected images.
- Storage-full errors distinguish quota exhaustion from physical Docker disk exhaustion.

### Task 1: Reference inventory and safe garbage collection

**Files:**
- Modify: `engine/cyberlab/authoring/software.py`
- Modify: `engine/cyberlab/runtime/software.py`
- Test: `tools/check_software.py`

- [x] Add a protected-image inventory from the preparation database and authoring snapshots.
- [x] Add a bounded cleanup operation that removes only unreferenced prepared images and stale receipts.
- [x] Add tests for protected saved revisions, active jobs, idempotent cleanup, and stale images.

### Task 2: Preparation quota and reuse behavior

**Files:**
- Modify: `engine/cyberlab/authoring/software.py`
- Modify: `engine/cyberlab/runtime/software.py`
- Test: `tools/check_auto_software.py`, `tools/check_software.py`

- [x] Reuse a verified image for the exact software fingerprint/base pair.
- [x] Run safe cleanup before rejecting a full quota.
- [ ] Keep the image immutable and report actual quota usage plus cleanup result (immutability retained; quota accounting/reporting still needs review).

### Task 3: Session lifecycle cleanup

**Files:**
- Modify: `engine/cyberlab/runtime/docker.py`
- Modify: `engine/cyberlab/service.py`
- Test: `tools/check_workstations.py`, `tools/check_session_state.py`

- [x] Ensure Session stop/reset removes containers and networks but not protected prepared images.
- [x] Ensure restarting a Lab does not create a duplicate software image.
- [x] Add regression coverage for repeated start/stop and changed software revisions.

### Task 4: User-facing storage status

**Files:**
- Modify: `engine/cyberlab/authoring/software.py`
- Modify: `daemon/cyberlabd/authoring.py`
- Modify: `ui/studio/views/editor/NodePackagePicker.qml`
- Modify: `ui/studio/models/Messages.js`
- Test: `tools/check_notifications.py`, `ui/studio/testing/SoftwareEditorTest.qml`

- [ ] Replace the vague storage error with quota/physical-disk wording and an actionable cleanup path.
- [ ] Keep all errors as popup notifications without duplicate inline errors.

### Task 5: Documentation and full verification

**Files:**
- Modify: `docs/software-preparation.md`
- Modify: `docs/checkwork-and-quiz.md` only if lifecycle behavior is referenced.

- [x] Document image reuse, reference protection, cleanup, and Session restart behavior.
- [ ] Run backend, UI, lint, and diff checks; record any Docker privilege limitation.

## Follow-up verification, 2026-11-22

- Added failing regressions before fixing stale READY/FAILED job retention,
  automatic-image reuse for declarative drafts, multi-node preparation leases,
  disabled-Ubuntu cleanup, and checkpoint-definition validation before capture.
- Keep current software fingerprint/base cache entries for drafts and published
  Labs even when their declarations contain no explicit image ID. Preserve
  temporary image references until the Engine accepts the prepared Session.
- Serialize image collection with publication/draft snapshots, skip collection
  during an active build, and never wait for a build while stopping a Session.
- Reject checkpoint images in software collection even if they inherit software
  labels. Use non-forced removal without recursively pruning parent images.
- Startup collection failures are logged rather than preventing daemon startup.
- Backend verification: software 29, automatic startup 34, session state 23,
  workstation/checkpoints 31. Software UI: 32 offscreen tests passed.
- Runtime verification is still blocked: the current process has NoNewPrivs=1
  and Docker returns permission denied. No authentication bypass, image deletion,
  production catalog changes, or installed-runtime deployment was performed.
- Shared-layer accounting now counts a verified layer chain once, with a
  conservative full-size fallback when Docker history cannot be verified.
  Both software preparation and checkpoint capture use this accounting.
- Remaining: check the complete lifecycle and layer accounting on real Docker,
  and deploy using the guarded updater only when Session/editor safeguards and
  administrator access permit. The earlier GUI acceptance is not evidence for
  these new lifecycle changes.

## Packaging verification, 2026-11-22

- Fresh isolated checks passed: image storage 8, software 33, automatic startup
  38, session state 23, workstation/checkpoints 33; 285 static Vietnamese
  message checks passed. Software editor UI: 32 offscreen tests passed.
  `git diff --check` passed.
- Resolved the build-tool blocker without installing dependencies or changing
  the system: the host Python already has setuptools 84.2.1 and wheel 0.48.0.
  Built with `/usr/bin/python -m pip wheel . --no-build-isolation --no-deps
  --wheel-dir /tmp/cyberlab-lifecycle-wheel`.
- Artifact: `/tmp/cyberlab-lifecycle-wheel/cyberlab_engine-0.9.0-py3-none-any.whl`.
  SHA-256: `485dabfbc5056f6bfea74f2ec26a761c2d31cd2ce25e59aabbbfccc7c024f4af`.
  All 271 Python/QML/JavaScript source assets compared byte-for-byte with the
  wheel. This artifact is built, not installed.
- Docker access was rechecked and still returns permission denied; the process
  has `NoNewPrivs: 1`. No privilege bypass or deployment was attempted.

## User-run Docker acceptance, 2026-11-22

- The user supplied terminal output from the real-Docker acceptance command:
  terminal capture groups, non-root ICMP capture between nodes, sandboxed
  Firefox, save/resume isolation, repeated checkpoint replacement and repeated
  start/reset without software image growth all reported PASS. Fixture cleanup
  reported completion. This is user-provided runtime evidence, not a direct
  Docker run by the agent; the supplied excerpt does not measure startup time.
- Two checkpoint-removal warnings occurred before the final lifecycle PASS.
  The test asserts the old checkpoint set is replaced after repeated save and
  no checkpoint images remain after reset. The warnings therefore did not
  cause retained checkpoint images at those verified boundaries. Their exact
  underlying Docker exceptions are not included in this output.
- Rechecked the build: all 271 code assets still match the wheel listed above.
  Installation and installed-runtime acceptance remain pending; the agent
  process still cannot elevate privileges (`NoNewPrivs: 1`).

## Guarded updater readiness correction, 2026-11-22

- The user-run upgrade failed on `cyberlab info`. Service logs and the retained
  failed-venv directory show that installation reached restart and rolled back,
  rather than failing at the initial preflight. The restored daemon currently
  answers `info` successfully. Preserve `/var/tmp/cyberlab-runtime-backup-gostj_3u`.
- Confirmed a readiness race: the Type=dbus service acquires its bus name before
  runtime cleanup and API-handler registration, but the updater queried `info`
  immediately after systemctl start. The original subprocess stderr was hidden,
  so the exact exception in that failed run cannot be recovered from its output.
- The updater now waits with bounded read-only `info` probes while the service
  is active, and reports captured subprocess diagnostics on failure. It never
  retries a mutating operation. Existing rollback and Session guards remain.
- Eight isolated updater regressions and 33 native-display checks passed;
  `git diff --check` passed. Retry the guarded update with the same verified
  wheel: this fix is to the repository updater, not the packaged runtime.
