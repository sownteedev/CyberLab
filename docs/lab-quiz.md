# Library Quiz and Preparation

Implemented in development source on October 25, 2026. Installed-runtime and
real-Docker acceptance remain separate release gates. The local Labtainer
Designer guide's Quizzes section describes quizzes on the VM host, independent
of running containers. CyberLab now provides that workflow in the Library;
it does not claim that Labtainer itself requires a passing quiz before start.

## Authoring and learner workflow

The existing `quizzes[].pre_start` flag in Labedit now has runtime behavior.
The loader preserves it on the immutable question model; the earlier duplicate
model construction accidentally discarded it. Legacy `quiz` definitions remain
optional in-Session quizzes, and all quiz groups can also be answered from the
Library without starting a Session.

The Library Quiz button opens the shared learner dialog. The user can select
groups, answer, submit, reopen and forget the saved answers after confirmation.
Opening or submitting never starts Docker or reserves a Session. Question text
is plain text; metadata excludes answer keys and feedback until submission.
Every allowed user can use this workflow; it adds no instructor/student roles.

When a Lab declares preparation questions, Start opens only the preparation
groups before the parameter dialog. Continue requires a saved, completed
preparation attempt. An edit invalidates the displayed completion until it is
saved again. Closing the dialog, Escape or cancellation never starts a Lab.
Generation guards reject replies from a previous Lab, Session or closed dialog.

Completion means every applicable preparation question has an answer, including
ungraded questions. A question skipped because its earlier prerequisite was
correct needs no answer. A wrong answer can still complete preparation: this is
local concept practice, not a pass-score gate or anti-cheating mechanism.
Prefaces alone do not gate Start. Optional later groups need not be completed.
`passed` continues to mean all graded questions are correct; `completed` and
`pre_start_completed` are separate flags.

## Shared API

The `lab-quiz` capability requires enabled practice storage. All calls use the
same System D-Bus service as existing Session Quiz operations:

- `GetLabQuiz(s) -> s`: Lab ID to JSON containing public questions, title,
  `lab_digest`, `pre_start_required` and this caller's latest matching attempt.
- `SubmitLabQuiz(sss) -> s`: Lab ID, reviewed digest and answers JSON to a saved
  report. The daemon checks the exact current package revision, not just version.
- `DeleteLabQuizAttempt(s) -> b`: forget only this caller's Lab-level answers.

```text
cyberlab lab-quiz LAB
cyberlab lab-quiz LAB --digest DIGEST_FROM_READ --answer question-id=1
cyberlab delete-lab-quiz LAB --yes
```

Indexes remain zero-based. Submitting requires the digest from the read response,
even when submitting no answers. Unknown IDs, duplicate CLI IDs, non-integer or
out-of-range options and oversized requests fail without replacing an attempt.
`StartLab` and `StartLabWithParameters` both enforce preparation in the Engine,
before runtime creation. Calling the CLI directly cannot bypass it. A missing
attempt raises the typed `QuizRequired` D-Bus error; a stale quiz submission
raises `Conflict`. Disabled storage cannot bypass a declared preparation gate.

## Persistence and identity

Practice database schema 7 adds `lab_quiz_attempts` without changing existing
Session attempts, saved workspaces or Checkwork reports. The new store retains
one latest attempt per `(Lab ID, owner UID)`, with its exact package digest.
The digest includes definition and assets, so same-version edits invalidate old
completion. Reads never expose another owner's attempt, even to UID 0 through
this learner API. A new matching attempt replaces only that owner's prior Lab
attempt. Stale attempts stay recoverable until replaced or explicitly forgotten.

Limits for this store: 256 KiB per payload, 100 attempts / 8 MiB per user,
250 attempts / 32 MiB globally. Count/byte checks and replacement occur in one
transaction. Failure preserves the previous attempt; capacity never evicts
another user's answers. These quotas are separate from the existing Session
Quiz quotas. Daemon restart and stopped-Session retention do not remove Lab
attempts. Explicit Lab deletion removes only that Lab's preparation attempts.

At Start, the exact preparation answers are copied into the new Session Quiz
attempt, retaining their original timestamp, package digest and `pre-start`
source. Quota failure prevents runtime creation. Later Library edits/forgetting
cannot rewrite this copy, a Checkwork capture or an exported `quiz.json`.
Optional Library answers are not silently copied into a practice Session.
Existing Session Quiz submission can replace its own attempt as before.

Resume uses the saved Session's captured revision and does not run preparation
again. Destructive reset clears the Session Quiz attempt but not the independent
Library attempt. These operations are not a new Lab start. Runtime readiness
checks for authors continue to validate containers without a learner quiz gate.

## Verification

- `tests/test_lab_quiz.py`: completion vs correctness, prerequisites, ungraded
  questions, owner isolation, exact revisions, quota rollback, migration, restart,
  immutable Session/report copies, authorization and request bounds.
- `tests/test_lab_quiz_integration.py`: actual CLI/private-D-Bus round trips,
  restart and stale revision rejection; rendered Library, cancel/focus, preparation
  and Start flow at 1024x700 dark and 1280x820 light using only the memory runtime.
- `tests/test_studio_quiz_service.py`: cross-Lab/Session callbacks, preserving
  answers for other groups, unsaved edits, failed requests and confirmed forget.

Automated checks use temporary fixture catalogs, isolated databases and offscreen
Studio process groups. No production catalog is modified. A separate bounded
multiline/multi-file Quiz importer is documented in `docs/lab-packages.md`.
Temporal assessment, container cloning, complete Labtainer conversion and the
other parity backlog are not completed by this feature.
