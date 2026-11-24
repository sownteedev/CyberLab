# CyberLab Studio

Studio is the Quickshell desktop client for the shared CyberLab daemon API.
The common workflow is Library, practice and basic Lab editing; advanced
declarations remain optional. It is not a claim of complete Labtainer parity.

## Launching

For an installed runtime, use the explicit installed entry point:

```sh
/usr/local/bin/cyberlab-studio
```

For source development, with a fresh editable repository venv and native
Quickshell installed by the distro's package manager:

```sh
bash tools/run_studio.sh --require-native
```

Both connect to the real System D-Bus daemon and can change the user's Sessions
and drafts. Neither installs, upgrades or restarts the daemon automatically.
Run as the ordinary desktop user with `DISPLAY` or `WAYLAND_DISPLAY`, not root.
A compatible native terminal must be available for automatic terminal windows;
Konsole is no longer required. Settings > Terminal shows the detected default
and, with multiple compatible applications, allows an explicit choice or Auto.

The old fixture-based `--demo`/`--smoke` tools were archived outside the
checkout. The compatibility `tools/run_studio.py` entry point preserves old
source shortcuts but refuses those preview flags before starting anything.
Normal Studio is not a disposable preview and can change real user data.
An already-installed legacy AppImage can still be used without
`--require-native` on the old VM; new installations neither fetch nor require it.

See `install-mvp.md` for desktop dependencies, shortcut targets and updates.

### Desktop Window Identity

Studio sets the Quickshell startup AppId to `cyberlab-studio`, matching the
installed `cyberlab-studio.desktop` entry. This lets Wayland compositors and
taskbars associate the running window with its launcher and icon. The generic
`org.quickshell` ID is reserved for the desktop shell and may be hidden from
docks/workspace indicators; Studio must not inherit it. The application menu
can still show a desktop entry even when running windows use the wrong ID.

After updating an older installation, save editor work and close/reopen Studio
normally: the AppId is applied at process startup, not by QML hot reload. Do not
work around this by disabling the desktop shell's window filters. The offscreen
Studio smoke also checks the expected AppId before exercising the workflow.

Verified on Niri with native Quickshell 0.3.2 (2026-10-28): QML lint and the
private MemoryRuntime/offscreen Studio smoke pass. A temporary native Wayland
window using Studio's startup pragmas reports `cyberlab-studio` and resolves
the installed desktop entry; only that test process is closed. Existing Studio
windows are preserved. The desktop launcher also supplies
`QS_APP_ID=cyberlab-studio`, so an older installed package gets the correct ID
when opened normally, without a manual terminal command. A same-name personal
entry under the user's XDG data `applications` directory can apply this launcher
fix without replacing the installed runtime; the updater preserves personal
shortcuts. Save and close existing Studio windows, then reopen from the launcher.

## Library and Practice

### Primary Navigation

The three existing destinations (Library, Practice and Authoring) live in a
compact horizontal group beside the CyberLab brand in the header, not in a
full-height sidebar. There is only one Authoring entry; it opens the existing
draft/editor workflow, not an immediate new-draft mutation. The old static VM
label is removed; the live daemon connection status stays in the header.

Below the existing 880px compact breakpoint, the group moves to its own header
row. Narrow widths retain all three text labels and hide only their decorative
icons. Settings, refresh and window controls remain accessible. Arrow/Home/End
keys move focus between destinations; Space activates the focused destination.
The current page indicator changes only when guarded navigation succeeds.
The group is 440 logical pixels wide on desktop. Its shared active pill slides
to the accepted destination in 260ms, retargets immediately on another change,
and uses shared motion tokens. There is no user-facing reduced-motion setting.
Hover/press feedback uses a fixed-color layer with animated opacity, independent
of the sliding selection. It never interpolates transparent black into a surface
color. Labels keep the same font weight when selected, avoiding brightness flashes
and text shifts during pointer interaction.

`python3 -I -B tools/check_notifications.py --suite navigation` verifies route
selection, keyboard access, busy controls, connection status and header geometry
from 320px to 1440px in isolated light/dark captures. The private-bus Studio smoke
also verifies that canceling navigation preserves unsaved draft text.

- Search/select a Lab, read its packaged Markdown and start a Session through
  the daemon. Configured terminal windows open after successful startup.
- Manage private drafts and explicitly clone, update or delete a Lab through
  the reviewed daemon workflows; clients never write the catalog directly.
- Practice displays captured instructions, nodes, terminals and workspace files.
  File transfers remain bounded to authorized container workspaces.
- Save, suspend and resume are distinct from destructive reset or stop. See
  `saved-practice.md` before relying on a checkpoint for work preservation.
- Checkwork, Quiz and evidence export use the Lab's declared features. Reports
  are local self-checks, not authenticated or tamper-proof grading.

### Compact Machine Cards

Practice cards keep the account/host and home path in one header, with Terminal
as the primary action and a secondary GUI button when supported. GUI instructions
move to the button's hover/focus hint; connection status and warnings stay visible.
Each attached network has one badge, combining its name and declared IP. Networks
without an address in the Session response show a localized automatic-IP label,
not a guessed live address. The daemon currently reports declared addresses only.

The initial Lab file tree is collapsed behind a keyboard-accessible file-count
button. Expanding it never adds runtime-generated files or file-transfer actions.
The card resets expansion when its Session/node identity changes, not on a status
refresh. Narrow cards wrap actions and network badges instead of scrolling sideways.
The practice UI suite checks these layouts, automatic addresses, file expansion,
terminal slots, GUI capability gating, busy/stopped controls and visible warnings.

### Compact Library Tools

The Lab list reserves only two rows for its controls: the heading/count with
an Import icon and an overflow menu, followed by the always-visible search.
The toolbar is 104 logical pixels high with 12px before the scrollable list.
Saved results and submission review live in the overflow menu rather than
expanding full-width rows above the Labs. Opening it does not move the list.
The menu uses the shared popup shadow and dimmed backdrop; Escape/outside click
closes it and restores focus. Keyboard activation and daemon capability/busy
gating remain intact. Actions dispatch after the menu has closed, so subsequent
dialogs receive focus rather than competing with the menu.

Export belongs to the selected Lab's detail actions beside Edit/Clone/Delete,
not the list toolbar. Import remains accessible even with an empty library;
neither action bypasses the existing package dialogs or shared daemon API.
Compact widths retain the existing list/instructions tabs and these same tools.
The empty/search-no-match/offline message is centered within the remaining Lab
list viewport, below the toolbar, independently of the list's scroll position.

`python3 -I -B tools/check_notifications.py --suite library` checks toolbar
height, menu dispatch/dismissal/focus, capability and offline/busy gating,
search/empty lists, transfer icons/location, and light/dark/compact layouts at
70/100/150 percent zoom using temporary preferences and synthetic Lab metadata.

Verified on 2026-10-29: 18 Library checks pass against source and installed QML;
navigation/zoom pass 25/12 checks in both locations, and source notification/picker
regressions pass 20/24 checks. The wheel's private-bus MemoryRuntime smoke passes,
including actual page/header spacing, dirty-editor navigation and close guards.
Qt 6 qmllint is clean for the new toolbar and its test. The guarded update keeps
its rollback backup; all 234 runtime files match wheel SHA256
`577c608fc39997deba250bbc3295f0ee8b1584b520a1e19b703c5843670421cf`.
The normal installed launcher maps one `cyberlab-studio` window without QML
warnings; that exact verification instance is closed afterward. No production
package transfer, catalog modification or real-Docker Session is used to test
this layout change; manual desktop acceptance remains separate.

## Basic Authoring

1. Create a private draft or open a Lab for reviewed editing.
2. Add machines, choose an allowed environment/account and set terminal counts.
3. Configure private networks and node addresses. The daemon validates topology,
   image policy and conflicts; a suggested address is not a readiness guarantee.
4. Select a machine and add files/folders to its home tree. Folder imports preserve
   nested directories; replacing existing destinations requires confirmation.
5. Write/import Markdown instructions, then save to the Library. Studio saves,
   validates and runtime-checks the revision before publication/update confirmation.

Advanced controls hold custom startup commands, account IDs, resources, aliases,
dependencies, extra hosts, DNS and raw file mappings. Hiding them does not erase
stored declarations. Changing environments confirms the choice and preserves
custom settings rather than silently replacing an authored configuration.

File placement is described in `home-file-placement.md`; network and terminal
declarations in `network-terminal-configuration.md`. No example Labs are
installed automatically; create or import your own Lab through Studio.

## Layout and Preferences

### Brand Description

The subtitle beneath CyberLab is the fixed Vietnamese description
"Khong gian thuc hanh" (localized in QML), not the active page name. The selected
navigation tab conveys location. The brand area reserves 200 logical pixels
where text is shown; existing compact icon-only behavior is preserved.

Verified on 2026-10-30: 26 navigation checks pass on source and installed QML,
including unchanged subtitle across all three tabs and untruncated text at
520/640/1000/1100/1280 widths. The 12 zoom and 20 landing checks, targeted
qmllint and `git diff --check` also pass. Guarded deployment SHA256:
`d7f500b2e9a5c661516a91bea8eaa9b31036b6ddfae98f6b56c811a7cc170749`;
backup `/var/tmp/cyberlab-runtime-backup-hch9b77j`. Installed app-bar/window
components match source, and the normally relaunched Studio visibly displays
the fixed description. Production catalog and drafts were not changed.

### Draft Landing

The Create page uses a centered, 1040px-maximum content area. A 380px creation
card sits beside a matching draft-list card on wide windows; their top edges,
headers and 24px insets align, but each card has its own natural height. The
creation form never stretches with the draft count. Below 880 logical pixels,
the sections stack. Both reuse the shared low-surface, typography,
rounded-shape and spacing tokens. The create action spans the form width, with
guidance directly below the form. Saved drafts have a count, refresh action and
tonal rows inside one shared surface; the empty state is centered in that card.

Name and Lab ID still pass through `DraftService.create` unchanged except for
trimming. Enter moves from name to ID, then creates only when enabled. Busy and
unsaved-work guards remain in place; returning to the current draft does not
discard it. Keyboard focus scrolls the landing page into view at small sizes or
high zoom. Long draft lists remain virtualized and scroll within a bounded area.
No sorting, inferred IDs, new backend operations or catalog writes are added.

`python3 -I -B tools/check_notifications.py --suite landing` uses synthetic draft
metadata and isolated preferences. It covers creation, opening/refresh, busy and
dirty-state guards, 60 drafts, keyboard focus, dark/light colors, narrow/wide
windows and 70/150-percent zoom. The private-bus smoke fills and activates the
actual landing form before continuing the existing MemoryRuntime authoring and
publication checks; its `.landing.png` capture uses only the temporary catalog.

Verified on 2026-10-29: 18 landing checks pass against source, packaged and
installed resources; dialog/library/navigation/zoom/notification/picker
regressions pass 28/23/25/12/20/24. Targeted Qt 6 qmllint and the packaged
private-bus smoke pass, including `CYBERLAB_STUDIO_DRAFT_LANDING_PASS`.
The guarded updater installs wheel SHA256
`36d999a261f8bfb4bd3c0ed9ed9835bde72b89bed99c491be5cd290430e4af97`
with backup `/var/tmp/cyberlab-runtime-backup-m5dzo0sl`. All 241 runtime files
match the artifact, cyberlabd is active and Sessions remain empty. The active
desktop launcher's command opens a native `cyberlab-studio` window without QML
warnings; the exact verification instance is then closed. Release receipts and
isolated screenshots are in `/tmp/cyberlab-landing-release-20261029-tvyo7y8c`.
No real-Docker Session, production draft or catalog content is used as test data;
manual visual acceptance remains separate.

Alignment follow-up (2026-10-30): the matching-card layout passes 19 isolated
landing checks on source and installed resources, plus 55 editor regression
checks. Geometry assertions cover equal card heights/header positions, full-width
creation action, stacked layout and the five-draft/return-button case. Targeted
qmllint and `git diff --check` pass. Screenshots were reviewed at desktop and
compact widths in `/tmp/cyberlab-landing-alignment`.
Guarded deployment artifact SHA256:
`55171a0ad566c7b8616c00369d00f53b5362004f1fe8f19d656619928fa78e5e`;
backup: `/var/tmp/cyberlab-runtime-backup-y3t09qmu`.
The previous Studio window accepted a normal close without discarding edits;
its replacement launched through the normal installed launcher and loaded
successfully. The three installed landing components match source. No catalog,
draft or Session data was changed for these checks.

Natural-height adjustment (2026-10-30): per user feedback, cards now align only
at the top; the creation card no longer follows the list height. Removed the
stretch spacer so guidance stays immediately below the form. All 20 landing
checks pass against source and the built wheel, including stable creation-card
height with 0/1/6/60 drafts. Targeted qmllint and `git diff --check` pass.
Artifact SHA256: `22f307a194a316ad6a960b84471390ecbcdd5efb67fb7c9c8cc41094ee288603`;
wheel and receipt: `/tmp/cyberlab-landing-natural-release-kpw394qq`.
Deployment was initially deferred because the open creation form contained
input. On the follow-up, the form was empty and no Sessions were active; Studio
accepted a normal close. The exact artifact above was deployed with the guarded
updater, backup `/var/tmp/cyberlab-runtime-backup-3rwilraq`. Both changed installed
components match source, all 20 landing checks pass against installed QML, and
the normal launcher restored the user's Studio window with configuration loaded.
No production drafts/catalog were changed for verification.

### App Window

The top app bar includes a separate tonal Maximize/Restore and Close group.
Both icon buttons keep 48px interaction targets, keyboard focus and localized
tooltips/accessibility names. Close uses an error-colored state on hover/focus;
the remaining colors follow Studio's light/dark tokens. Compact headers move
the three navigation destinations onto their own row.

Drag the empty top bar or CyberLab brand to move the window with Qt's native
`startSystemMove()` request. Navigation and action buttons (including disabled
buttons) do not start window movement. This follows the compositor's normal
move behavior rather than assigning window coordinates or invoking host commands.
The navigation selection and window-control capsule have equal 4px outer insets
on every side; the buttons retain their 48px interaction targets.
The app bar owns the entire vertical gap: 8 logical pixels above its controls
and 8px below the navigation before page content. Pages retain their 12px side
and bottom insets, but do not add a second top margin. The private-bus window
smoke measures this combined header-to-page spacing at 70/100/150 percent zoom,
including the two-row compact header.
Local Import actions use the inward/down arrow and Export actions the outward/up
arrow consistently across library packages, drafts and practice file transfers.

Verified on 2026-10-29: the navigation suite passes 25 checks, including equal
capsule insets and drag exclusion over enabled/disabled controls. The zoom suite
passes 12 checks, including the drag region at 70/100/150 percent. The packaged
private-bus smoke verifies package/draft transfer icons and existing close
safeguards. After the guarded update, navigation/zoom checks pass against the
installed QML and a normal-launcher native window loads without runtime warnings;
the exact verification window is closed afterward. Physical pointer movement
under the user's compositor remains a manual acceptance check.

Maximize/Restore uses Qt's native window state, not fullscreen or a compositor
command. Close calls the same window close path as the desktop: unsaved editor
changes or a blocking backend operation still require confirmation, and closing
Studio never sends a Session stop/reset request. The isolated UI smoke checks
maximize/restore, dirty-draft cancellation, busy-close protection and clean close.

Verified on 2026-10-28: offscreen pointer/keyboard checks and private-bus Studio
smoke pass, including light/dark and compact headers. A separate native Wayland
window on Niri also passes maximize/restore and guarded-close checks; it is
closed afterward while existing user windows are preserved. These source and
packaging checks do not replace deployment through the guarded runtime updater.

Library uses list/detail panes, practice has a draggable guide/machines split,
and the editor fills its available workspace. Compact views switch to tabs
instead of squeezing both panes. Instructions have independently scrolling
source/preview panes; resizing preserves unsaved text and cursor position.

Settings contains System/Light/Dark appearance, application zoom
and Terminal. Ctrl+- zooms out; Ctrl++ or Ctrl+= zooms in; Ctrl+0 resets to 100%.
Zoom is bounded to 70-150% in steps of 10 percentage points and is also adjustable
in Settings > Appearance. It scales the header, content, icons, notifications and
popup overlay together, with layouts responding to the logical available size.
It does not change desktop scaling, terminal windows, Lab data or editor text.
The selected percentage persists per user in `studio.ini`; missing/invalid saved
values fall back to 100%. Shortcuts remain available inside modal dialogs.

`python3 -I -B tools/check_notifications.py --suite zoom` checks shortcuts,
limits, draft text preservation, preferences reload, scaled pointer targets,
resize, popup positioning and full-window modal dimming using temporary config.

Terminal discovery and selection use the local `cyberlab terminal-apps` CLI,
including when the daemon is disconnected. Rescan refreshes availability;
choices apply only to future windows, never migrate active attachments. A saved
but removed terminal is preserved in configuration with a temporary automatic
fallback and a warning. Appearance remains in `studio.ini`; the shared CLI/UI
terminal preference is in `terminal.json` under the user's CyberLab config
directory. Preferences are not Lab data or privileged D-Bus settings. Shared typography,
responsive thresholds and source components are documented in `studio-structure.md`.

## Verification and Limits

### In-App Notifications

Global API errors and `Backend.notify()` messages now use a shared notification
overlay at the upper-right of the Studio content, below the app bar. The overlay
does not reserve layout space or take focus when a message arrives. Cards use
Studio's light/dark tonal surfaces, semantic icon containers and a short slide
from beyond the right edge on entry, and return to the right on dismissal.
Toasts have a soft shadow but do not
dim or block the rest of the window.

At most one error and one ordinary notice are shown together. New messages
replace the card of the same kind; a success never hides an outstanding error.
Both errors and ordinary notices slide out automatically after five seconds,
including while hovered, keyboard-focused or the window is inactive. Replacing
a message restarts only that card's timer. Automatic dismissal hides the card
without clearing the underlying backend error. Text remains selectable plain text, with
scrolling for long diagnostics; backend error details are not rewritten.
Dismissal is available by the 48px close button or Escape while a card is focused.

This replaces the full-width global error strip and Studio's detached desktop
notification calls, avoiding duplicate OS popups. Contextual validation errors
inside forms/dialogs remain beside the relevant fields as compact icon/text
messages, without a full-width red banner. No daemon API or Session
behavior changes. `python3 -I -B tools/check_notifications.py` runs isolated Qt 6
checks; `--studio PATH` checks packaged QML and `--artifacts DIR` saves light/dark/
compact captures. The private-bus Studio smoke also checks the backend-to-overlay
connection without starting a real Lab or changing user data.

### Popup Surfaces

All modal dialogs share `StudioDialog`: settings, confirmations, file/folder
choosers, parameters, Quiz, Checkwork and submission review. They center in the
window overlay, dim the entire background with a 50% black scrim and block
background input until closed. Their existing acceptance, cancellation and
safe-action focus behavior is preserved, including nested confirmations.

`StudioPopupSurface` adds a soft rounded shadow to dialogs, toast cards and
combo-box menus. It uses ordinary Qt Quick rectangles, including on the software
renderer; no effects module, Qt upgrade or extra package is needed. Menus and
toasts that do not dim the background stay non-modal. The Library overflow menu
does dim and block the background. The notification checks also verify modal input blocking,
focus restoration, nested dialogs, shadow pixels and scrim removal in light,
dark and compact layouts.

### Reports, Review and Settings Layout

Checkwork results, offline submission review and Settings share a header with a
24px headline, contextual icon, short description and a 48px close target.
Their footer actions remain separate from scrollable content, with a quiet
divider and 24px horizontal padding. Shared modal corners are 28px. Dimmed
dialogs, including the file chooser and Library overflow menu, use the main
`Theme.surface` color rather than a brighter elevated fill; shadow, outline and
the scrim distinguish their layers. Non-modal combo menus/toasts keep their own
surface treatment.

Results and review center their empty/loading states in the result viewport;
small heights simplify the decoration instead of overlapping the footer.
Report export/delete appear only when a report is selected. The explicit delete
confirmation, exact selected report ID, self-check disclaimer, transfer picker
and busy/connection guards remain unchanged. Opening empty history focuses the
close button rather than a hidden check action. Review still clears its local
results and restores focus on close; selecting ZIP files uses the same API.

Settings uses Appearance/Terminal tabs above the content instead of a two-item
side rail. The selector is a full-width segmented capsule matching the main
navigation bar: shared dark surface, full rounding, equal slots, 4px inset and
an animated primary active pill. Each tab retains a 48px-high pointer target;
selection stays synchronized with programmatic page changes and dialog reopening.
Appearance groups color and zoom in compact cards;
the decorative preview no longer consumes space. Terminal displays its detected
selection in a summary card and retains Auto/manual selection and rescan. The
content scrolls at small sizes/high zoom; the footer always explains auto-save
and provides Done. Tab-arrow navigation stays on the tabs, while programmatic
section opening still focuses that section's first control.

`python3 -I -B tools/check_notifications.py --suite dialogs` runs isolated
light/dark, 380px-wide, 150%-zoom and short-window checks. It covers both empty
and populated report actions, safe deletion, review picker cancellation, focus,
Settings navigation/actions, background input blocking and the shared surface
color. The Library suite also checks centered empty/filter/offline messages.

Original modal redesign verified on 2026-10-29: the dialogs suite passes 26 checks and the Library suite
passes 23 checks. Navigation/zoom/notification/picker regressions pass 25/12/20/24;
the packaged private-bus smoke passes, the guarded update preserves the catalog
and configuration, all 237 runtime files match wheel SHA256
`5613138ce49acee9ff3571164a062f9a00dba7b86a66e77e4d49547fbf55988f`, and the
installed normal launcher opens without warnings before the exact verification
window is closed. No real-Docker Session or production catalog content is used.

Settings capsule follow-up verified on 2026-10-29: the dialogs suite passes 28
checks against source, wheel and installed resources, including selection
synchronization and full-height tab targets. Library/navigation/zoom/notification/
picker regressions pass 23/25/12/20/24; the isolated private-bus smoke passes.
The guarded update installs wheel SHA256
`0cdb0c905ab4b8f8319d3c180f324d5b896e82a2b46d57152b2e674ae46de281`;
all 238 runtime files match, cyberlabd is active and Sessions remain empty.
The updater retains backup `/var/tmp/cyberlab-runtime-backup-pdo6i5ul` and reports
the catalog/configuration unchanged. The active desktop launcher's command opens
a native `cyberlab-studio` window without runtime warnings; that exact verification
window is closed afterward. Release receipts are in
`/tmp/cyberlab-settings-finish-20261029-fpjk238v`. This delivery does not include
the subsequently requested Draft landing redesign.

### Draft Editor Surface

The draft editor uses one responsive MD3 toolbar instead of two competing rows.
It keeps the back action and draft status on the left, with Save, Check and the
primary library action grouped on the right; export, reload and delete stay in
an overflow menu so destructive or infrequent actions do not dominate the
workspace. The toolbar preserves the existing dirty, busy and confirmation
guards.

On wide windows, the editor has a 216px tonal navigation rail grouped into
`NỘI DUNG` and `HOÀN THIỆN`. Below 960 logical pixels it collapses to a 72px
icon-only rail rather than a dropdown, retaining all seven destinations as
directly selectable tabs. Group headings become a quiet separator. Icon tabs
keep at least 48px targets, accessible names and hover/focus labels. Short
windows can scroll the rail; keyboard navigation reveals the focused tab.
The selected destination uses the same primary-container pill as the rest of
Studio, with keyboard Up/Down/Home/End navigation and no change to the
underlying `DraftService` section state.

Each section is centered in a bounded 1040px content column. Metadata, machine
and network configuration, resources, review and Labedit content use the shared
`DraftFormCard` surface; machines and networks use selectable object cards with
stable dimensions and a clear selected state. Empty machines, networks and
files use the shared empty state rather than a stretched blank panel.

Markdown keeps independently scrolling source and preview panes. The compact
review result uses `StudioDialog`, including the normal scrim, rounded surface,
shadow and Escape/focus behavior. No CLI, daemon, Engine, schema or catalog
behavior changes in this redesign.

`python3 -I -B tools/check_notifications.py --suite editor` runs the isolated
editor suite. It covers 39 checks across wide/compact layouts, dark/light
themes, zoom-responsive conditions, all seven sections, six Labedit
categories, unsaved text, stale revision reports, overflow actions and the
modal review surface, icon-rail keyboard scrolling and preservation of section
selection/unsaved work across resize. Screenshots are written only to the requested temporary
artifact directory.

Verified on 2026-10-29: the editor suite passes 37 checks against source, wheel
and installed resources (including QtTest initialization/cleanup rows).
Landing/dialog/library/navigation/zoom/notification/picker regressions pass
18/28/23/25/12/20/24. The packaged private-bus smoke passes without QML warnings
after fixing the shared form card's implicit-width sizing loop.
The guarded updater installs wheel SHA256
`b7aa449068ad995e81a648930265f3e131a3a7f151dbc5a3359f8fe5022c6cd9`, retaining
backup `/var/tmp/cyberlab-runtime-backup-nfuyy1_b`. All 246 runtime files match
the wheel; cyberlabd is active and Sessions remain empty. No Studio window was
open at deployment. The active desktop launcher's command subsequently opens
native window 51 without QML warnings; only that tracked verification instance
is closed. Receipts are in
`/tmp/cyberlab-editor-release-20261029-final-5HMPDD` and installed editor captures
in `/tmp/cyberlab-installed-editor-20261029-7PDaOR`. No real-Docker Session or
production catalog/draft is used as a fixture. Visual acceptance remains manual.

Compact-rail follow-up verified on 2026-10-29: the dropdown is removed; narrow
windows retain the vertical icon tabs. The editor suite passes 39 rows against
source, wheel and installed resources, including resize/dirty-state retention,
48px targets and keyboard scrolling in short windows. Landing/navigation/zoom
regressions pass 18/25/12, and packaged private-bus smoke has no QML warnings.
The guarded updater installs wheel SHA256
`d86a4f0b4aa63795f0eb43d306d8c775c66940a5e5f3286322cb8f94b95fe46f`, with backup
`/var/tmp/cyberlab-runtime-backup-lmnbiv_c`. All 246 runtime files match; only
the navigation, workspace, narrow Markdown tabs and editor test differ from
the previous wheel. No Studio window is open at deployment; cyberlabd is
active and Sessions remain empty. Normal launcher window 54 loads without
warnings and is closed with its exact process group afterward. Receipts and
isolated screenshots: `/tmp/cyberlab-iconrail-release-20261029-l2Ch8b`.

### Studio File and Folder Choosers

Import/export, Markdown and home-file authoring, workspace transfers and
submission review use the shared `StudioFileDialog`/`StudioFolderDialog`.
They use Studio's typography, light/dark colors, rounded surfaces, localized
buttons and shared motion tokens instead of Qt's differently styled fallback
file dialog. The MD3 chooser uses a places sidebar, a responsive thumbnail grid
and a right-hand preview pane, with the same CyberLab color tokens as Studio.
Below 900 logical pixels the preview is hidden; below 760 the places sidebar is
also hidden, leaving more room for the grid. App zoom applies to the whole
chooser, including its dimmed modal overlay.

The picker supports local paths, home/download/documents/pictures shortcuts, parent
navigation, file filters, hidden files, multiple selection and save suffixes.
Arrow keys move between cards in both dimensions, Space selects a card, Enter opens it and Escape
cancels. Cancel does not invoke the transfer callback; focus returns to the
caller. Unreadable/invalid paths and stale selections are rejected. Destinations
already present in the visible list report an inline no-overwrite error; the
existing CLI/daemon checks remain authoritative for hidden/filtered entries,
permissions, bounds and races. Choosing a destination never writes a file itself.

Directory metadata is listed with the public `Qt.labs.folderlistmodel` only
while a chooser is open. Dot entries are kept for path validation but removed
from the visual model, so they never leave empty grid cells. Selected files use
canonical local URLs so spaces, Unicode, percent signs and hashes keep their
selection indicator. Preview metadata clears when the folder/filter changes.
Common image formats get asynchronous, size-bounded thumbnails and a larger
aspect-preserving preview when Qt has a decoder; other entries use file/folder
icons. Text file contents are not previewed. No shell, external file manager, privileged helper,
new transport or direct Docker access is involved. The picker only returns a
local URL to the existing transfer callback; it never edits the catalog.

Run `python3 -I -B tools/check_file_picker.py` with Qt 6 qmltestrunner installed.
Optional `--artifacts /tmp/cyberlab-picker-artifacts` retains dark/light/compact
screenshots and the test log. `--studio PATH` checks a packaged Studio directory.
The runner isolates HOME/XDG state, uses temporary file and image fixtures, verifies their
contents remain unchanged and cleans up its process group. It neither installs
dependencies nor connects to the production daemon.
The installer also probes the folder-list module; its Debian/Ubuntu dependency
plan includes `qml6-module-qt-labs-folderlistmodel`. App-only updates still do
not install or upgrade host packages.

Previous list-based chooser verification on 2026-10-28: the picker suite reported 17 passing checks against both
the packaged and installed QML, including light/dark/compact captures and focus
handoff to a replacement confirmation. The private-bus MemoryRuntime Studio
smoke and native module probe pass. The guarded app update completes, installed
picker files match the source, and the normal desktop launcher opens one Studio
window with AppId `cyberlab-studio`. No production import/export is performed
for acceptance; real user file transfers remain a separate manual check.

MD3 grid/preview verification on 2026-10-29: 24 picker checks pass against the
source, wheel and installed QML, including real temporary image previews,
empty-folder navigation, stable hover/press state, URL-safe selection and
dark/light/compact captures. The zoom suite has 11 passing checks (including
the chooser at 70/100/150 percent); navigation and notification suites pass
21 and 20 checks respectively. Qt 6 qmllint is clean for the changed chooser
components and tests. The private-bus MemoryRuntime smoke passes. The guarded
runtime update completes with backup, installed resources match the wheel and
a normal-launcher native window loads without QML warnings. That exact
verification instance is closed afterward; no production transfer is performed.

### Runtime Checks

UI checks must be offscreen, isolated from production data and cleaned up by
process group. Preserve the user's main window and unsaved editor work; do not
use blanket process-name kills or leave duplicate visible test windows.

Static validation, MemoryRuntime smoke checks and real-Docker acceptance are
different checks. Unsupported capabilities must remain unavailable rather than
being implemented with direct Docker calls. See `labedit-parity.md` for the full
inventory and outstanding acceptance/policy decisions.
