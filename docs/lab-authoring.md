# Local Lab Authoring Backend (0.9.0)

## Product Boundary

This milestone implements the backend of the future **Lab editor**, not another
teaching Lab and not a Quickshell screen. The CLI is a temporary/test client for
the same System D-Bus API the UI will use. No new Lab is added to `labs/`.

The supported workflow is:

```text
Create private draft → edit node/network/environment/document declarations
    → upload assets → save revision → validate
    → owner confirms revision + content digest → save new Lab to local library
    → the same user sees the Lab beside preinstalled Labs and starts Sessions
```

Runtime operations still follow CLI/UI → System D-Bus → cyberlabd → engine →
Docker. The editor does not build images, execute draft commands, or give the
student Docker access. Existing runtime policy still applies; a UI must not
offer unsupported mount, root-user, capability or assessment fields. Restricted
static IPv4/subnet/bridge-gateway, internal DNS and terminal counts are available
in development source; see `network-terminal-configuration.md`. They are not
in the existing 0.9.0 bundle.

Each Ubuntu VM has its own library. There is no central service, separate author
role or administrator approval queue. `draft publish` means save a validated
new Lab into that local library; it does not upload anything. The 0.8.0 root-only
publication restriction is deliberately removed in 0.9.0. All allowed Unix
accounts on the same VM can browse/run saved Labs; drafts remain private.

## Implemented Editor Operations

- Query the versioned Lab schema, image allowlist, runtime limits, authoring
  quotas, and whether the caller can publish. The UI can build forms for nodes,
  networks, accounts, hostnames, shell/home, terminal plans, docs and file maps
  from the same definition the backend validates.
- Create, list, reopen, save and delete private drafts. A new draft is
  intentionally incomplete (no nodes); it never appears in the student catalog.
- Save a whole definition as bounded YAML or JSON text. JSON is valid YAML and
  is suitable for a UI form model. Drafts may contain incomplete or invalid
  definitions; validation is a separate operation with structured diagnostics.
- Add/replace asset files, upload a folder's regular files in one atomic batch,
  inspect asset metadata/hashes, download a specific revision's asset bytes,
  and remove individual assets. These are **template assets**, distinct from
  `import-file`, which only affects an already running Session.
- Validate syntax, schema, topology, initial-file/doc loading and runtime policy
  without starting containers. Reports identify stage, field path, message,
  revision and content digest. `runtime_verified: false` is explicit: validation
  does not prove that an image is installed, an account exists inside it, or a
  service starts successfully.
- Publish one's own reviewed revision as a **new** catalog Lab, without sudo.
  It is immediately available to existing `labs`, `show`, `docs` and `start`
  operations. Editing/deleting the draft does not change its published copy or
  any running Session.

## Storage, Isolation and Revision Safety

Production drafts are persisted in
`/var/lib/cyberlab/authoring/drafts.sqlite3`, a private root-owned SQLite database
outside the catalog. Definition text and raw asset bytes are data, never pickle,
Python modules or executable host scripts. Database format is version 1;
unsupported future formats are refused rather than reset. Drafts survive daemon
restarts; Sessions still do not. Backups must include the private authoring
directory consistently while the daemon is stopped.

The existing Unix UID allowlist controls access. Each allowed user sees/edits
only their own drafts and can publish their own validated revisions. UID 0
retains access to all drafts for local maintenance. Identity comes from the
actual D-Bus caller, never a supplied username/owner or a UI role label.
When authoring is enabled, `can_publish: true` and
`publish_requires_admin: false` describe this owner-based permission, not
permission to publish another user's draft or overwrite an existing Lab.

Every mutation and asset read supplies the expected revision. A successful
mutation increments it; stale operations return `Conflict` without partially
applying changes. Upload batches use one SQLite transaction. The UI should
reload after conflict, not silently retry against a newer revision. A digest
binds the exact definition text and every asset path/content hash, including
assets not referenced by a node. Publication requires **both** the reviewed
revision and digest; any subsequent edit invalidates that approval.

Quotas: 10 drafts per owner, 100 total; definition text up to 64 KiB; an asset up
to 1 MiB; 2 MiB total definition+assets per draft; 128 paths including directory
parents. Node seed and doc quotas still apply separately during validation.
The database also has a bounded page count. Deleting unused drafts releases
logical quotas; SQLite may retain reusable free pages on disk.

Publication also enforces a VM-wide limit of 128 catalog Labs (including
preinstalled Labs), exposed as `max_catalog_labs`. The limit is checked under
the lifecycle lock before staging, so concurrent saves cannot exceed it.
Each authored package remains limited to 2 MiB / 128 paths. Deleting a draft
does not free a catalog slot. Catalog deletion/updates need a later reviewed
workflow; reaching this limit returns `LimitReached` without writing a Lab.

Asset paths must be conservative relative paths under `assets/`, using the same
path-segment rules as initial files. No traversal, symlinks, hardlinks, special
files or file/directory collisions are accepted. The CLI reads sources as the
invoking user and sends bytes, never host paths. Folder upload refuses hidden
entries, excessive size/count and filesystem crossings. Empty directories are
not represented yet. Replacing an asset in a draft requires the exact current
revision; it does not overwrite a file in a live container or published Lab.

Downloads require an explicit **new** local output file and never overwrite an
existing local path. Draft listings do not return asset contents. Drafts can
still contain sensitive data intentionally uploaded by the owner: keep the
database private, review **all** assets before publication, and do not upload
credentials or secrets.

## Publication Safety

The daemon materializes the reviewed snapshot into a fresh hidden staging
directory inside the catalog, revalidates it, and assigns trusted permissions.
Linux `renameat2(RENAME_NOREPLACE)` exposes the whole package together without
replacing even an existing empty directory. Duplicate Lab IDs anywhere in the
catalog are rejected. Normal failures remove the staging directory; a crash
may leave hidden staging data for administrator review, never a runnable
half-written Lab. This is not an automatic recovery/rollback mechanism.

Files are root-owned mode 0644 and directories 0755 in production. Arbitrary
commands from the definition are not run during validation/publication. They
are subject to the existing image/user/container restrictions when a Session
starts. Publication does not update the image allowlist or build/pull an image.

Publishing remains intentionally append-only in 0.9.0: no replacement, unpublish,
or deletion API for installed Labs. Repeating a publish after a lost reply may
return `Conflict` because the first call succeeded; inspect the catalog before
retrying. New definitions with an existing Lab ID require a later reviewed
update/version-management workflow. Publication does not interrupt Sessions.

## Shared D-Bus Contract

Capability `authoring` appears only when enabled. Service/interface and object
remain `org.ptit.CyberLab1`, `/org/ptit/CyberLab1`.

| Method | Input | Output |
| --- | --- | --- |
| GetAuthoringInfo | none | JSON string: schema, allowlist, limits, permission |
| CreateDraft | `ss`: Lab ID, title | JSON draft |
| ListDrafts | none | JSON list of IDs, owners, revisions |
| GetDraft | `s`: draft ID | JSON draft and asset metadata |
| SaveDraft | `sus`: draft ID, revision, YAML/JSON definition | JSON draft |
| PutDraftAssets | `sua(say)`: draft ID, revision, path/bytes pairs | JSON draft |
| GetDraftAsset | `sus`: draft ID, revision, asset path | `ay`: bytes |
| RemoveDraftAsset | `sus`: draft ID, revision, asset path | JSON draft |
| ValidateDraft | `su`: draft ID, revision | JSON report |
| PublishDraft | `sus`: draft ID, revision, reviewed digest | JSON report |
| DeleteDraft | `su`: draft ID, revision | `b`: deleted |

Structured JSON is carried **inside System D-Bus strings**, not a REST API or
another transport. This keeps schema/form data extensible while binary assets
remain typed D-Bus byte arrays. Definitions are raw text in the `definition`
field; JSON clients must decode that field separately into a form model when
appropriate. Responses use `id`, `owner`, `revision`, `definition`, `digest`,
and `assets` (path/size/sha256). Diagnostics use `issues` entries with `stage`,
`path`, and `message`, capped at 32 schema issues per validation.

All methods still perform caller authorization. Disabled authoring fails
closed; oversized messages are rejected before scheduling work. Existing
`AccessDenied`, `NotFound`, `LimitReached`, and the new `Conflict` errors should
be displayed meaningfully by future UI clients.

## CLI Editor Workflow

These commands exercise the future UI's operations; they are not intended to
be the final student experience. No Docker commands are needed.

```sh
cyberlab draft info
cyberlab draft create my-lab --title 'Bai lab cua toi'
cyberlab draft list
cyberlab draft show DRAFT_ID
cyberlab draft show DRAFT_ID --definition > my-lab.yaml
```

Replace `DRAFT_ID` with the ID returned by create. Edit the local definition
using the schema from `draft info`. A UI will perform these changes via forms.
Each mutation returns a **new** revision; use that value for the next command:

```sh
cyberlab draft save DRAFT_ID my-lab.yaml --revision REVISION
cyberlab draft put-file DRAFT_ID ./README.md assets/docs/README.md --revision REVISION
cyberlab draft put-tree DRAFT_ID ./exercise-files --prefix assets/client --revision REVISION
cyberlab draft check DRAFT_ID --revision REVISION
```

`check` exits nonzero and prints a report when invalid. Fix issues and validate
again. File upload only stores assets: reference them using `documentation`
or node `files` mappings to use them in the Lab. Optional review/edit commands:

```sh
cyberlab draft asset DRAFT_ID assets/docs/README.md --revision REVISION --output reviewed-manual.md
cyberlab draft remove-asset DRAFT_ID assets/obsolete.txt --revision REVISION
```

The same ordinary user checks the complete definition and assets, then saves
exactly that revision/digest into the library; no sudo is needed:

```sh
cyberlab draft show DRAFT_ID
cyberlab draft check DRAFT_ID --revision REVISION
cyberlab draft publish DRAFT_ID --revision REVISION --digest REVIEWED_DIGEST
cyberlab labs
cyberlab start LAB_ID
```

Do not paste arbitrary definitions or assets into a root shell. Review includes
image selection, declared commands, network topology, user identity and every
asset. `valid: true` is a policy check, not a substitute for that review.
After publication, students can use the existing catalog/Session operations.
Deleting a draft only removes its private editing data:

```sh
cyberlab draft delete DRAFT_ID --revision REVISION
```

## Enable on the Existing VM

Base installs and ordinary package repairs leave production authoring disabled.
The optional upgrade is separate because it allows narrowly scoped writes by
the daemon. Repository file `daemon/systemd/authoring.conf` adds only
`ReadWritePaths=/var/lib/cyberlab/labs /var/lib/cyberlab/authoring`; all original
unit hardening, Docker socket restrictions and D-Bus policy remain unchanged.
The config gains only `authoring = true`; image and caller allowlists are kept.
The existing config is backed up in the private installation staging area.

Developer-side bundle preparation (already-built bundles need only `check`):

```sh
.venv/bin/python -m pytest -q
.venv/bin/python tools/deploy_mvp.py build dist/mvp-local-authoring-0.9.0
.venv/bin/python tools/deploy_mvp.py check dist/mvp-local-authoring-0.9.0
```

**Save current Session work first. Stopping the daemon discards all temporary
Session data. Persistent drafts, once enabled, survive the restart.** On the VM:

```sh
cd /home/student/CyberLab
sudo systemctl disable --now cyberlabd.service &&
sudo /usr/bin/python3 -I tools/deploy_mvp.py repair dist/mvp-local-authoring-0.9.0 --uid "$(id -u)" --enable-authoring
```

This does not add a new Lab or build/pull images. It installs the reviewed
drop-in, creates the private state directory, enables authoring and runs the
existing verifier plus a temporary draft create/save/asset/check/reopen
flow. The verifier confirms that owner publication is available, a wrong digest
is rejected and the catalog is unchanged, then deletes its temporary draft.
It **does not** auto-publish a
Lab or claim that an arbitrary authored Lab has been tested in Docker.

If failure occurs, keep output/staging files for review; do not blindly rerun
or remove the database. There is no automatic rollback. Coding itself does not
enable the service or install these system files.

## Verification and Remaining Work

Tests cover ownership, draft persistence, quotas, atomic uploads, stale and
concurrent saves, safe local folder import, schema/asset/policy diagnostics,
owner publication, catalog limits, digest binding, no-overwrite atomic publication,
catalog usability and unchanged Session snapshots. Real private D-Bus smoke
tests use MemoryRuntime and never contact Docker. Positive publication tests
use temporary catalogs only. System-service/drop-in acceptance is pending the
administrator-run VM upgrade. See `local-authoring-acceptance.md` for the separate
ordinary-user create/save/run acceptance command. Successful local saves require
no administrator interaction after the service has been upgraded/enabled.

Still deferred: Quickshell layout/widgets, installed-Lab editing/version
replacement, image preparation workflows, router/forwarding policy, directory
imports into running Sessions, arbitrary export/browsing of live container
files, and assessment. They should extend this API incrementally rather than
put privileged logic into the UI.
