# Checkwork audit - November 24, 2026

> **Tài liệu lịch sử.** Trạng thái và lệnh bên dưới thuộc lần ghi nhận này,
> không thay thế [hướng dẫn hiện hành](../../README.md).

## Scope and preservation

This is a source-only audit/fix of the existing local Checkwork implementation,
not a new assessment architecture, deployment or full Labedit completion claim.
The root `AGENTS.md` and the Checkwork foundation in
`docs/archive/plans/labedit-completion-plan.md` were read. The explicit ownership limits for
this task supersede standing development-deployment approval.

Changes made in this slice:

- `engine/cyberlab/assessment_goals.py`: resolve group/count dependencies against
  both captured Results and already evaluated Goals.
- `tools/tests/unit/check_checkwork_regression.py`: new isolated regression suite.
- `docs/archive/reviews/checkwork-audit-2026-11-24.md`: this evidence and integration record.

Existing edits to `assessment.py`, `assessment_checks.py`, the remaining
`assessment_goals.py` code and `service.py` are preserved. In particular,
collection-aware aggregate status, collection/extraction support and digest
normalization were already present; they are not changes delivered by this
slice. `tools/tests/unit/check_assessment_quiz.py` is unchanged. No commits, staging,
production-catalog writes, system-file writes, installations, Docker operations
or production daemon calls were performed. Test packages, stores, dependencies
and logs are temporary; private-bus tests use MemoryRuntime.

## Confirmed bug and minimal fix

The loader accepts earlier Goal IDs in group/count `results` dependencies.
`evaluate()` already supplies `goals_by_id` in declaration order. Boolean goals
consult that map, but group/count goals previously looked only in the captured
Results map. Thus a valid dependency on a passing or failing earlier Goal became
`ERROR`, and downstream Boolean goals inherited that error.

Before changing implementation, the new regression suite reproduced four
failing subcases: group and count dependencies, each with PASS and FAIL inputs.
The observed Goal status chains were respectively `[PASS, ERROR, ERROR]` and
`[FAIL, ERROR, ERROR]`. ERROR inputs were already propagated correctly.

`check_goal()` now creates a local combined condition map and uses it for the
two status-based dependency lookups. No caller/input mutation, new operators,
sorting or dependency-graph implementation was added. Comparison goals still
read Result values only. Existing three-valued/decisive all/any/count semantics
remain unchanged. The loader still rejects undefined, forward and cyclic
dependencies; assessment IDs remain unique across declarations.

## Targeted coverage

The new suite has 26 tests, using the real loader/evaluator and, for integration,
the existing Engine with MemoryRuntime and temporary SQLite report storage:

- Result without a Goal: correct, wrong and absent files produce PASS, FAIL and
  FAIL. Capture absence/failure is ERROR, not learner failure.
- Scalar collect-only reports remain COLLECTED, not PASS; mixed collected and
  graded Results retain the graded status. No criteria produces NO_CRITERIA.
- Evidence readiness remains separate from grading: required/optional missing
  artifacts and capture failures retain their respective statuses.
- `assess=False` omits Results/Goals but still collects declared artifacts.
- Comparisons test correct/wrong/missing selected values, invalid UTF-8,
  noninteger/out-of-range evidence, and captured values whose independent
  Result condition failed.
- Unsafe/duplicate paths, links, non-file evidence, oversized text and regex
  errors propagate to Results, Goals and aggregate status.
- Group/count/Boolean chains, mixed Result/Goal dependencies, count values,
  decisive unknown handling and invalid dependency rejection are covered.
- Repeated evaluations and checks move from error/wrong to correct to missing
  evidence without mutating inputs or overwriting earlier saved reports.
- Capture reads each referenced node once, skips unreferenced nodes, saves
  owner-scoped reports, removes public evidence payloads, and preserves
  COLLECTED status across storage. Disabled Checkwork rejects capture.
- Mocked capture deadline and unexpected runtime exceptions save no report and
  release the capture guard so a subsequent check can proceed.
- All five aggregate statuses survive report summaries, public reports, HTML,
  ZIP export and submission review without turning ungraded data into PASS.

## Capture service integration

`Engine._capture_report()` in `engine/cyberlab/service.py` was inspected but not
edited. It already captures referenced nodes, records `RuntimeFailure` per
node, calls `evaluate()`, persists the resulting report and releases `_checking`
in `finally`. `evaluate()` already passes earlier Goal reports to `check_goal()`.

**No service.py integration change is required for this fix.** An end-to-end
MemoryRuntime test checks a Result -> group -> group -> count -> Boolean chain
through `Engine.checkwork()` and saved-report retrieval for PASS, FAIL and
ERROR inputs. No report format, daemon method or client API changes are needed.

The runtime workspace adapter was also read: it converts archive validation
errors to `RuntimeFailure`, uses an unprivileged bounded workspace read, and
does not supply arbitrary grading commands. This is inspection, not a claim
that real Docker capture or its timing was exercised. The service's 120-second
budget is checked around synchronous captures; the deadline regression uses a
mocked clock, not a real-time latency measurement.

## Status-consumer audit and main integration handoff

This fix introduces **no new status values**. PASS/FAIL/ERROR, COLLECTED and
NO_CRITERIA were already emitted by the dirty baseline. Read-only callsite audit:

- `engine/cyberlab/session/reports.py:16`: `report_summary()` accepts all five
  report statuses. No persistence migration is needed.
- `engine/cyberlab/submission.py:12`: public reports preserve status;
  `html_report()` renders the escaped raw status; `submission_archive()` keeps
  it in both manifest and Checkwork JSON. Round-trip tests pass for all five.
- `engine/cyberlab/submission_review.py:39`: Result validation accepts COLLECTED;
  Goals remain PASS/FAIL/ERROR. At line 223 the same `assessment_status()` is
  used to validate the aggregate. Only PASS contributes to the passed summary.
- `daemon/cyberlabd/server.py:280` and `cli/cyberlab_cli/main.py:149`: the shared
  CheckWork/report/review paths serialize and deserialize JSON without status
  remapping. `cli/cyberlab_cli/submissions.py:49` uses the prepared report ID,
  not grade status, for export/finalization.
- `ui/studio/services/CheckworkService.qml:31`: stores the returned report
  without status coercion. `ui/studio/models/Checkwork.js:3` labels all existing
  report/artifact statuses; COLLECTED and NO_CRITERIA use neutral description
  icons, not a passing checkmark. A read-only Node VM check verified all seven
  report/artifact label mappings and neutral ungraded icons.
- `ui/studio/views/practice/CheckworkDetails.qml:24` uses those shared mappings
  for report/criterion badges, history and artifact labels. Evidence readiness
  remains a distinct control/message from grading.

**Existing UI gap for the main owner (not changed here):**
`ui/studio/views/practice/SubmissionReviewRow.qml:27` and line 28 render every
valid non-PASS report with a warning color/icon, including COLLECTED and
NO_CRITERIA; line 57 displays the raw status token instead of the shared label.
For status-consistent review, import `../../models/Checkwork.js` and use
`Checks.statusText()` for the label; give COLLECTED/NO_CRITERIA a neutral
description icon/color, PASS success, FAIL warning and ERROR error (invalid
archives remain errors). Do not equate `valid` with a passing grade.
Add row-level rendering tests for PASS, FAIL, ERROR, COLLECTED, NO_CRITERIA and
invalid packages in the owning UI slice. The review's Result passed/total count
also includes collected values in the total; do not describe that as a learner
score without separately distinguishing graded and collected Results.
No `service.py`, API, schema, or report-storage integration is needed for the
engine dependency fix. This UI finding is a pre-existing consumer presentation
gap, not a new enum incompatibility caused by this slice.

## Verification results

Python commands used a temporary dependency environment:
`/tmp/cyberlab-checkwork-audit-ni3s5e5q/venv/bin/python -B`.
The final 26-test regression also passed with the main owner's supplied
`/tmp/cyberlab-nov24-venv/bin/python -B`.
Logs, initial owned-file snapshots and index baseline are under
`/tmp/cyberlab-checkwork-audit-ni3s5e5q/`.

| Command after Python prefix | Result |
| --- | --- |
| `tools/tests/unit/check_checkwork_regression.py` | 26 passed after the fix |
| `tools/tests/unit/check_assessment_quiz.py` | 9 passed, before and after |
| `tools/tests/unit/check_result_collection.py` | 14 passed, 1 pre-existing failure, before and after |
| `tools/tests/unit/check_labtainer_compatibility.py` | 14 passed, before and after |
| `tools/tests/unit/check_editing_drafts.py` | 16 passed, before and after |
| `tools/tests/unit/check_session_state.py` | 23 passed, before and after |

The unchanged failure is
`ResultCollectionChecks.test_legacy_extraction_and_digest_unchanged` at
`tools/tests/unit/check_result_collection.py:131`. Its expected digest removes the new
Result `timestamp_type` field but retains node defaults that the existing
`lab_digest()` implementation removes (`setup=None` and empty `system_seed`).
The mismatch was recorded before this slice's implementation edit. Neither
digest behavior nor this out-of-ownership test was changed; its owner should
reconcile the test with the intended compatibility contract.

Additional existing Labedit/UI checks:

- `node tools/tests/ui/check_result_model.cjs`: passed.
- `python -B tools/tests/ui/check_notifications.py --suite assessment`: 12 passed,
  exit 0.
- `python -B tools/tests/ui/check_notifications.py --suite quiz`: 18 passed, exit 0.
- `python -B tools/tests/ui/check_notifications.py --suite labtainer`: 10 passed,
  exit 0.
- `python -B tools/tests/ui/check_notifications.py --suite editor`: 150 assertions/tests
  passed, but the strict wrapper exited 1 on Qt
  `QObject::connect(QJSEngine, QtObject): invalid nullptr parameter` warnings.
- A separate editor run with `--allow-worker-init-warning` recorded 149 passed,
  1 failed: `test_create_from_topic_dialog_preserves_selected_tags`. The first
  run passed that test. This inconsistent UI outcome is outside this slice;
  it is not represented as a clean editor acceptance result.
- A second warning-exempt editor run exited 2: 150 passed, 2 failed,
  `test_create_from_topic_dialog_preserves_selected_tags` and
  `test_difficulty_overview_tracks_loaded_document`. These outcomes are
  recorded without changing UI files or claiming their cause is established.

The historical `tests/test_assessment_*.py` / `tests/test_labedit_*.py` suites
are not present in this checkout. The maintained tools above were run instead;
no archived suite or production Lab was restored to run tests.

## Remaining verification limits

Real Docker capture, hard wall-clock deadlines, concurrent Session replacement,
real system D-Bus, installed-package behavior and manual Studio interaction
were not exercised. Offscreen UI fixtures and MemoryRuntime tests are not
substitutes for those acceptance checks. No deployment is part of this slice.
The broader suite is not fully green because of the recorded digest failure
and editor warning/inconsistent-test outcomes.
