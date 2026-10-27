# Checkwork and Quiz

These features are implemented in the development source. They have not been
deployed to the installed runtime. This is local practice feedback, not an
authenticated examination or an anti-cheating system. The complete Labedit
parity backlog remains in `docs/labedit-parity.md`.

## Shared API and Studio

Studio uses the same unprivileged CLI and System D-Bus API as terminal users.
No UI component runs Docker or privileged commands. Authoring declarations
remain in the versioned Lab definition; Session work and reports are separate
from the catalog template.

```text
cyberlab checkwork SESSION
cyberlab reports [SESSION]
cyberlab report REPORT
cyberlab export-submission REPORT NEW_OUTPUT.zip
cyberlab submit SESSION NEW_OUTPUT.zip
cyberlab finish-submission SESSION REPORT --yes
cyberlab review-submissions FILE [FILE ...]
cyberlab delete-report REPORT --yes
cyberlab quiz SESSION --answer question-id=0 --answer another-id=1
cyberlab quiz-result SESSION
cyberlab lab-quiz LAB
cyberlab lab-quiz LAB --digest REVIEWED_DIGEST --answer question-id=0
cyberlab delete-lab-quiz LAB --yes
```

Quiz option indexes are zero-based in the API/CLI. Studio presents labeled
choices. The latest submission replaces only that Session's previous attempt.
Unknown questions, duplicate CLI question IDs and invalid option indexes are
rejected without changing the saved attempt. A missing attempt is `{}` through
the CLI. Normal Lab/Session metadata omits answer keys and authored feedback;
feedback is returned after submitting.

Quiz definitions support the legacy single `quiz` list and the Labedit-style
`quizzes` list of up to eight named groups. Each group can contain `preface`,
multiple-choice (`choice`) and `true_false` items. True/False is represented in
the public Session view as the two choices `Sai` and `Đúng`, while the answer
key remains daemon-private. Questions can declare an earlier question as a
`prerequisite`; a prerequisite that was answered correctly causes the dependent
question to be marked `SKIPPED`. Prerequisites are local to one group and may
not point forward or to a preface.

Studio separates `QuizService`, `QuizDialog` and `QuizQuestionCard`. Closing,
reopening or switching Sessions invalidates outstanding callbacks. A late saved
answer never overwrites edits made while loading. Submission disables editing
until the response arrives. The dialog restores its opening control's focus.
When a Lab has multiple Quiz groups, Studio presents a group selector while a
single submission still preserves the answers for all groups in that Session.

Library Quiz also works without a running Session. Optional `pre_start` groups
must be completed before a new Start, enforced by the Engine on both CLI and
Studio paths. Completion requires answers, not a perfect score. Attempts are
owner-scoped, bounded and tied to the exact Lab package digest; they survive
daemon restart independently of Sessions. Preparation answers are copied into
the new Session without allowing later Library edits to rewrite that copy.
See `docs/lab-quiz.md` for the shared API, revision guards and lifecycle rules.

The parameter-start dialog distinguishes an omitted override (use the authored
default, otherwise generate) from an explicit empty text value. Integer, choice,
boolean and UTF-8 size checks run in both the client and engine; the engine is
authoritative. A field's reset button removes its override, not its declaration.

## Submit and finish

The source capability `submit-and-finish` exposes `PrepareSubmission` and
`FinalizeSubmission` on the shared daemon API. Studio's practice screen offers
**Nop va ket thuc** with a local save picker and explicit confirmation. It uses
`cyberlab submit SESSION NEW_OUTPUT.zip`; the UI never reads Docker or writes
the catalog. The CLI closes only the selected Session's tracked terminals after
the daemon confirms `STOPPED`.

Preparation captures every node's bounded workspace once, freezes the current
Quiz attempt, and saves a resumable checkpoint and immutable report in one
database transaction. Evidence export contains only authored artifact paths,
not every file in that checkpoint. Missing/unsafe required artifacts, capture
failure, archive limits or storage quota failure prevent preparation without
stopping the Session or partially replacing its existing checkpoint/report.
Failing a learning goal does not prevent submission. A Lab with Checkwork
disabled can submit declared evidence without evaluating or exposing its
Results/Goals; its report is `NO_CRITERIA`.

The CLI exports that exact report, writes a private temporary file, fsyncs it,
links it to a new output name without overwriting any existing file/symlink,
and fsyncs the destination directory before requesting finalization. Failed
export never requests a stop. A failed directory fsync can leave a complete
output file, but still does not finalize automatically. The saved checkpoint
and report remain available when writing the user's output fails.

Finalization requires the same owner, Session generation, prepared report,
Quiz attempt and workspace contents/permissions. It rechecks all node
workspaces, including files not exported as evidence. An intervening save,
reset, resume, discard, new preparation, Quiz edit, changed workspace or daemon
restart invalidates automatic completion. Ordinary Checkwork reports are not
finish tickets. Removal/retention eviction of a prepared report also refuses
finalization. Only one current prepared ticket is retained per Session; tickets
are bounded by Session history and are not recovered after daemon restart.

A failed stop preserves the checkpoint and exported file. The CLI prints the
report identity and recovery command `finish-submission SESSION REPORT --yes`.
Use it only after verifying that the exported file was saved. It retries only
that prepared cleanup and is idempotent after confirmed completion; stale
tickets cannot stop a newer Session incarnation. If the daemon restarted,
resume the saved practice and prepare a new submission instead. Exported
packages and Checkwork reports remain readable independently of these tickets.

This is not a distributed transaction with the user's filesystem: the daemon
trusts an authorized client's finalization acknowledgement. Nor is capture an
atomic freeze across containers or background processes. Stop editing and
quiesce workspace writers before submitting. The second content comparison
detects intervening edits but cannot prove that no background write occurred
after a node's final read. These bounds are the same workspace-only persistence
limits documented in `saved-practice.md`; no process-memory or whole-image
checkpoint is implied.

## Check conditions and regex bounds

Built-in checks cover existence, text inclusion/equality, matching lines,
file-size comparisons, line/substring counts, SHA-256, MD5, field extraction and
regex. Goals combine conditions with `all`/`any`, compare captured values or
count passing Results in the current snapshot. Full semantics and remaining
Labtainer gaps are documented in `docs/results-goals-parity.md`. Only declared
workspace data is used; links and special files are not accepted as evidence.
Text input is limited to 64 KiB.

Regex is never evaluated in the daemon process. A fixed internal Python module
receives bounded JSON through pipes and returns a status and bounded selected
value where needed. It runs with
isolated Python import handling, at most 128 MiB address space, one CPU second,
no core/file output, and at most one wall-clock second. The parent kills and
reaps a timed-out worker. All regex conditions in one report share a five-second
budget. These limits are independent from workspace-capture limits and do not
claim that the whole multi-container capture is atomic.

Invalid syntax, deadline/resource failure or an unavailable worker produce an
`ERROR`, not a learner `FAIL`. Later ordinary file checks still run. This is not
a general script executor or a new public IPC protocol. Python regex semantics
are supported within these bounds, including groups, escapes and lookarounds.

## Quiz persistence and evidence

- One latest attempt per Session, at most 256 KiB per attempt.
- At most 100 attempts / 8 MiB per owner and 250 attempts / 32 MiB overall.
- Replacement checks quotas transactionally without counting the old row twice;
  capacity failure preserves it and never evicts another user's attempt.
- Stop preserves the latest attempt while that Session remains in history.
- Save/suspend/resume preserves it across daemon restarts with the checkpoint.
- Destructive reset clears the latest attempt along with the practice checkpoint.
- Removing stopped Session history or deleting its Lab clears the associated
  latest attempt. At daemon startup, attempts without any saved Session row
  are removed; saved rows retained for corruption recovery protect their quiz.
- Checkwork reports are independent, immutable history. Their embedded Quiz
  remains available even after reset or transient Session history disappears.

Checkwork freezes the latest Quiz result when capture begins. Session mutations,
including Quiz submission, are rejected while that capture is in progress.
Export reuses stored data rather than recollecting a newer answer. A submission
contains `manifest.json`, `checkwork.json`, `report.html`, declared artifacts and,
when present, `quiz.json` and packaged instructions. HTML escapes authored text.
The Quiz timestamp is separate from the file-capture timestamp. Passing Quiz
does not implicitly make the workspace goals pass, or vice versa.

## Verification scope

`tests/test_submission_lifecycle.py` checks exact-capture ownership, stale
tickets, changed evidence/Quiz, atomic quota rollback, cleanup retry,
restart/resume and concurrency guards. `tests/test_submission_cli.py` checks
no-overwrite/fsync failure, recovery messages, scoped terminal cleanup and a
real CLI/private-D-Bus round trip. `tests/test_studio_submission.py` exercises
capability gates, cancellation/focus, confirmation and real CLI submission
offscreen at 1024x700 and 1280x820. `tools/accept_docker_runtime.py` includes the
same submission/export/resume lifecycle on its isolated approved-image fixture;
adding that gate does not mean the real-Docker run has passed.

`tests/test_regex_check.py` exercises real workers, pathological patterns,
process reaping, shared deadlines and failure reporting. `tests/test_quiz.py`
covers ownership, quotas, lifecycle, immutable captured results, prefaces,
True/False feedback and prerequisite skipping.

`tests/test_labedit_integration.py` launches an isolated D-Bus and the real daemon
with its memory runtime and temporary fixture catalog. It exercises actual CLI
serialization, private metadata, empty overrides, Quiz, Checkwork/ZIP export,
checkpoint/restart/resume and daemon responsiveness after a regex timeout. Its
offscreen Studio scenarios click real controls and use the actual CLI/backend
at 1024x700 and 1280x820. `tests/test_studio_quiz_service.py` additionally checks
stale callbacks, value bounds and switching between Quiz groups. Exact test
process groups are cleaned up.

This does not substitute for real-Docker, installed-wheel or user acceptance.
Do not use the production catalog for verification. Deployment requires STOPPED
Sessions, the guarded updater's backup/rollback path and installed verification.

`review-submissions` is a bounded, read-only offline summary for exported
reports. It verifies the package format and report identity, returns one result
per input (including malformed packages), detects duplicate report IDs and
counts passed goals/results. It never renders submitted HTML, executes files,
changes Labs/Sessions, or claims authenticated instructor grading.
