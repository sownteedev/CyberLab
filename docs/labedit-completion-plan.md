# Labedit Completion Plan

Status: October 25, 2026. Target: Labtainer/Labedit authoring workflows in
CyberLab Studio, not merely a Checkwork button or a screen full of saved fields.
The development source and installed app are separate acceptance targets.
The installed package version was read as 0.9.0; this work has not deployed the
new assessment features.

## Reference and scope

The feature inventory uses the Labtainer Lab Designer guide and Labedit Java
models from the user-provided `labtainer-analysis.tar.gz`. It covers container
configuration, network configuration, parameterization, artifacts/results,
goals, quizzes, delivery and author verification. It does not establish that
this local archive is the latest upstream revision.

Architecture stays Studio/CLI -> System D-Bus -> cyberlabd -> Engine -> Docker.
No GUI/CLI Docker access, new transport, user roles, runtime upgrade or production
catalog changes are part of these milestones. Every allowed user can author a
private draft and publish through the reviewed API.

## Milestones, in order

### 1. Finish the safe local Checkwork foundation

Implemented in source: declared workspace evidence; bounded Results; group,
scalar comparison and snapshot-count Goals; report history; immutable evidence
export; Quiz feedback; typed parameters, unique-random/hash/multi-target
operations, and two-phase submit-and-finish through Engine/API/CLI/Studio.
Submission checkpoints and reports commit together; failed exports do not stop
practice, and finalization rejects intervening Session/workspace/Quiz changes.
See `docs/checkwork-and-quiz.md` for exact recovery and capture bounds.

Recent integration fixes cover metadata disclosure, missing evidence vs capture
errors, integer coercion, regex resource bounds, parameter expansion and editor
type/reference transitions. These are independently tested and tested together
through the actual CLI/private D-Bus with a memory runtime.

Dependency cycles are now checked at the runtime-policy boundary. Still required
before release: retain explicitly reviewed CPU/RAM ceilings, validate
extra-host addresses against attached private topology and resolve all network
parameter tokens before policy checks. A schema field alone is not permission
to widen the Docker security policy.

Exit gate: a temporary authored Lab can be saved, validated, started, checked,
exported, stopped, saved/resumed and reset without corrupting references or
misreporting runtime failure as learner failure. Every test process is reaped.

### 2. Complete parameter authoring and real terminal grouping

- Add bounded unique-random allocation, shared generated values across selected
  seed targets, and generated-value references in Goals. Specify repeatability
  on reset/resume, range exhaustion and collision errors before implementation.
- Define container clone semantics before offering `CLONE_REPLACE`; do not
  substitute Lab cloning for runtime container cloning.
- Implement terminal groups as actual tabs/windows, not title prefixes. Keep
  node/slot ownership, reopen/close tracking and exact-instance cleanup.
- Keep definition/import compatibility distinct from similar UI labels.

Unique-random, multi-target/generated values and Konsole tab-file grouping now
exist in source; do not repeat their implementation. Container-clone semantics,
network parameter validation and real-Docker/installed acceptance remain open.

Exit gate: one authored configuration produces the same validated values after
reset and resume, rejects impossible uniqueness ranges, and opens/closes exactly
its declared terminal groups without affecting another Session.

### 3. Add the missing evidence/time model for advanced Goals

Labtainer Results can contain timestamped activity from multiple program
invocations; current CyberLab captures one workspace snapshot. Implementing
`matchany`, `matchlast`, `matchacross`, temporal relations or event counts requires
explicit bounded event records, provenance, timestamps and retention semantics.

Design capture first, then typed extraction, then comparison/boolean/temporal
Goals. Keep the distinction between capture time and actual event time. Do not
pretend that repeatedly checking files records program execution history.

Only approved workspace evidence is in scope. Shell instrumentation, system
logs, `execute`/pregrade hooks or arbitrary commands require a separate reviewed
policy decision; no silent script runner or Session agent is introduced.

Exit gate: documented multi-event fixtures prove temporal operators, missing
events, repeated invocations and deterministic report replay from stored data.

### 4. Complete Quiz and offline submission review

The first bounded batch-review slice is implemented in the development source.
`review-submissions` accepts exported packages through the shared D-Bus method,
verifies each package independently, reports malformed/duplicate inputs and
never renders or executes submitted content. It is a local review summary, not
an authenticated instructor grader.

- In-Session Quiz parity is implemented in source: named groups, prefaces,
  True/False items, right/wrong feedback, and earlier-question prerequisites.
  Preserve attempts without overwriting unsaved answers.
- Library Quiz and optional pre-start questions now have an independent,
  owner/revision-scoped lifecycle, bounded persistence and Engine start gating.
  The former loader dropped the stored flag; that is fixed. Completion is distinct
  from correctness. See `docs/lab-quiz.md`; installed acceptance remains open.
- Add bounded import and batch summaries for exported submissions. Verify the
  package manifest and show report/Lab revision identity; do not trust embedded
  HTML/scripts or confuse local self-check with authenticated grading.
- Keep evidence immutable and export the selected historical report, not a new
  live capture. Add no teacher/student account split.

Exit gate: a user can answer, revisit and export; another local review workflow
can inspect multiple bounded packages, including malformed/repeated packages,
without changing Labs or Sessions.

### 5. Add offline Lab-package exchange and author scenarios

The Labtainer converter now uses strict, bounded source parsers rather than
silently substituting BusyBox, changing paths or approximating temporal goals.
It retains supported terminal slots/groups, home files/directories, parameters
and multiline Quiz groups, with a persistent review report and missing runtime
fields that must be configured before publication. Unsupported syntax fails
before draft creation. This corrects false compatibility; it does not complete
the full importer, event model, cloning or image-delivery requirements.
See `docs/lab-packages.md` for the exact supported and pending semantics.

The bounded `.cyberlab` exchange slice is implemented in the development
source and wired into Studio Library controls (`ImportLabPackagePicker`,
`ExportLabPackagePicker`, `SubmissionReviewDialog`). `ExportLabPackage`,
`ExportDraftPackage`, `ImportLabPackage` and `ReviewSubmissions` use the shared
System D-Bus API; CLI and Studio round trips are covered with a private daemon,
temporary fixture catalog and offscreen verification. The package carries
declarative definitions, approved image references and bounded assets, never
Docker images or host privileges. Studio exchange flows preserve unsaved editor
work. Destination real-Docker/image acceptance remains release work.

- Export a bounded Lab definition, documentation, assets and approved image
  references. Images remain preloaded/admin-approved; Docker Hub is optional.
- Import into a private draft, validate and review before publishing or updating.
  Reject traversal, links, oversize input and silent overwrite; preserve exact
  revision/digest checks and existing Session snapshots.
- Add a reproducible author scenario runner over supported API operations. Use
  isolated temporary Sessions, bounded steps and exact cleanup. Do not expose
  arbitrary privileged command execution under a "test" label.

Exit gate: export/import preserves the reviewed content; stale updates fail;
an author scenario detects a deliberate failure and leaves unrelated work intact.

### 6. Resolve incompatible options, then release

Explicit pending decisions: arbitrary system-file provisioning and services,
startup/grading/build scripts, unrestricted image builds, password provisioning,
router capabilities, TAP/MACVLAN, host mounts and external networking. These
cannot be marked supported under the current policy. Show unsupported choices
as such, rather than storing options that do nothing.

Release gates: complete regression; isolated real-Docker acceptance using only
reviewed images; offscreen Studio verification; all allowed users' Sessions
STOPPED; guarded wheel update with backup/rollback and recorded artifact;
installed capability checks; manual acceptance in the user's main Studio.
OVA export and a fresh VMware import are subsequent delivery checks, not proof
that missing authoring features have been implemented.

## Definition of completion

For every row in `docs/labedit-parity.md`, record declaration, validation, engine
behavior, shared API/CLI access, Studio controls and evidence of verification.
Unsupported policy-conflicting features remain explicit open decisions. Passing
unit tests, building a wheel or showing a button does not complete parity.
