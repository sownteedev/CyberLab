# Local Lab Authoring Backend (0.9.0)

## Studio authoring contract (2026-11-11)

This section defines the current Studio workflow and supersedes the historical
backend-only milestone description below. Newly authored Labs use:

```text
CyberLab-labs/<lab-id>/
  lab.yaml
  assets/
    docs/guide.md
    files/<node-id>/...
    editor/<node-id>/...
    startup/<node-id>/start.sh
```

Only `lab.yaml` is mandatory. Assets are created when the author adds them;
empty folders, placeholder instructions and startup scripts are not generated
for every Lab. `lab.yaml` declares `apiVersion`, `kind`, `metadata`, `nodes`
(at least one) and `networks` (which may be empty). Publication still validates
the complete definition, assets, image policy and prepared software.

| Studio section | Stored content |
| --- | --- |
| Overview | `metadata`: ID, name, version |
| Machines / Configuration | `nodes`: environment, account, terminals, connections |
| Machines / Software | `nodes[].software`: packages and optional GUI apps |
| Machines / Startup | Optional startup-script switch; shell and custom argv under Advanced |
| Networks | `networks`, with optional subnet and advanced gateway |
| Files | Tree and tabbed editor; private resources under `assets/editor/<node-id>/`, linked through `nodes[].files` |
| Instructions | Markdown at `assets/docs/guide.md`, linked through `documentation` |
| Options | Optional checks, quizzes, evidence and parameters in `lab.yaml` |
| Check / Save to library | Validate and publish the reviewed revision |

Machine configuration uses balanced fields and network cards; only attached
static networks show an IP input. Advanced resources, terminal metadata,
name resolution and accounts are separate collapsible groups, without clearing
hidden values. New Ubuntu nodes enable GUI using the daemon's software resource
defaults. The software page has no GUI switch; preparation also supports GUI-only
machines. Opening existing Labs/drafts does not silently rewrite their software.

Startup is a first-class authoring control, not a new runtime service or schema.
Enabling the startup-script switch creates the asset and its machine-local mapping, then sets
`command` to `[/bin/sh, start.sh]`. Authors write directly in Studio or import
a `.sh` file; imports select Bash for a Bash shebang, otherwise POSIX sh. The
shell remains selectable under Advanced. The normal view contains only the
switch, a script editor with line numbers/shell highlighting and a Choose file
action. With the switch off, the
environment's default command runs; no script is required. Existing custom argv
is preserved and indicated explicitly, with its editor under Advanced. Replacing
a script with custom argv or vice versa requires confirmation tied to the current
draft/node/revision/definition. Switching modes retains script contents and can
restore the previous custom command within the editing session.
The generated template ends with `exec sleep infinity`;
authors running a server can instead end with its foreground command. Scripts
run as the configured machine account when the container starts, not when an
ordinary terminal is opened. Privileges remain unchanged. Installing a package
does not implicitly configure or start a service such as SSH.

The main Save/Publish flow and Ctrl+S save the definition, text/binary resources,
empty directories and deletions in one revision-checked `SaveDraftWorkspace`
transaction. Failed saves retain all pending work. File imports are staged in
the editor until Save; reading a local file does not write to a draft. These
operations never update an installed Lab without publication/update.

Active startup scripts appear in Files and share their text buffer with Startup.
Managed shell/script command paths follow tree renames. Deleting an active
startup script requires first selecting another startup mode; arbitrary paths
inside user code are never rewritten. Shared scripts in Startup remain read-only
until copied; editing in the file tree creates private machine resources.
Editing shared instructions creates a separate documentation resource.
Existing custom argv, script paths, imports and asset layouts remain valid.
Canonical paths describe new content, not a loader requirement. Renaming a
machine does not move existing assets. Name collisions use numbered script
filenames rather than overwrite anything. Switching to Default preserves files;
switching back in the same editing session reuses the previous script.

If an existing machine maps a folder onto its entire home (`target: .`), adding
a separate startup script expands that mapping into its immediate children.
Contents and destinations remain unchanged; the 16-mapping limit is checked
before mutation. This preserves the engine's non-overlapping-target policy.
Legacy per-file and root mappings remain supported. The file workspace converts
only the machine being edited to a private root when its resources are mutated.

### File workspace

The instruction editor links source and preview vertical scrolling by relative
scroll position in both directions. This is proportional synchronization, not
a Markdown source-line map. Library, practice and authoring preview share the
same readable typography, paragraph/heading spacing, padded tables and code
blocks. Styling changes the rendered view only, never the saved Markdown.
Instructions remain UTF-8 Markdown up to 64 KiB; Word/PDF, embedded images,
executable HTML and extensions such as Mermaid or LaTeX are not rendered.

Each machine is a tree root; paths below it are relative to its Lab workspace.
Right-click or the small menu button creates files/folders, imports local
resources, renames or deletes. Names are entered inline (Enter accepts, Escape
cancels); deletion requires confirmation and duplicate names are rejected.
The tree contains only authored seed resources, never live container files.

The editor has tabs, line numbers, indentation, undo/redo and in-file search.
UTF-8 text without NUL is editable up to 64 KiB. Binary/larger resources remain
in the tree but are not decoded into editable text. Closing a tab retains its
pending buffer; switching sections/machines does not discard work. The existing
draft exit/reload confirmations include pending resource changes.
The editor's back arrow remains available with unsaved edits. Returning to the
draft picker asks before discarding them; cancelling keeps the current buffers.
Confirming restores the saved draft without saving, publishing or deleting it.

The Material 3 workspace uses tonal panes, rounded selection states and 48-pixel
tree rows/actions. Tabs show the filename, adding machine/path context only for
duplicate names; the breadcrumb always keeps the complete path. Tab activation
and closing work from the keyboard, and focused/active tabs scroll into view.
Narrow windows stack the tree above the editor. All colors follow the existing
light/dark theme; state animations use the shared motion tokens. These are UI-only
changes: saving, seed-file limits and the daemon contract are unchanged.
All authoring sections use the available content width with small side gutters.
The file workspace grows with the remaining viewport height; short windows keep
its minimum editing height and allow the section to scroll.
Line numbers have a separate muted color and divider. Syntax colors are selected
by filename for Python, shell scripts, JSON, YAML, JavaScript and Markdown, with
Python/shell shebang detection for extensionless scripts. Unknown files remain
plain text. Highlight.js 11.11.1 is bundled locally (BSD-3-Clause); no API,
runtime download, code execution or additional system package is required.
Only a display layer is colored; the editable buffer, selection, clipboard and
saved data stay plain text. IME composition temporarily uses native text rendering.
Highlighting runs in a background WorkerScript with one in-flight request per
active editor, discarding outdated results. Both light and dark palettes are
supported. See `ui/studio/vendor/highlightjs.PROVENANCE.txt` and
`tools/vendor_code_syntax.py` for the pinned archive and QML adaptations.
File/folder creation and rename validation errors use the existing floating
notification instead of the distant page banner, retaining the name for correction.
Existing editor limitation: long unwrapped lines can be scrolled horizontally,
but caret tracking currently scrolls only vertically.

On first mutation of a legacy/shared node mapping, resources are copied to an
unused private root and the node receives one root mapping. Copies and mapping
changes commit together. Other machines, shared documentation and unpublished
catalog data remain untouched. Backend limits remain 128 paths and 2 MiB total;
individual binary assets are bounded to 1 MiB. Paths have at most eight segments,
200 characters and the existing safe-name rules. The daemon reads no host paths.

Verification: `node tools/check_file_model.cjs`, `tools/check_file_editor.py`,
`tools/check_notifications.py --suite files`, and the existing editor/native
checks. The private-bus test covers CLI -> daemon -> transaction -> validation
and publication into a temporary catalog, including binary and empty folders.

Deployment verified on 2026-11-11: installed wheel
`/tmp/cyberlab-file-editor-release-20261111-711hm6g8/cyberlab_engine-0.9.0-py3-none-any.whl`,
SHA256 `0e178c82025a391733bbf3ea4ada4c50ccafc4fa044f9c20b8bc7896b2820806`;
rollback backup `/var/tmp/cyberlab-runtime-backup-g4b9aox_`.
All 298 installed package files match the wheel. The daemon advertises
`file_workspace`, remains active and has no Sessions. Source editor checks
(103), file workspace (8), software (19), practice (26), landing (20), backend
(18) and startup package/materialization (4) passed; installed file workspace
checks also passed (8). Native Quickshell loaded the updated editor, and the
normal installed Studio launch loaded successfully. The existing startup
warning from `NodeSoftwareEditor.qml:122` (null policy before initial load) and
the host accessibility subscription warning remain outside this change.
Verification windows were closed by their exact process group. No real-Docker
Session or production catalog/draft mutation was used for acceptance testing.

Material 3 update deployed on 2026-11-12: wheel
`/tmp/cyberlab-file-md3-release-20261112-wrd64jsp/cyberlab_engine-0.9.0-py3-none-any.whl`,
SHA256 `7da83764705d99fe56e1406e76574ecf757ea0b20f147316b5453204236be40e`;
rollback backup `/var/tmp/cyberlab-runtime-backup-ea29nycs`.
All 299 installed package files match the wheel; the daemon is active with no
Sessions. Source checks: file workspace (11), editor (103), software (19),
practice (26), landing (20), backend (18), startup authoring (4), and the file
model checks passed. Native Quickshell loaded the editor. Visual checks cover
wide/narrow layouts, light/dark palettes and the file context menu. Regression
checks cover readable tab labels, 48-pixel close targets, duplicate filenames,
keyboard focus scrolling and tab/tree synchronization through collapsed folders.
Installed file-workspace checks also passed (11), and a normal installed Studio
launch loaded successfully. Its verification process group was closed afterward;
the previously documented startup/accessibility warnings remain unchanged.

Syntax colors and file-name notifications deployed on 2026-11-12: wheel
`/tmp/cyberlab-syntax-release-20261112-haj7twyf/cyberlab_engine-0.9.0-py3-none-any.whl`,
SHA256 `5a9c3a0f7000c902f9e2790c7d26b2cae17aeb53faa5ecb299ec91e9fcd85937`;
rollback backup `/var/tmp/cyberlab-runtime-backup-q90__ubz`.
All 306 installed package files match the wheel. Installed file tests passed
(23), including popup validation, syntax palettes, text/undo preservation,
Unicode/tab geometry and stale worker results. Native Quickshell rendered the
Python color layer (`CYBERLAB_SYNTAX_LOAD_PASS`). The daemon is active with no
Sessions; the guarded updater preserved the catalog and configuration.

Known host Qt 6.12 diagnostic: WorkerScript initializes a QtObject without an
associated QJSEngine, logging `QObject::connect(QJSEngine, QtObject): invalid
nullptr parameter`. The worker still returns verified results. The test helper
accepts only that exact diagnostic when explicitly passed
`--allow-worker-init-warning`; it retains original warnings in the log and
continues to fail other warnings. No Qt package or runtime warning filter was
changed. Syntax is display-only, not a parser/validator for executing code.

A teaching-ready Lab normally has a working environment, instructions with
objectives/tasks/expected results, and any required input data. Startup scripts,
GUI apps and automated checks are optional. Sessions, saved work, images and
runtime-generated SSH keys are not part of this template directory. Referenced
images/prepared environments must also be available on the destination host;
exporting a Lab package does not bundle them.

Verification: `check_notifications.py --suite editor --native` covers script
authoring and existing Labs. `check_startup_authoring.py --qml-log LOG` validates
and publishes the actual package emitted by that QML test into a temporary
catalog, then checks export/import and workspace seed materialization.

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

### Resume Editing (2026-10-30)

Studio's **Edit** action and `cyberlab draft edit LAB` share daemon-side reuse:
no matching draft creates one, one matching draft returns it unchanged, and
multiple matches return `{selection_required: true, lab_id, drafts}` without
writing anything. Candidates must belong to the caller, retain the same Lab ID
in their definition, and carry the matching installed-Lab origin. Names alone
are not identities; unrelated new/imported drafts are not silently adopted.
The lookup and creation run under the lifecycle/store locks to prevent two
simultaneous requests from creating duplicates in the daemon.

Studio shows a bounded selection dialog with draft ID, revision and a warning
if its origin differs from the current catalog digest. Revision is an edit
counter, not a timestamp or a ranking of different drafts. Continuing the
currently open matching draft preserves unsaved form/documentation edits.
Opening another Lab requires saving current edits first. Cancel changes nothing;
**Create separate draft** requires confirmation and preserves every old draft.
The existing drafts are not cleaned up or merged automatically.

CLI selection is `cyberlab draft edit LAB --draft DRAFT_ID`; explicit fresh copy
is `cyberlab draft edit LAB --new`. These options are mutually exclusive. A
deleted/mismatched choice fails instead of creating a replacement. Returned
existing drafts keep their exact revision, contents/assets and original catalog
digest, including stale origins; installed-update conflict checks are unchanged.
`GetAuthoringInfo.resume_editing_draft` advertises the behavior. JSON consumers
of `EditLab` must handle the selection response rather than assuming a draft.

`tools/check_editing_drafts.py` uses temporary stores and an isolated private
D-Bus daemon with MemoryRuntime, never the production catalog or Docker.

Verification: 12 isolated backend/CLI/private-bus checks, 65 editor checks on
source and installed QML, 20 landing checks, 34 dialog checks and 22 workstation
regressions pass. Targeted qmllint and `git diff --check` pass. The guarded updater
deployed wheel SHA256
`2ac85c559d7b7d325454536edd6182a9a88a369929a6663bcbf8b091bdc9b12e`,
backup `/var/tmp/cyberlab-runtime-backup-epm72_le`. Installed changed files match
the artifact and the daemon advertises reuse. All three preexisting production
draft IDs/revisions remain unchanged. The normal launcher loaded Studio; only
that tracked verification window/process group was closed. No production edit,
new draft, catalog mutation or real-Docker Session was used for verification.

### Methods

Capability `authoring` appears only when enabled. Service/interface and object
remain `org.ptit.CyberLab1`, `/org/ptit/CyberLab1`.

| Method | Input | Output |
| --- | --- | --- |
| GetAuthoringInfo | none | JSON string: schema, allowlist, limits, permission |
| CreateDraft | `ss`: Lab ID, title | JSON draft |
| EditLab | `s`: installed Lab ID | JSON draft or selection-required choices |
| ResolveLabDraft | `ssb`: Lab ID, draft ID (or empty), fresh flag | JSON draft or choices; same reuse rules |
| ListDrafts | none | JSON list of IDs, owners, revisions, Lab metadata and origins |
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
cyberlab draft create my-lab --title 'Bai lab cua toi' --tag linux
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

Studio translates authoring, validation, runtime and software errors into
Vietnamese at the display boundary (`ui/studio/models/Messages.js`). The daemon
contract, logs, identifiers, file contents and package names remain unchanged.
Unrecognized external diagnostics are preserved rather than guessed or hidden.
Validation and visible contextual errors also open the shared error popup;
errors arriving together are grouped and duplicate lines are suppressed. Hidden
fields do not raise stale popups, and dismissing a popup does not edit the draft.
`node tools/check_messages.cjs` checks translations against backend error strings;
the notifications UI suite checks popup delivery, localization and dismissal.

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
