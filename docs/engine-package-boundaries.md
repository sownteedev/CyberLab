# CyberLab Architecture and Engine Boundaries

## Fixed Architecture

```text
Studio (Quickshell) / CLI
           |
      System D-Bus
           |
       cyberlabd
           |
    CyberLab Engine
           |
     Docker Engine
```

Studio may invoke the unprivileged CLI with explicit argv. Both clients use the
same daemon API; neither controls Docker or performs privileged operations.
There is no REST server, alternate socket protocol or container-side agent.

## Responsibilities

| Component | Responsibility |
| --- | --- |
| `ui/` | Desktop presentation, editing and local appearance preferences. |
| `cli/` | Daemon client, terminal attachment and desktop terminal windows. |
| `daemon/` | System D-Bus transport, caller authorization and service lifecycle. |
| `engine/` | Core Lab, authoring, Session, workspace and assessment behavior. |
| `schemas/` | Versioned declarative Lab-definition schema. |

Docker is a runtime implementation detail, not the public CyberLab API. Engine
logic must remain independent of Quickshell and other GUI components. Views must
not bypass the daemon or duplicate its security decisions.

## Engine Source Map

Paths below are relative to `engine/cyberlab/`.

| Module | Responsibility |
| --- | --- |
| `service.py` | Application orchestration and Session operations. |
| `lab/` | Immutable definitions, validation, catalog and package conversion. |
| `authoring/` | Private drafts, asset storage, publication and reviewed updates. |
| `session/` | Session models and persistence for practice, reports and quizzes. |
| `policy/` | Restrictions applied before runtime operations. |
| `runtime/` | Runtime contracts, restricted Docker adapter, seeding and workspace access. |
| `parameters.py`, `parameter_operations.py` | Parameter resolution and substitutions. |
| `assessment*.py`, `quiz.py` | Bounded local checks and quiz evaluation. |
| `submission.py`, `submission_review.py` | Evidence packaging and read-only review. |

## Data Boundaries

- A Lab is a versioned template; a Session is a running or stopped instance.
  Existing Sessions retain their captured definition when the catalog changes.
- Production Labs live in `/home/<user>/CyberLab-labs`, configured by the daemon.
  Private authoring and saved-practice state are separate from that catalog.
- Draft operations check ownership and revisions. Publication and installed-Lab
  updates require the exact reviewed content; a new publish never overwrites a Lab.
- Terminal handles and workspace operations belong to an authorized Session.
  Home files are container data, not unrestricted mounts of the user's host home.
- Tests use temporary catalogs and fixtures. Test-session D-Bus uses MemoryRuntime,
  never real Docker. Passing it does not prove real-container behavior.

## Safety and Contracts

Do not expose the Docker socket, add learners to the Docker group, use privileged
containers by default or introduce arbitrary host mounts/scripts. Keep private
network and image restrictions explicit. Static validation, runtime readiness
and a successful teaching exercise are different levels of verification.

Use `schemas/v1/lab.schema.json` and
`daemon/cyberlab_ipc/org.ptit.CyberLab1.xml` for concrete fields and signatures.
See `labedit-parity.md` for unsupported features; `AGENTS.md` governs approvals
and architecture changes.
