# Ubuntu workstations

The 2026-10-30 request for a Labtainer-like Ubuntu environment introduces an
explicit administrator-enabled workstation tier. This is not full Labtainer
parity or a full virtual machine. The shared System D-Bus architecture remains
unchanged: Studio/CLI -> cyberlabd -> Engine -> Docker.

## Learner experience

- Select **Ubuntu 24.04 (sudo / apt)** when authoring a machine. Its reviewed
  profile defaults to `student` (UID/GID 2000), Bash, `/home/student`, 512 MiB RAM and
  one CPU. The host's username, home and UID are unrelated.
- Seed assets are copied into `/home/student`, not mounted from the catalog.
- Run `sudo apt update` and `sudo apt install neovim` inside the lab terminal.
  This installs into the container only, not the Arch host.
- A declared network can carry both Lab traffic and outbound Internet through
  the same interface; Studio exposes an **Internet** switch on each network.
  No extra `packages` card is added. Legacy Ubuntu Labs default to Internet on
  their first attached network unless explicitly disabled. Standalone machines
  without a declared network retain one Session-owned outbound bridge.
  Outbound access can reach external/LAN services permitted by the host's
  routing/firewall; it is NOT an Internet-only destination filter. No inbound
  ports are published. See `network-terminal-configuration.md` for defaults.
- Save/Suspend checkpoints the writable Ubuntu filesystem, including installed
  packages and home. Resume creates containers from the exact saved image IDs.
  Processes, `/tmp` and `/run` are not checkpointed; this is not live VM migration.
  Wait for package operations to finish before saving. Stop without saving loses
  changes since the last save. Reset intentionally discards saved system state.
- The existing file browser/export and assessment limits still apply to home
  files. Full system checkpoints are private Docker images, not portable Lab
  packages or submission exports. Packages installed in one Session do not
  modify the Library template or another Session.
- systemd boot, host-display forwarding, host devices, nested Docker, kernel changes,
  privileged networking and arbitrary images remain unsupported.

### Default username (2026-10-30)

Open **Settings -> May lab -> Username mac dinh**, enter a name and press Save.
The default is stored per desktop user in
`$XDG_CONFIG_HOME/cyberlab/lab-defaults.ini` (normally `~/.config`). Nothing is
saved until Save/Enter; invalid stored names fall back to `student` without
silently rewriting the file. Names are 1-32 lowercase ASCII characters, start
with a letter, and may then contain digits, underscore or hyphen. Reserved
system names are rejected; the daemon is the authoritative validator.

This preference affects newly added Ubuntu machines and machines explicitly
switched to Ubuntu. Existing drafts, published Labs and Sessions are unchanged.
The chosen identity is part of the Lab definition, not a runtime substitution
from a user's Settings. Another learner receives the same account specified in
that Lab. CLI authors can declare the same validated `user` object directly;
an older daemon without the `custom_username` capability keeps using `student`.

In the draft machine editor, Ubuntu also exposes an editable **Username** field.
Press Enter or leave the field to apply a valid name to that machine; its home
and automatic terminal title follow the account. Invalid names show an inline
error and do not replace the previous account. Other images and older daemons
keep the existing-account selector. This edits the draft only, not the global
default or an existing Session; save and review publication as usual. Relative
home-file targets are preserved; custom commands or absolute paths referring
to the previous home are not rewritten and should be reviewed by the author.

On a fresh custom-name container, a fixed startup procedure renames the image's
student account/group, moves the empty home to `/home/<name>`, updates the
container-only sudo rule, and drops to UID/GID 2000 before seeding/running the
node command. Names and commands are separate argv values, never interpolated
into shell source. It rejects an existing account/group or home instead of
overwriting it. Bootstrap root is confined to the container; terminal exec uses
UID/GID 2000 and validates the declared identity. Saving retains this account
and home in the system image; resume never re-runs the rename procedure, while
reset provisions it again from the original image. No image rebuild is needed.

Username verification: isolated tests cover invalid names, fixed setup argv,
no rename on restored images, existing-draft preservation and old-daemon
fallback. Offscreen Settings checks cover Save, cancelled edits, tab reopening,
compact/zoomed layouts and persistence across four fresh Qt processes (including
corrupt preference recovery). Administrator fixture acceptance with `--username
alice` passed `/home/alice`, seed ownership, sudo/apt, package retention across
suspend/reload/resume and reset; it used no production data.

## Security boundary

Only `cyberlab/ubuntu:24.04-1`, explicitly present in both `allowed_images` and
`workstation_images` in trusted daemon configuration, receives workstation
permissions. Lab YAML cannot request privileged mode, mounts, capabilities or
host networking. The prepared image carries a versioned label and no volumes.

Workstations have a writable container root filesystem and allow sudo to root
inside the container. They retain `privileged=False`, Docker's default seccomp
and platform security policy, dropped capabilities with a bounded allowlist,
resource limits, and no host mounts/socket/ports. `SYS_ADMIN`, `NET_ADMIN`,
`SYS_PTRACE`, `MKNOD` and `NET_RAW` are not granted. `no-new-privileges` cannot be
enabled in this tier because it prevents sudo's intended setuid transition.
This is a deliberate relaxation compared with the restricted BusyBox tier,
not a VM-strength boundary for hostile root code on a personal host.

BusyBox and existing Labs retain the restricted read-only/non-root/internal
network policy. Merely adding an arbitrary image to `allowed_images` does not
enable this tier. Ubuntu identity must use the validated name, UID/GID 2000,
Bash and matching `/home/<name>` path.

## Preparation and deployment

No host packages, desktop dependencies or repositories are installed by this
workflow. The reviewed helper only pulls an Ubuntu base and builds the fixed
recipe. It resolves the downloaded base to an immutable image ID before build,
records recipe/base/output identities, and refuses to overwrite an existing tag.

1. Review `python3 tools/prepare_ubuntu_workstation.py plan`.
2. Stop all allowed users' Sessions explicitly and preserve unsaved Studio work.
3. Build/test the runtime wheel and deploy it through `tools/upgrade_runtime.py`
   with its exact SHA-256 and existing backup/rollback safeguards.
4. As administrator, run `tools/prepare_ubuntu_workstation.py build --uid UID`.
5. Run `tools/prepare_ubuntu_workstation.py enable --uid UID` as administrator.
   It checks all-users STOPPED again, backs up config, adds only the reviewed
   image/policy, restarts the existing daemon, verifies profiles and preserves
   catalog identities; failure restores the old configuration.
6. Refresh Studio, select Ubuntu and publish a new Lab or explicitly review an
   installed-Lab update. Existing Labs/drafts are never migrated by this tool.

Use the host's authentication dialog (`pkexec`) when needed; never share a
password in chat. This workflow must not run the unrestricted Docker adapter
on a test-session D-Bus daemon. Live acceptance uses a separately tracked
administrator-owned fixture container, never a production Lab or Session.

## Checkpoint bounds and recovery

Saved image references live in the root-private practice database (schema 8).
Restore checks immutable IDs and Session/owner/node labels. Missing images fail
explicitly and retain the checkpoint; there is no fallback to a fresh machine.
Checkpoint image size is capped at 2 GiB per node and 12 GiB aggregate retained
image size (conservative: shared base layers count multiple times). These are
save limits, not a writable-layer disk quota; active apt downloads can still
consume host disk. Existing Session/save quotas also apply.

New image captures are discarded if the database transaction fails. Replaced
or discarded checkpoints are collected only after database commit; referenced
images and images used by live containers are never forcibly removed. Startup
collects orphan checkpoint images after the normal container cleanup. No Docker
prune or unlabelled resource removal is performed. Administrator image deletion
outside CyberLab can make saved practice unrecoverable.

Run `python tools/check_workstations.py` using the runtime's dependencies for
isolated policy, SDK argument, checkpoint, rollback and config tests. Mocked
checks are not evidence that apt, network access or live recovery works.

## Verification on 2026-10-30

- 20 isolated Python checks pass, including SDK-signature mocks, schema-7
  checkpoint migration, failed-save handling and restricted BusyBox lifecycle.
- 49 editor and 28 dialog offscreen checks pass, including Ubuntu defaults.
- The explicit administrator fixture passed student/Bash/home/seed/dir/sudo,
  apt update + Neovim installation, suspend + fresh Engine + resume retaining
  Neovim and a home file, and reset restoring the base image and seed.
  All fixture containers/networks/checkpoints were removed; production catalog
  and practice database were not used. This does not certify every apt package,
  desktop service or multi-machine network layout.
- Prepared image: `cyberlab/ubuntu:24.04-1`, ID
  `sha256:9762f2079bab9959226209d45d92a168b4a8959c0c9e6c5b139216144e11f5ab`.
  Build receipt: `/var/tmp/cyberlab-ubuntu-build-5tdgt81r/receipt.json`.

### Username Settings follow-up (2026-10-30)

- 22 isolated workstation checks, 50 editor checks, 34 dialog checks and 12
  zoom checks pass. Four isolated preference processes verify save, restart,
  invalid configuration fallback and repair without changing user settings.
- The administrator-owned `alice` fixture passed identity/home/seed ownership,
  sudo, apt installation, suspend/resume and reset. Fixture cleanup completed;
  the production catalog and practice database were not used.
- Guarded updater deployed `cyberlab_engine-0.9.0-py3-none-any.whl`, SHA-256
  `9af2eb3b8c3bf52d338ec8d34b3505f7340680422258e83102b6581c2cd3e30d`.
  Backup: `/var/tmp/cyberlab-runtime-backup-k43eu68_`.
- The installed daemon advertises custom usernames; installed workstation
  policy, bootstrap and Settings view match source. All 34 dialog checks also
  pass against installed QML. The normal launcher created a Studio window and
  loaded its configuration; only that verification window was then closed.

### Per-machine username field fix (2026-10-30)

- Replaced the Ubuntu account selector with a validated text field. Offscreen
  checks exercise real typing, Enter/Tab, invalid names, home/title updates,
  node switching, compact layout and fallback for older daemon profiles.
  All 55 editor checks pass on source and installed QML; 34 dialog checks pass.
  The new component passes qmllint and the patch passes `git diff --check`.
- Guarded deployment artifact SHA-256:
  `b6e80d15de22d36393ff0f1ab813bbcd6e97d7f10aaec1204fd892502b6761ff`.
  Backup: `/var/tmp/cyberlab-runtime-backup-6zu6qpgj`.
- Installed editor components match source; normal launcher verification loaded
  Studio successfully. Only the tracked verification window/process group was
  closed. No production drafts/catalog or real-Docker Sessions were changed
  for this UI fix; the earlier custom-account runtime acceptance still applies.

### Separate graphical application windows (2026-11-02)

The former TigerVNC/Openbox full-desktop path is replaced by Xpra **seamless**
mode. The intended workflow is Labtainer-like: launch an application inside
the lab terminal and receive its individual window on the host. It is not
direct sharing of the host X11 display, nor a claim of Labtainer import parity.

Studio's **Ứng dụng** action is available only for administrator-enabled Ubuntu
nodes. Confirm installation once for each machine that needs GUI applications:
the daemon installs a fixed set (`xpra`, `xvfb`, `xauth`, `dbus-x11`,
`fonts-dejavu-core` and `python3-pil`)
inside that machine. It never runs host apt. Save practice to retain packages;
reset discards them. Terminal-only machines need no guest GUI installation.

After enabling, run an installed application such as `wireshark` from that
machine's terminal. Its files, processes and network remain in that machine.
Each application window is separate and labelled with the CyberLab node ID.
Closing an application window is the application's ordinary close action, not
a Session stop. New terminal attachments automatically reconnect a prepared
machine's display when a graphical host is available; they never install
packages automatically. Use **Ứng dụng** to retry a failed connection. An
already-connected machine does not launch another client. Empty displays do
not open a desktop window: start an application from the terminal.

The host still requires an application-display client dependency: `xpra`.
CyberLab launches it in the background without its launcher, tray or desktop
viewer. It uses the distribution's system Python/GTK3, not the CyberLab venv.
The client currently checks Xpra 3-6 and rencodeplus support. An absent or
incompatible client produces an error without stopping or recreating a Session.
The installer replaces its TigerVNC dependency with Xpra; it does not remove
previous packages, enable an Xpra service, add package repositories or upgrade
Qt/Quickshell. On Niri, XWayland is used by the native GTK/X11 client.

### Linux display compatibility and diagnosis

The supported design targets Linux desktops, not macOS or Windows. There is no
DE/WM name allowlist: GNOME, Plasma, Xfce, Cinnamon, LXQt, i3, Sway, Hyprland and
Niri follow the same capability checks. This is a target list, not a claim of
acceptance testing on every desktop/version. X11 requires an accessible X
display; Wayland requires working XWayland for the current GTK/X11 client.
Niri integrates X11 windows through xwayland-satellite. CyberLab does not change
the compositor configuration, start a host display server, or use `xhost +`.

`cyberlab gui-status` checks the local client and actually attempts to connect
to the display as the current desktop user. It does not contact cyberlabd or
change a Session. Its JSON distinguishes missing/incompatible Xpra, headless,
unreachable X11, unavailable XWayland, and running as root. `desktop-status`
also reports this host result separately from guest package readiness. The
`desktop-status` command exits successfully when the query succeeds, including
`ready: false`: Studio must offer preparation rather than show a failed-operation
toast. Transport/daemon errors remain failures. `prepare-desktop` and `gui-status`
retain nonzero exit codes for unsuccessful preparation/readiness checks. The
installer checks client packages as the target desktop user, but does not
pretend that a sanitized administrator environment can verify the user's live
display: run `gui-status` from that desktop for the connectivity check.

The client explicitly disables protocol compression. Xpra 6 can compress its
initial hello before peer capabilities are known, even with `-z 0`; Ubuntu's
minimal Xpra installation may lack the optional LZ4 decoder. Use
`--compressors=none` as well as `-z 0` so an already-prepared guest does not
require another package installation merely to authenticate. This trades
display-stream bandwidth for compatibility; it does not disable authentication
or permit additional host integration. High-motion/large-window performance
requires separate measurements.

The client adapts the encoding/DPI capability fields to the flat representation
accepted by Ubuntu's Xpra 3, while retaining the native protocol and authenticated
startup event. It also sends the full legacy keyboard mapping at initial
connection and decodes old-server byte-string window titles. Guest readiness
also checks Pillow: executable-only detection
previously missed this optional package, which Xpra 3 needs when sending existing
application windows during reconnect. Older prepared machines missing Pillow
are offered the normal confirmed preparation step again, not silently modified.

### Isolated guest display

Inside the container, Xpra manages an Xvfb display on `:99`, with X11 TCP
disabled and a private Xauthority file. New terminals receive `DISPLAY=:99`
and `XAUTHORITY=/tmp/cyberlab-apps/Xauthority`. If a terminal was opened before
updating CyberLab, reopen it or set those two variables there. The display
socket, authentication file and server stay inside the container; no host
X11/Wayland socket is mounted. A private local client socket carries display
bytes through the existing owner/sender-scoped D-Bus attachment. It is not a
new privileged control API. No Docker port is published, no host service is
enabled, and clients still never talk to Docker.

Clipboard, file/URL opening, file transfer, printing, microphone, speaker,
webcam, remote D-Bus proxying and remote command launching are disabled.
Authentication is per-machine and ephemeral; readiness is reported only after
the native client receives the authenticated startup-complete event. A guest
bridge waits for the client hello before connecting, avoiding Xpra's short
socket-peek timeout. Attachments remain bounded to one per node and 16 total,
expire after inactivity and close on stop/reset/suspend. No blanket process
kills are used. Display disconnection preserves guest applications while the
Session runs; stop/suspend do not preserve running processes or RAM.

The reviewed image does not preinstall large GUI applications. Install a
container-compatible application inside the machine before launching it.
Host devices, host mounts, privileged containers and published ports remain
prohibited. Xpra is a parser for guest-controlled display data, not a guarantee
against vulnerabilities in the client; use maintained distribution packages.

Ubuntu's Firefox package may depend on Snap; Snap/systemd desktop integration
is not provided by this container. Do not disable browser sandboxing as a
workaround. Wireshark can open pcap files in the guest; live capture requiring
extra network capabilities is not enabled. Large GUI apps may exceed the
existing memory limit; the GUI action does not raise resource ceilings
automatically. Real-Docker application acceptance remains separate.

CLI equivalents:

```sh
cyberlab desktop-status SESSION_ID NODE_ID
cyberlab prepare-desktop SESSION_ID NODE_ID --yes
cyberlab open-desktop SESSION_ID NODE_ID
```

The historical `desktop*` CLI/D-Bus names remain for compatibility; their
backend is now `xpra` and the advertised capability is `seamless-apps`.
`desktop` is the foreground attachment used by `open-desktop`; authentication
material is never printed. The private socket and client process are cleaned
on detach. `ConfirmDesktop` marks only the calling connection's attachment
ready after its handshake, so a connecting client is not reported as ready.
GUI setup is a Session operation, not a Lab template/schema change.

Isolated checks: `tools/check_desktops.py` exercises owner/sender checks, stream
limits, expiry, stop cleanup, binary PTY transport, a private D-Bus round trip
and a synthetic client. `tools/check_notifications.py --suite desktop` checks
confirmation/cancellation, failure handling, missing-viewer handling and
node/state/capability gating offscreen. Neither creates a Docker Session;
`tools/check_seamless_apps.py --xvfb /absolute/path/to/Xvfb` additionally uses
real Xpra and GTK applications on two temporary X displays to verify individual
windows, authenticated readiness, detach and reconnect. It does not use Docker
or the production catalog. These checks do not prove the Ubuntu container
package installation, Firefox/Wireshark compatibility, interactive performance
or full Labtainer import support; real-Docker acceptance remains separate.

`tools/check_gui_runtime.py --uid UID --display DISPLAY` is an administrator-only
acceptance check for that real-Docker boundary. It creates a temporary catalog
and Ubuntu Session with the normal 512 MiB policy, prepares the guest, installs
Mousepad only in that disposable guest, and runs the actual CLI relay/client
under the desktop UID. It verifies authenticated readiness, a uniquely named
guest window on the host display, and reattachment to the same application.
Its request callback dispatches to the real Engine directly; D-Bus transport
and ownership are covered separately by `check_desktops.py`. Without `--display`
it checks only guest preparation/startup, not actual window forwarding.
Cleanup removes only its own container/network/checkpoint scope and temporary
files, including after failure. It never modifies the production catalog,
user drafts or existing practice. This opens a short-lived test window; it is
not part of routine installer checks.

Add `--installed` to run the same fixture against the installed package instead
of source. The check also samples pixels below the window title bar to reject
an empty/black placeholder; an actual screenshot is still useful for visual QA.

Acceptance on 2026-11-03: Arch/Niri with XWayland, host Xpra 6.4.4 and the
Ubuntu 24.04 guest's Xpra 3.1.5 passed real Mousepad rendering and detach/reconnect,
on source and again after guarded installation. A temporary X11/Xvfb host also
passed the real Docker connection/window/reconnect check. Native Xpra-to-Xpra
offscreen forwarding of two windows passed separately. This does not certify
all DE/WM versions, arbitrary GUI applications, graphics acceleration, or
interactive performance. Initial testing exposed missing guest Pillow and
old/new Xpra capability differences; executable presence and host-only tests
had not caught those failures.
