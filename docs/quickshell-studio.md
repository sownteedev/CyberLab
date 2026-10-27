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
Konsole must be available for automatic terminal windows.

The old fixture-based `--demo`/`--smoke` tools were archived outside the
checkout. The compatibility `tools/run_studio.py` entry point preserves old
source shortcuts but refuses those preview flags before starting anything.
Normal Studio is not a disposable preview and can change real user data.
An already-installed legacy AppImage can still be used without
`--require-native` on the old VM; new installations neither fetch nor require it.

See `install-mvp.md` for desktop dependencies, shortcut targets and updates.

## Library and Practice

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

Library uses list/detail panes, practice has a draggable guide/machines split,
and the editor fills its available workspace. Compact views switch to tabs
instead of squeezing both panes. Instructions have independently scrolling
source/preview panes; resizing preserves unsaved text and cursor position.

Settings contains System/Light/Dark appearance and Reduced motion. Preferences
are local user configuration, not Lab data or D-Bus settings. Shared typography,
responsive thresholds and source components are documented in `studio-structure.md`.

## Verification and Limits

UI checks must be offscreen, isolated from production data and cleaned up by
process group. Preserve the user's main window and unsaved editor work; do not
use blanket process-name kills or leave duplicate visible test windows.

Static validation, MemoryRuntime smoke checks and real-Docker acceptance are
different checks. Unsupported capabilities must remain unavailable rather than
being implemented with direct Docker calls. See `labedit-parity.md` for the full
inventory and outstanding acceptance/policy decisions.
