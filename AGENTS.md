# CyberLab Agent Instructions

CyberLab is a graduation thesis project. Changes must be incremental,
reviewable, documented, and consistent with the agreed architecture.

## Fixed Architecture

CyberLab Studio (Quickshell)
        |
        | System D-Bus
        v
    cyberlabd
        |
        v
 CyberLab Engine
        |
        v
    Docker Engine

The CLI and Quickshell UI must use the same cyberlabd API.

## Component Responsibilities

### engine/
Contains core CyberLab business logic.

The engine must not depend on Quickshell or other GUI components.

### daemon/
Contains cyberlabd.

cyberlabd exposes the privileged CyberLab API through System D-Bus.

### cli/
Contains the CyberLab command-line client.

The CLI communicates with cyberlabd and must not directly control Docker.

### ui/
Contains CyberLab Studio implemented with Quickshell.

The UI must not directly control Docker or execute privileged operations.

### schemas/
Contains versioned CyberLab lab definition schemas.

### labs/
The production catalog lives outside this repository at
`/home/student/CyberLab-labs` (`/home/<user>/CyberLab-labs` on another VM).
The old repository `labs/` is retained only until the administrator completes
the catalog relocation. Do not recreate it afterward.

The external catalog is persistent user data, not a development fixture.
Do not edit, delete, restore examples into, or clean this directory during
development, tests, builds, upgrades, or repository cleanup without explicit
user approval for those particular data changes. Runtime authoring through
the approved daemon API remains the user-controlled way to add Labs.
Tests and UI smoke mode must use `tests/fixtures/labs` and temporary copies,
never the external production catalog.

### tests/
Contains unit and integration tests.
`tests/fixtures/labs/` contains independent sample templates for tests only;
these are not displayed in the user's normal Studio library.

## Security Rules

- Never add the student user to the docker group.
- Never expose /var/run/docker.sock to the student user.
- Never expose the Docker socket to lab containers.
- Quickshell must never invoke Docker directly.
- CLI must never invoke Docker directly.
- Privileged operations must pass through cyberlabd.
- Lab containers must not be privileged by default.
- Host filesystem mounts must be validated by policy.
- Do not commit credentials, API keys, SSH keys, tokens, or secrets.

## Design Rules

- Docker is a runtime implementation detail.
- Docker Compose is not the CyberLab public API.
- Lab definitions must be declarative and versioned.
- A Lab is a template.
- A Session is a running instance of a Lab.
- Keep the engine independent from the user interface.
- Prefer small, testable modules.
- Do not introduce REST APIs, web servers, Unix socket protocols,
  Kubernetes, or session agents unless explicitly approved.

## Development Rules

- Work incrementally.
- Do not generate large amounts of boilerplate without approval.
- Do not modify system files under /etc or /usr directly.
- System installation files must first be added to the repository.
- Add tests for implemented behavior.
- Explain architectural changes before implementing them.
- Do not change the agreed architecture without explicit approval.
- Run automated UI checks offscreen with process-group cleanup. When a visible
  Studio instance is needed for verification, track and close that exact
  instance afterward. Do not leave duplicate test windows or use blanket
  process-name kills. Preserve the user's main Studio window and editor work.

## Current Phase

Current phase: CLI/daemon/runtime development and minimal Quickshell UI,
explicitly approved by the user.

Implement Quickshell incrementally: library and practice first, then minimal
draft editing. The UI may invoke the existing unprivileged CLI using explicit
argv to consume the same daemon D-Bus API; no shell commands or alternate server.
Do not implement assessment yet.
Docker orchestration is limited to the reviewed MVP security policy.
Keep installation files in the repository. New system services and unrelated
host configuration changes require separate approval; updates to the existing
development runtime follow the standing approval below.

Approved development deployment (2026-10-22): the user authorizes building the
current app, updating the installed CyberLab package through the repository's
guarded updater, restarting cyberlabd and refreshing/relaunching Studio as part
of approved development work, without asking again for each update. Verify that
all allowed users' Sessions are STOPPED before replacing the runtime; never
force-stop a Lab or discard unsaved editor work to deploy. Preserve the updater's
backup/rollback path and record the installed artifact and verification result.
Do not rewrite the production catalog, alter Docker access policy, upgrade
Quickshell/Qt or make unrelated host changes under this approval. The user
performs manual acceptance after the running app has been updated.

Approved completion work (2026-10-22): implement the gaps identified in the
feature review: bounded Session-history retention, automatic Studio connection
recovery, live workspace browsing and bounded directory import/export, Lab
cloning and reviewed installed-Lab updates, saved/resumable practice, and runtime
readiness checks. Extend the shared daemon API rather than adding a transport.
Installed-Lab updates must check the exact reviewed source and target revisions,
preserve existing Session snapshots and never silently overwrite another edit.
Saved practice must be distinct from destructive reset; never evict saved work
as ordinary stopped-history cleanup. These features do not authorize editing
the production catalog or user drafts to test, changing Docker access policy,
unrestricted image builds, assessment, router support or upgrading Quickshell/Qt.

The current work focuses on the System D-Bus daemon, CLI, Session lifecycle,
restricted Docker adapter, Quickshell client, and automated tests. Assessment
remains deferred. Test-session D-Bus mode must never use the real Docker adapter.

Approved local-authoring workflow: every allowed CyberLab user may create a
private draft and save their own validated revision as a new Lab in the VM's
existing catalog through cyberlabd, without sudo or a separate author role.
Keep exact revision/digest checks, bounded publication and no-overwrite policy.
This does not authorize direct catalog writes by clients, unrestricted images,
unreviewed installed-Lab replacement, or new system service installation by the coding agent.

Approved installed-Lab deletion (2026-10-22): an allowed CyberLab user may
explicitly delete a Lab in this VM through the shared daemon API. Studio must
ask for confirmation; CLI deletion requires --yes. The engine rejects deletion
while any user has a non-STOPPED Session of that Lab, including FAILED Sessions.
Resolve Lab identities through the validated catalog, never as host paths.
Deletion removes only the selected template/assets and its stopped history;
drafts, Docker images and other Labs are preserved. This feature approval does
not authorize the coding agent to delete production data for verification.
Runtime updates follow the separate development-deployment approval above.

Approved network/container setup slice: declarative private IPv4 subnets,
static per-network node addresses, bridge gateway reservation, internal DNS
selection and bounded independent terminal slots per node. Keep internal
bridges and reject overlapping subnets rather than sharing or renumbering them.
Router capabilities, MACVLAN/TAP, external networking, X11 and password/account
provisioning remain outside this slice. See docs/network-terminal-configuration.md.

Approved Labedit feature work (2026-10-24): the user requests Labtainer/Labedit
functionality in Studio, including Checkwork, results/goals, declared evidence
export, parameters and quizzes. The earlier assessment deferral is superseded
for these local authoring and self-check workflows. Preserve the full parity
backlog in docs/labedit-parity.md; a partial implementation is not completion.
This approval does not relax Docker isolation, authorize arbitrary privileged
grading/build scripts, host mounts, external networking, new account roles or
production-catalog changes. Policy-conflicting features remain explicit pending
decisions, not silently implemented or reported as supported. Keep all feature
paths on the shared daemon API and use isolated fixtures for verification.

Approved simplification (2026-10-26): prioritize basic Labtainer/Labedit-style
Lab management over adding parity features. Keep everyday authoring to machines,
private networks, home files, instructions and optional Checkwork/Quiz. Hide
technical fields and infrequent actions behind explicit advanced controls;
never erase existing declarations just because their controls are collapsed.
Prefer reviewed defaults from the shared daemon API, not guessed image users
or unrestricted discovery/builds. Simplification must preserve revision checks,
confirmation of replacement/deletion, existing drafts and the external catalog.
The parity backlog remains reference material, not automatic implementation scope.
