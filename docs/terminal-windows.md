# Native Terminal Selection and Session Windows

## User Workflow

Studio > Settings > Terminal shows the selected application and why it was
selected. With two or more compatible terminals, the selector offers Auto plus
the installed applications. With one, its name is shown without a selector.
Rescan checks again after software is installed or removed. Changes affect only
future windows and never migrate or close existing attachments.

The same unprivileged preference is used by the CLI:

```sh
cyberlab terminal-apps
cyberlab terminal-apps --set blackbox
cyberlab terminal-apps --set auto
```

These commands return JSON and work without connecting to cyberlabd. Preference
storage is `$XDG_CONFIG_HOME/cyberlab/terminal.json`, or
`~/.config/cyberlab/terminal.json`; only a version and known terminal ID are
stored. Writes are atomic and user-private. Appearance's `studio.ini` is
unchanged. Reads never repair or overwrite a malformed preference file.

Selection order:

1. Available explicit CyberLab choice.
2. XDG default: query `xdg-terminal-exec --print-id` if installed, otherwise
   consult desktop-specific and generic `xdg-terminals.list` files in XDG
   configuration/data order. Unsupported helper results fall back to the lists.
3. `TERMINAL`, when it identifies a supported executable, not a shell command.
4. A supported target of `x-terminal-emulator`.
5. The first available adapter ID in stable alphabetical order, respecting
   fallback exclusions read from XDG lists.

The helper is queried only if its help advertises `--print-id`; older helpers
fall back to the lists without receiving an unsupported launch argument.
Unknown XDG directives/entries are ignored. Desktop action IDs select the
application; custom action commands/profiles are not imported into CyberLab.
There is no prompt blocking the first launch. If a saved application disappears,
its ID remains saved while Auto is used temporarily and a warning is shown.

## Supported Native Applications

Black Box, Konsole, GNOME Terminal, GNOME Console, Ptyxis, Xfce Terminal, Kitty,
Foot, Alacritty, Ghostty, WezTerm, Tilix, MATE Terminal, LXTerminal and XTerm have
explicit command adapters. Discovery checks executable native binaries on
absolute PATH entries, deduplicates aliases and does not launch them. Flatpak,
Snap, custom shell wrappers and arbitrary user-entered launch commands are not
supported. Discovery is not proof that an application can render on the current
desktop or that its native libraries are healthy.

The installer reuses existing compatible applications. Only an empty inventory
adds `xfce4-terminal` to the reviewed dependency transaction; it does not install
the Xfce desktop or replace the OS default. Check/update/no-deps never install
terminal packages. If discovery cannot run yet, do not infer an empty inventory.

## Architecture and Launch Contract

Studio calls `cyberlab open-terminals SESSION_ID`, optionally with
`--node NODE_ID --slot N`. Start/resume use the same launcher unless
`--no-terminals` is passed. Each terminal runs the same Python environment's
`cyberlab_cli.main terminal` client with isolation (`-I`). The client attaches
through the existing System D-Bus API; the daemon/Engine never launch GUI
applications, and UI/CLI never access Docker directly.

The returned Session snapshot supplies the declared nodes, slots and display
metadata. No executable or host command comes from a Lab. Every adapter passes
display titles as encoded CLI data, avoiding emulator-side variable expansion;
the attached client decodes and sets the bounded title. Every adapter uses
an explicit argv without `shell=True`. Black Box 0.15 internally runs commands
through its configured shell even when given `--`; its adapter therefore uses
`--command` with a fixed `exec` and individually quoted CLI arguments. Lab
metadata remains literal data, never shell syntax. Tilix receives a quoted
command string for its GLib argv parser, not a shell. Other adapters pass the
child argv directly. Konsole retains grouped tabs based on its built-in profile:
private per-tab profiles preserve quoted argv, because the tab file's `command:`
field splits on spaces without respecting quotes. Titles are stripped of control
characters/separators. Other applications receive one launch per slot, retaining
group/title context. Private test-bus mode is propagated only when explicitly
selected by the parent CLI.

Automatic CLI windows require a non-root graphical session and interactive
stdout. Studio's explicit open command may capture stdout. Without a desktop,
CLI start/resume keep the Session and print manual attachment instructions:

```sh
cyberlab terminal SESSION_ID NODE_ID --slot 0
```

The direct terminal command and `--no-terminals` remain independent of graphical
terminal discovery. Window failures never retry StartLab, stop/delete a Session
or change a successful start into a failed Lab operation. The explicit
`open-terminals` command returns a nonzero status on launch/attachment failure
and adds `terminal_launch` diagnostics to its Session JSON for Studio.

## Attachment Tracking and Cleanup

Each managed launch gets a unique identifier. After a successful D-Bus attach,
the child CLI registers its own PID, process start time, interpreter and exact
Session/node/slot argv in the private per-user runtime registry. The launcher
waits up to five seconds for confirmation. A terminal application's launcher
exiting with code zero is not itself a failure: GUI applications may forward
requests to an already-running process. Lack of confirmation is reported, not
silently treated as successful attachment.

After confirmed stop/suspend/reset/submission completion, cleanup signals only
the verified child CLI using pidfds. It never terminates a shared terminal
application or broadcasts a process-group/name kill. Manual host terminals are
not registered. Stale PID/start-time mismatches and legacy emulator-only records
are ignored; an old record never authorizes killing an emulator. Normally the tab/window
closes when its child exits; a user's hold-open preference may leave an exited
tab to close manually. Detaching/closing a terminal does not stop its Lab.

## Validation

Run isolated regression checks with a Python environment containing the project
dependencies:

```sh
python -I -B tools/check_terminal_apps.py
```

Checks cover selection precedence, multiple/single/absent applications,
malformed/stale/symlink preferences, literal argv, slots, grouped-tab quoting,
shared-process launch acknowledgement, stale/foreign process rejection and
mocked package plans for four distro families. They never call real Docker,
the production system bus or package managers.

The existing Studio smoke supports `CYBERLAB_STUDIO_TERMINAL_SETTINGS_TEST=1`
with a private test bus and a config root below `/tmp/cyberlab-terminal-*`.
It checks selection, rescan and dialog reopening; a second offscreen process
can set `CYBERLAB_STUDIO_TERMINAL_EXPECTED=ID` to assert persisted selection.
`CYBERLAB_STUDIO_TERMINAL_COUNT=N` asserts an inventory isolated via PATH;
the selector must be hidden for zero/one application and visible for several.
Fixtures, draft storage and config must all be temporary. Clean up only tracked
test processes; preserve the user's Studio and terminal windows.

Mocked adapters are not certification of every terminal/distro/version.
Validate real Black Box/Konsole attachments with MemoryRuntime on a private bus,
and report actual coverage separately from real-Docker/manual acceptance.
Runtime rollout uses the guarded updater after every allowed user's Session is
STOPPED, preserves unsaved editor work and never modifies production Labs.

### Local Verification (2026-10-28)

- 28 isolated regression checks pass, including mocked dependency plans for
  Arch, Debian/Ubuntu, Fedora and openSUSE. No package manager was invoked.
- Offscreen Studio smoke passes with zero, one and two native applications,
  compact Settings, save/rescan/reopen and persisted choice after restart.
- Real Black Box and Konsole attach three slots against a private MemoryRuntime
  daemon. Busy-slot rejection, reset, suspend/resume and stop pass; an unrelated
  Black Box control tab survives Session cleanup. A Python path containing spaces
  and titles containing spaces/quotes also pass, including grouped Konsole tabs.
- Other adapters have argv regression coverage, not live graphical acceptance.
  These checks do not exercise real Docker, the production catalog or user work.
- The installed runtime is not updated by these checks. Deployment still needs
  the guarded updater, all-users STOPPED verification and preserved editor work;
  this development session has no noninteractive administrator access.

Verified candidate: `cyberlab_engine-0.9.0-py3-none-any.whl`, SHA-256
`d464d7c0fd527e1ca2f689276511efdec02bf5094d52df23d9ee1d520a0ecbd0`.
The 28 checks, offscreen Studio and native Black Box/Konsole lifecycle checks
also pass using this wheel extracted into a temporary venv; it is not an
installed-runtime receipt.
