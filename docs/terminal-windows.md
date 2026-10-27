# Configured Terminal Windows (0.4.0)

## Workflow and Architecture

On the Ubuntu VM desktop, `cyberlab start demo-basic` now requests a separate
Konsole window for each node listed in the Lab's optional `terminals` field:

```yaml
terminals: [client, server]
```

1. CLI requests StartLab over System D-Bus as before.
2. The daemon/engine creates the restricted containers and isolated networks.
3. The daemon replies with the Session state and terminal plan from its captured
   Lab template. The CLI prints the Session JSON before attempting any windows.
4. Only when the state is RUNNING, the CLI launches the configured windows in
   order. Each runs the same Python environment's `cyberlab_cli.main terminal
   SESSION_ID NODE_ID`, which connects through the existing daemon API.

The architecture is unchanged. The daemon never starts Konsole, and the engine
does not import GUI code. No Quickshell, new privileged API, protocol, session
agent, Docker access in the CLI, or system service change is introduced.

The Lab schema accepts up to four unique declared node IDs. The optional field
is backwards-compatible for new readers of old v1 definitions. No window title,
host command, shell script, emulator path, or profile comes from the Lab. The
CLI also validates the returned plan before launching, then uses a fixed
`/usr/bin/konsole --separate --builtin-profile -e ...` argv with no shell.
The child Python invocation uses `-I`, and private D-Bus test mode is propagated
only when the parent CLI was explicitly started in that mode.

Both Lab and Session D-Bus dictionaries include `terminals: as`; existing field
types and method signatures are unchanged. GetCapabilities adds `terminal-plan`.
Using the Session's plan avoids a race with a changed catalog after StartLab.

## Headless and Failure Behavior

```sh
cyberlab start demo-basic --no-terminals
```

This starts the same lab without launching windows and is the recommended form
for scripts and verification. The updated administrator verifier uses it whenever
the daemon supports terminal plans. Old daemons remain compatible with the
verifier's older start invocation.

Automatic windows also require non-root execution, interactive stdout, a DISPLAY
or WAYLAND_DISPLAY, and executable `/usr/bin/konsole`. Otherwise the CLI keeps
the RUNNING Session and prints manual attachment commands to stderr. Redirected
JSON output therefore never opens windows. Missing/empty plans (including replies
from older daemons) open nothing. A failed StartLab opens nothing. Status, stop,
and reset do not launch windows or silently attach a second time.

Launch diagnostics use stderr so stdout stays valid Session JSON. If one window
cannot be started, the remaining configured nodes are still attempted. A failure
to open a window does not stop/delete the Session, retry StartLab, or change the
successful start exit status. The CLI checks for immediate Konsole exits but
cannot guarantee a visible window or successful attachment: “Requested terminal
window” is not an acknowledgement from the node shell. If a window fails later,
use the printed Session ID with `cyberlab terminal SESSION_ID NODE_ID`; do not
start another Session just to recover a window.

`Ctrl+]`, `exit`, and window closure affect the attachment/shell as described in
`terminal-mvp.md`; they do not stop the Lab. Explicitly run `cyberlab stop
SESSION_ID` on the host when finished. The CLI records the PIDs and process
groups of windows it launches in the user's runtime directory. A confirmed
`STOPPED` response then sends `SIGTERM` through Linux pidfds to verified Konsole
processes belonging to that Session (not to an arbitrary stored process group);
stale or already-closed PIDs are ignored. Windows opened manually with
`cyberlab terminal` are not tracked and must still be closed manually.

## Shared Studio launcher

`cyberlab open-terminals SESSION_ID` fetches the Session over the same daemon
API and opens its configured auto-open slots, including when stdout is captured
by Studio. `--node NODE_ID --slot N` requests one declared slot even if that node
is not configured for auto-open. Non-root execution and a graphical desktop are
still required. Studio delegates all window launches to this CLI command; it no
longer constructs a separate Konsole invocation.

After a successful reset, the CLI requests closure of old tracked windows and
Studio opens the reset Session's configured windows. Failed stop/reset replies
do not signal windows. Tracking failures are warnings, not a false failure of
the completed lifecycle operation. A requested close is not a GUI confirmation.

Registries are separated by system bus versus private test-bus address. Updates
are locked, records are bounded, and cleanup checks UID, process start time and
the exact Session-bearing CLI command before signaling a pinned process handle.
Old unnamespaced registry files are not trusted for cleanup; windows opened by
the previous launcher may need to be closed manually once after upgrade.

## Update the Existing VM

The installed 0.3.1 runtime has passed real-Docker verification. This coding task
does not stop it, alter system files, or install 0.4.0. The repository example
`demo-basic` is now version 1.1.0 and contains `terminals: [client, server]`.
Updating only the application wheel will **not** change an installed Lab, so this
release provides an explicit, guarded `--update-demo-basic` repair option.

Review changes and build/check the bundle as student (skip build if it exists):

```sh
cd /home/student/CyberLab
.venv/bin/python tools/deploy_mvp.py build dist/mvp-windows-0.4.0
.venv/bin/python tools/deploy_mvp.py check dist/mvp-windows-0.4.0
```

**Stopping the daemon deletes all current MVP Sessions and their temporary
container data.** Finish all users' lab work and inspect `cyberlab sessions`
before running this administrator update in the VM terminal:

```sh
sudo systemctl disable --now cyberlabd.service &&
sudo /usr/bin/python3 -I tools/deploy_mvp.py repair dist/mvp-windows-0.4.0 --uid "$(id -u)" --update-demo-basic
```

The normal repair trust checks and no-leftover-resources requirement still apply.
The optional Lab update accepts only the byte-for-byte original bundled demo
(identified by its known SHA256) or one already identical to the new bundle.
Customized definitions are refused, not overwritten. A copy of the previous
definition is retained in the root-private repair staging directory and checked
before package installation. The new definition is validated using the installed
schema before root-owned installation to the fixed `demo-basic/lab.yaml` path.
Other labs, daemon configuration, policy, dependencies, unit, and account
permissions are unchanged. Without the option, repair still preserves all labs.

As before, failure retains the deployment and staging files, with no automatic
rollback. A package may already have been updated if later validation fails.
Read the error; do not delete all Docker resources or blindly rerun the installer.

## Desktop Acceptance Test

After the administrator command reports DONE, use a normal Konsole as student:

```sh
cyberlab info
cyberlab show demo-basic
cyberlab start demo-basic
```

Expect version 0.4.0, a `terminal-plan` capability, and a `terminals` list containing
client/server. A RUNNING Session JSON should appear, then two new Konsole windows.
In each window run `id`, `hostname`, and `pwd`: expect UID/GID 65534, respectively
client/server, and initially `/tmp`. This test checks windows and attachment,
not packet delivery between nodes. Stop the Session afterwards on the host.

The automatic test suite checks schema compatibility/reference validation,
immutable Session plans, exact launcher argv, test-bus propagation, headless/root
guards, no-terminal mode, launch failures, JSON ordering, and guarded demo update.
The existing private-bus smoke test checks terminal plans and actual CLI TTY I/O
using MemoryRuntime. Launcher tests mock process creation; **they do not prove
visible Konsole windows on the VM**. The administrator verifier still checks real
Docker lifecycle and a CLI shell, but it deliberately does not spawn GUI windows.
Visible-window acceptance remains the student's desktop test above.
