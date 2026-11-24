# Simplified Lab authoring (2026-11-05)

## Fixed Lab topics (2026-11-16)

The version-1 schema defines twelve topic IDs and Vietnamese display labels in
`metadata.tags`. `GetAuthoringInfo.topic_catalog` supplies the authoring picker;
`ListLabs`/`GetLab` include `tags` and `tag_labels` for display and filtering.
Creation requires at least one choice, with no automatic default or free text.
Studio uses the additive `CreateTaggedDraft` method through
`cyberlab draft create ID --title TITLE --tag linux --tag networking`.
The old `CreateDraft` signature remains registered but rejects tagless creation.

Tags can be edited in Overview. Private incomplete drafts may still be saved;
publication and installed-Lab updates reject missing, unknown or duplicate tags
on the shared backend. Existing untagged Labs remain loadable and runnable;
no production catalog or draft is migrated automatically. Import/export and
cloning preserve declared topics. The library shows only topics used by its
Labs; multiple selected topics use OR, combined with text search using AND.
Topic chips share a theme-aware color and icon per topic across Library rows,
Lab headers and the topic picker. Selection keeps the topic icon and adds a
separate check mark; colors do not replace labels or selection indicators.
Canceling the picker leaves the current selection unchanged.

Library cards keep the title and machine/network counts together, with topic
chips on a separate full-width row. The detail header places Lab identity and
topics on the left and Session status/counts on the right at widths of 640 or
more; narrower headers stack the same content without hiding metadata.

## Practice file controls removed (2026-11-11)

Practice now shows **Machines** rather than **Machines and files**. Each node
retains a read-only **Lab files** tree from its captured `seed_files` and
`seed_directories` metadata (declared mappings on older daemons). Files generated
or imported during practice are not included. No filesystem scan is performed;
the tree describes the initial Lab contents, not current file existence.
Refresh/import/export buttons, transfer explanations, the separate file import
form and import history are removed from this view. Selecting or resetting
a Session no longer automatically requests workspace listings or import history.
Terminal/GUI controls, instructions, save/resume and submission remain unchanged.

Authors still add seed files/folders in the Lab editor; those declared files are
placed in each machine when the runtime initializes it. This UI change does not
delete files, edit Lab definitions, overwrite checkpoints or remove the shared
daemon/CLI file-transfer APIs. Files created during practice remain in the machine
and follow the existing save/resume behavior.

Source checks cover initial-file trees and absence of transfer controls on desktop
and compact layouts, continued terminal dispatch/busy guards, no hidden workspace requests
on selection/reset/resume, and unchanged authoring and GUI interactions.

Verification on 2026-11-11 passed 26 practice checks and native offscreen loading,
40 lifecycle checks, 9 GUI checks and 103 authoring checks. Desktop/compact seed
tree screenshots were inspected. Targeted Qt 6 lint and diff checks passed
(lint retains existing naming/unqualified-access warnings). The extracted wheel
also passed all 26 practice checks and native offscreen loading.
Installed artifact: `/tmp/cyberlab-seed-tree-release-20261111-XbQcoe/cyberlab_engine-0.9.0-py3-none-any.whl`,
SHA-256 `1a52e64af1912a6ffe3f3e8f27b8eeb3150e738c3c928a90de646349d484ce7f`.
Guarded installation completed on 2026-11-11 after the user closed Studio and
all allowed users passed the stopped-Session gate. Backup:
`/var/tmp/cyberlab-runtime-backup-1qr5rymv`. All 292 installed package files match
the wheel; installed practice checks passed all 26 cases and native offscreen
loading. Normal installed Studio opened on Wayland and its exact test window
closed cleanly. The daemon is active with `RestrictAddressFamilies=AF_UNIX`,
XWayland readiness remains available, and no Session is running. No production
Lab or draft was modified. The existing `NodeSoftwareEditor.qml:122`
initialization warning remains outside this change.

## Authoring layout

The everyday editor presents the learner's outcome rather than storage details:

- Overview: name and metadata; private draft status in one sentence.
- Machines: configuration, software and startup in separate tabs. Startup scripts
  can be written/imported directly; Studio manages their assets and commands.
  See `lab-authoring.md` for the canonical package/authoring contract. One software
  picker combines applications and package suggestions, automatically enabling
  window support for builtin GUI apps. Search uses the shared daemon's catalog,
  not package names the author must memorize.
- Networks: name, optional subnet and connected machines. The bridge gateway
  is behind Advanced; hiding it never changes its declaration.
- Machine settings omit repeated account/home summaries and successful-input
  hints. Username guidance appears only for invalid input. Networks omit prose
  already covered by the subnet placeholder; validation errors stay visible.
- Files: choose a receiving machine, optional destination folder, then add a
  file or folder. Show only the resulting home-file tree and removal action.
  Remove the mapping/asset inventory controls from this everyday screen.
  Existing mappings and unreferenced assets are retained, not migrated/deleted.
  Folder import still copies its contents, and replacement still needs consent.
  When a displayed file belongs to a shared mapping or powers the instructions,
  Remove means detach it from the selected machine and retain the shared asset;
  the author never needs to open Advanced just to perform that normal action.
  Shared folder mappings are split around the selected file, keeping sibling
  files/subfolders (including empty folders) and other consumers unchanged.
  The existing 16-mapping limit is retained; exceeding it fails before any edit.
  Confirmation is tied to the displayed draft revision and definition.
- Instructions: the existing Markdown editor and preview.
- Check: short readiness states and the same reviewed publication/update flow.
- Options: the existing Labedit controls remain optional and keep all data.

No schema, transport, privileges, catalog or draft migration is introduced.
The extra package metadata is additive in GetAuthoringInfo capabilities.
This is a curated suggestion list, not an online APT search or proof of runtime
compatibility. GUI app preparation and package-only preparation share the same
bounded, revision-checked engine workflow. Disabling GUI keeps packages; deleting
the last package without GUI clears an unused software declaration.

## Shared-file removal regression

The previous file removal action rejected an asset used by documentation or a
second machine and directed the author to the removed Advanced UI. The corrected
action saves a machine-local definition change through the existing SaveDraft
API, without calling RemoveDraftAsset for shared content. Other mappings of the
same source on the same machine are also preserved. Private files retain the
existing asset-removal workflow. Tests cover exact files, shared folders, nested
siblings/empty directories, mapping limits and stale confirmation rejection.

Source validation: 77 editor tests and the native Quickshell offscreen probe
passed; targeted qmllint and git diff --check passed. This fix is included in the
guarded deployment recorded below. Production drafts were not edited.

Verification uses temporary catalogs, fake software builds and offscreen QML:
`tools/check_software.py` and `tools/check_notifications.py --suite software`
or `--suite editor`. Coverage includes package-only prepare/apply, filtering,
selection limits, inferred/custom GUI and node changes, old mappings, advanced
gateway preservation and compact/zoomed layouts. Real APT installation is not
asserted by these tests. Deployment evidence is recorded separately.

## Startup authoring verification (2026-11-06)

The unified authoring contract passed 94 editor cases with the native Quickshell
load probe, 4 engine checks using the actual QML-emitted package, 15 software UI
cases, 20 landing cases and 12 editing-draft checks. QML lint and diff checks
passed. Package checks cover publication, export/import, missing-script rejection
and execution of a known harmless fixture in a temporary workspace; they do not
claim Docker/SSH acceptance. No production Lab or draft was changed.

## Installed verification (2026-11-06)

On explicit user request, the guarded updater installed
`cyberlab_engine-0.9.0-py3-none-any.whl`, SHA-256
`1caff69d6e0ea9e0d545df62c58ca43115111561064a50b12b1fe27728011819`.
Backup: `/var/tmp/cyberlab-runtime-backup-tt4mgkru`.
All allowed users passed the stopped-Session gate; no Studio editor was open.
The updater verified the daemon and preserved catalog identity/configuration.
All 191 installed Studio resource files match the wheel. The installed editor
passed 94 tests and the native Quickshell load probe. A normal installed-launcher
test opened its own X11 window, loaded the configuration and exited cleanly via
WM_DELETE_WINDOW; no duplicate test window was left open. The daemon remains
active and the verification user's Session list is empty. No real Docker Lab
was started for acceptance.

## Startup UX follow-up (2026-11-06)

The three-way startup dropdown is replaced by a single optional-script switch.
Enabling it reveals the editor and Choose file button. Shell selection, asset
path and custom argv are under Advanced. Existing custom commands stay unchanged
and show a concise status; switching between custom argv and a script requires
confirmation. Cancel/stale confirmation does nothing. Toggling retains script
contents and the previous custom command during the editing session. Failed
script creation leaves the old command intact. Advanced collapses when changing
machines. Source checks passed 100 editor tests, the native load probe, four
package round-trip checks and QML lint.

Installed on explicit user request after Studio closed and the stopped-Session
gate passed. Wheel SHA-256:
`0c4c2c1998842834b82e4333bd2e92ee9fd02fe4bf9fde1e2aae0d9157e99caf`.
Backup: `/var/tmp/cyberlab-runtime-backup-qtn2ybv9`.
All 192 installed Studio files match the tested wheel. The installed editor
passed 100 tests and the native load probe. Normal launcher/window startup and
graceful close passed; no test window remains. The daemon is active, the
verification user's Session list is empty, and catalog/configuration were not
rewritten. No real Docker Lab was started.

## Unified software picker (2026-11-06)

The Software tab now has one searchable catalog and a compact list of selected
names. Add software expands the catalog; Done collapses it. Firefox/Wireshark
infer display support without a separate GUI section. Other APT software can
opt into window support in the manual entry form and launch from the Lab terminal.
Existing gui-only declarations remain visible/removable, and removing a builtin
application preserves display support for remaining custom packages. Manual
builtin names use the existing reviewed recipes; Snap and malformed names remain
blocked. GUI selection never reduces higher configured CPU/RAM values.

No schema, daemon API, package sources or runtime isolation policy changed.
Source verification passed 22 software UI tests (including real mouse/keyboard
input), 100 editor tests with native Quickshell loading, 18 fake-runtime/engine
checks, Qt 6 QML lint and diff checks. The fake runtime checks verify custom GUI
package declarations include the display stack without builtin applications;
they do not claim live APT availability or launch acceptance for arbitrary apps.

Installed with the guarded updater after Studio was closed and all users passed
its stopped-Session gate. Wheel SHA-256:
`6fcd2c9f10407b18d8a3d8a3553202f426c43db55b4d15f6029531fcde357753`.
Backup: `/var/tmp/cyberlab-runtime-backup-aw4vhdgh`.
All 190 installed Studio resource files match the tested wheel. Installed checks
passed 22 software cases, 100 editor cases and the native Quickshell probe.
Normal installed Studio launch passed on the current XFCE X11 display, and its
exact test window closed gracefully. The launch probe initially had no DISPLAY;
it passed after inheriting only the desktop connection variables from XFCE.
Daemon active; verification-user Sessions empty; no production Lab/draft edits,
real Docker Labs, or test windows left behind.

## Package search and trailing GUI switch prototype (2026-11-06)

The always-visible search field and compact checked rows replace the expandable
pill grid/manual package form. The GUI switch is below the list and independent
of selected application recipes. Switching it off preserves all selections.
Source checks: 19 software UI cases, 100 editor cases/native load, 19 software
engine/runtime checks and 11 metadata/CLI checks passed. Direct unprivileged
metadata lookup read 87,920 Ubuntu 24.04 amd64 package names across release,
updates and security, finding mousepad from partial names/descriptions.

Not installed: the existing daemon service restricts socket families to AF_UNIX.
The experimental downloader cannot fetch HTTPS from that service. No service
policy was weakened. A decision on moving public metadata fetching to an
unprivileged client or explicitly authorizing network access is needed before
shipping this prototype. Production Labs, drafts and Sessions were untouched.

## Unprivileged package lookup delivery (2026-11-06)

The user approved updating the prototype with public metadata lookup running as
the desktop user. The CLI checks GetAuthoringInfo before searching its private
cache; the draft software-search interface stays unchanged for Studio. The
experimental SearchSoftwarePackages daemon method is removed before deployment.
No daemon socket-family restriction or system-service configuration is changed.
An isolated unprivileged worker fetches fixed Ubuntu indexes; a passed file lock
prevents duplicate downloads across CLI calls and windows. Atomic 0600 cache
files have size/owner/type checks, no symlink following, bounded entries and a
six-hour TTL. Interrupted/failed refreshes keep the old index and allow retry.
Tests cover detached-lock ownership, cache publication, offline retention,
corruption, symlinks, root rejection and CLI policy checks.

Installed through the guarded updater after all allowed users passed the stopped
Session gate; no user Studio window was open. Wheel SHA-256:
`947c1b1c83a9dca7cf80df1fa4f33ac72150067f2007b4a2e914220332045e86`.
Backup: `/var/tmp/cyberlab-runtime-backup-4doxfinw`.
All 191 Studio resources match the wheel. Installed verification passed 19
software UI cases, 100 editor cases and the native load probe. A normal Studio
launch opened and closed its own window successfully. Metadata/cache/CLI tests
passed 18 cases; software engine/runtime checks passed 19 cases.

The installed CLI successfully loaded the real Ubuntu index using its detached
worker at UID 1000. Partial-name mousepad lookup and Vietnamese soan thao lookup
returned ready/cached results (94 text-editor matches); the measured warm CLI
lookup took 0.429 seconds on this machine. The user cache is now warmed for UI
acceptance. Daemon remains active with RestrictAddressFamilies=AF_UNIX unchanged;
verification-user Sessions remain empty. No Docker Lab, production draft/catalog
mutation, or duplicate test Studio window was created/left behind.
# Topic creation and popup-only errors (2026-11-21)

The topic picker can pass a QML sequence through the service method boundary,
not a JavaScript Array. Draft creation copies that sequence with `Array.from`
before checking its nonempty string entries and building repeated `--tag`
arguments. Empty or malformed selections still fail locally; backend topic
validation remains unchanged. The regression uses the real picker dialog,
create card and DraftService instead of a mock `create` method.

The workspace no longer renders `localError` beside the popup. The shared
`InlineError` compatibility component now reports through StudioFeedback
without drawing text, icons or reserving layout space. It still respects the
containing view's visibility and the existing notification opt-out/deduplication.
Checks cover hidden views, dismissed/repeated errors, Vietnamese messages,
and an unchanged landing layout while a validation error opens its popup.

