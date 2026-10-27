# Labedit parity work

Product direction updated October 26, 2026: basic Lab management and a compact
authoring workflow take priority over exhaustive parity. This inventory is
retained as reference, not an instruction to expose every feature or implement
all remaining items. See `studio-simple-authoring.md` and the latest approval
in `AGENTS.md`. Existing declarations must remain readable and preserved.

## Objective and reference

The requested end state is Labtainer/Labedit functionality in CyberLab Studio,
not just a Checkwork button. Reference: the upstream Lab Designer, Student and
Instructor guides, MainUI `LabData`/`ParamsData`/`ResultsData`/`GoalsData`
sources, and the local Labtainer archive inspected on October 24, 2026.

Every feature needs declaration, validation, engine behavior, shared D-Bus/CLI,
Studio controls, and verification. A saved field without runtime behavior does
not count as support. Source code has been extended, but the installed runtime
has not been deployed in this work and cannot be claimed to contain these
capabilities yet.

## Inventory

| Area | Current evidence | Status / remaining work |
| --- | --- | --- |
| Library / private drafts / clone / reviewed update / deletion | Existing daemon and Studio workflows | Supported; regression with extended definitions remains |
| Container identity / home files / terminal slots | Restricted runtime, account/home seeding | Existing workflow; aliases, wait_for dependency order, and Konsole tab-file grouping are implemented in source. CPU/memory ceilings remain source-only pending runtime-policy review and Docker acceptance |
| Network addressing | Internal bridges, IPv4/subnet/gateway/DNS; source adds RFC1918 extra hosts | Existing internal-network workflow; new extra-host validation still needs attachment/policy review. Router, per-node routes, TAP/MACVLAN and external connections remain unsupported |
| Parameters | Typed declarations, deterministic seed, public start dialog, token substitution and checkpoint persistence; bounded random, unique-random, hash, multi-target, and clone operations | Source-only; rand_replace_unique, multi-target replacements, generated operation values in goals, CLONE_REPLACE container clone semantics with sequential +CLONE address increments, network parameterization with defaults, and Labtainer format import are implemented and verified. Real-Docker/installed acceptance remains open |
| Results and goals | File/directory existence, bounded UTF-8 text, checksums, counts and field extraction; group, scalar comparison, hash_equal, snapshot count and Kleene boolean goals | Source-only; comparison references, error semantics, hash_equal (MD5/SHA256), boolean expressions with Kleene 3-valued logic, metadata redaction, rendered form transitions and private-D-Bus round trips verified. Timestamped log sets and cross-result temporal goals remain pending |
| Checkwork | Shared D-Bus/API, bounded capture, owner-scoped history, Studio details/history/delete | Source-only local self-check; not a tamper-proof grading system. Full real-Docker and installed-runtime acceptance remains pending |
| Submission / grading | Immutable evidence/Quiz export, read-only batch review, and two-phase submit-and-finish with an atomic workspace checkpoint | Source now has CLI/Studio confirmation, no-overwrite export and stale-capture/owner guards. Real-Docker/installed acceptance, stopped-snapshot rechecking and independent regrading against an exact Lab revision remain pending; no authenticated grader is provided |
| Quiz | Declarative groups, public metadata, Library and Session dialogs, bounded owner/revision-scoped attempts, Engine-enforced preparation | Source supports legacy single quizzes plus Labedit-style groups, prefaces, True/False, right/wrong feedback and earlier-question prerequisites. Library Quiz, independent persistence and actual pre-start completion gates were added on October 25 after finding that the loader discarded the old flag; see docs/lab-quiz.md. Bounded multiline/multi-file Labtainer Quiz import is now implemented and checked against four upstream examples; whole-Lab import and installed acceptance are not complete |
| Container system files / services / hooks | Reviewed image/workspace seeding only | Not supported; arbitrary host scripts, privileged hooks and host mounts are prohibited by policy |
| Image build / registry / no-pull options | Approved local images; no pull at Session start | Offline local execution supported; build/registry workflow remains a separate reviewed feature |
| Labpack / IModule-like delivery | Deterministic bounded `.cyberlab` export/import through daemon, CLI and Studio Library controls | Single-Lab exchange is implemented and verified offscreen. Labpack multi-lab sequences, course-level progress tracking, and Docker-image distribution remain incomplete |
| SimLab-like author verification | Runtime readiness check and editor review | Full reproducible author scenario runner remains pending |
| Labtainer format conversion | Shared ImportLabtainer API, bounded ZIP/TAR/folder reader, strict modular parsers, persistent conversion report | Source now preserves supported terminal/home-file/parameter/Quiz settings and requires explicit image/account review. It rejects unknown directives and unsupported event semantics instead of discarding or approximating them. Full format parity remains incomplete; see docs/lab-packages.md |

## Completed source slices in this phase

- Checkwork capture no longer holds the global Engine lock during runtime I/O;
  Session mutations are guarded while evidence is captured.
- Directory evidence includes descendants and empty directories, rejects links
  and special files, deduplicates export paths, and preserves report/evidence
  pairing through immutable stored reports.
- Report migration is versioned, owner-scoped and bounded by count and bytes;
  global capacity never evicts another user's report.
- Studio has parameter-start, Checkwork/history/export and Quiz flows; Labedit is
  split into reusable settings, parameter, evidence, result, goal and quiz forms.
- Quiz request/state handling is separated from the dialog and question cards;
  generation guards discard stale responses, and an arriving saved attempt
  cannot overwrite newly edited answers. CLI arguments use repeated `--answer`.
- Checkwork evaluates regex only in a short-lived Python worker, with a one-second
  wall deadline, OS CPU/memory limits and a shared five-second regex budget.
  Timeout is an ERROR, not a failed learning objective. No new dependency,
  public transport, arbitrary script runner or daemon service is introduced.
- Results now include safe Labedit-style value extraction: MD5, bounded substring
  counts, token/parenthesis/quote/slash fields, regex groups, and line selectors
  (line number, starts-with, contains, regex, previous-starts-with). Extracted
  values are returned in the immutable report for explainability. The worker
  still owns all regex matching and selector execution; no executable goal,
  shell hook, timestamp archive or host log reader is enabled.
- Quiz attempts are count/byte bounded and follow Session lifecycle. Checkwork
  captures the latest attempt once; later edits/reset never rewrite that report
  or its exported `quiz.json`. See `docs/checkwork-and-quiz.md` for exact semantics.
- `wait_for` is cycle-checked and starts Docker nodes in dependency order;
  aliases and bounded extra hosts are applied to internal Docker networks.
- Konsole tab-file grouping is implemented in source. Resource declarations
  are bounded, but this is not acceptance of higher ceilings under the reviewed
  runtime policy or proof of installed-runtime behavior.
- Submit-and-finish captures all workspaces into a resumable checkpoint and
  saves its report atomically. CLI writes the selected evidence package before
  requesting a guarded stop; Studio exposes a save picker and confirmation.
  Failures preserve running work or its checkpoint and exported file. This is
  workspace-only persistence, not a whole-container freeze; see
  `docs/checkwork-and-quiz.md` for concurrency and recovery limits.

## Immediate implementation sequence

The concrete milestones and acceptance gates are in
`docs/labedit-completion-plan.md`. This inventory is not a declaration of full
Labedit parity or of installed-runtime availability.

1. Finish source integration/validation: approve resource ceilings, extra-host
   network scope, network parameter
   targets/references, and meaningful rendered authoring interactions.
2. Finish compatibility operators for the Labtainer results/parameters formats,
   container-clone semantics, and author scenario verification. Keep these gaps
   visible rather than redefining parity as the current typed subset.
3. Verify installed pre-start Quiz; complete stopped-snapshot assessment and exact-revision
   regrading. Retain real-Docker/installed gates for submission, package exchange
   and batch review even after private-D-Bus/offscreen checks pass.
4. Review policy-conflicting Labtainer options explicitly; do not implement
   password provisioning, host mounts, arbitrary scripts, privileged containers,
   external networking, TAP/MACVLAN or unrestricted image builds implicitly.
5. Run full regression, private-D-Bus/real-Docker acceptance, guarded deployment,
   and manual Studio acceptance only after all allowed Sessions are STOPPED.

## Results/Goals integration follow-up (2026-10-24)

- Fixed quote and first-match line extraction; plain selectors work after the
  shared regex budget expires. Regex groups use one worker; escaped output is
  bounded without truncating JSON.
- Separated goal evaluation and seed operations into focused engine modules.
  Comparisons distinguish missing learner evidence from capture errors, use
  strict integer parsing, and omit answer/selector values from public metadata.
- Seed operations validate direct models, reject directory replacement, avoid
  recursive substitutions and bound aggregate growth before expanding data.
- Studio transitions clear incompatible fields atomically and store displayed
  defaults. Node/result renames preserve references; referenced entries cannot
  be deleted. Parameter operation forms have their own component.
- Added staged, keyboard-driven offscreen form checks at both supported sizes;
  their generated definitions are passed to the real schema/semantic loader.
  Added real-CLI/private-D-Bus authoring/publish/start/checkwork/export/restart
  coverage using only temporary fixture catalogs and the memory runtime.
- See `docs/results-goals-parity.md` and `docs/parameterization.md` for precise
  supported semantics and remaining incompatibilities. Real-Docker acceptance
  and installed deployment remain outstanding.

## Invariants and release gates

- Studio/CLI -> System D-Bus -> `cyberlabd` -> engine -> Docker; no new transport.
- Local self-check is not a tamper-proof examination system or anti-cheat claim.
- Reports describe captured evidence; they are not an atomic snapshot of all
  running processes or all containers. Exports reuse that evidence, not live
  files collected later.
- Only declared workspace files/directories are collected. Do not scrape an
  entire host home, follow links, or implicitly enable privileged scripts.
- History eviction is owner-scoped, count/byte bounded and transactional.
- Runtime and UI verification use fixtures/private D-Bus/offscreen instances,
  never the production catalog. Preserve the user's main Studio and drafts.
- Deployment requires STOPPED Sessions, backup/rollback including databases,
  installed capability verification and a recorded artifact. No deployment of
  an incomplete or unverified UI is implied by a source test pass.
