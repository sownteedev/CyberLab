# Native X11 safety and release record (2026-11-05)

## Private XWayland transport (2026-11-11)

The previous live Wayland attempt reached native preparation but the guest
could not connect: its UID 2000 cannot write to a desktop-owned 0755 Unix
socket. The current desktop also reparents Xwayland to the user systemd
manager, rather than leaving it beneath the compositor process. Both cases
are handled without chmod/xhost changes or copied desktop-login credentials.

The daemon creates one 0600 Unix listener per GUI node in its private lease
directory, owns its lifecycle and binds only that socket into the container.
A bounded worker drops to the desktop user's UID/GID before opening the verified
XWayland endpoint. It accepts only the configured guest UID and exact per-node
MIT-MAGIC-COOKIE-1 setup before connecting upstream, even if the host X server
would otherwise allow unauthenticated local connections. The worker is an X11
byte/SCM_RIGHTS forwarder, not an image encoder or another application API.
FD passing supports X11 shared-buffer operations; it does not turn shared host
XWayland into an isolated display. Xpra remains available for that purpose.

Workers have at most 32 connections and 64 KiB pending data per direction, a
bounded setup timeout, and close transferred FDs on errors. The worker loses
its connections on parent-pipe EOF. Stop/fallback closes it; reconnect reuses the
listener inode while replacing authorization. Daemon restart cleans stale lease
files. No new service or service capabilities are installed, and the daemon's
AF_UNIX-only restriction remains unchanged. Startup preparation or guest-probe
failure still selects Xpra. A running direct connection that disappears reports
disconnected and supports explicit reconnect; it does not silently migrate
existing application windows to Xpra.

XWayland discovery now also considers same-user, systemd-reparented servers;
the root-owned executable, exact shared listener inode, peer credentials and
both process start times must still match. Merely finding a process named
Xwayland is never sufficient. Local host `gui-status` now recognizes the current
Wayland session; this alone is not guest acceptance or a latency measurement.

Verification passed 10 relay tests, 31 native-display lifecycle tests, 11 X11
safety tests, 69 desktop/private-D-Bus tests and 18 Session-state tests. The
headless Cage/XWayland fixture passed both server-owned and inherited listener
modes. Its disposable, networkless Docker client reproduced UID 2000 denial on
the unchanged upstream 0755 socket, then created/mapped X11 windows through the
private relay. Invalid cookies were rejected. The production guest Xauthority
mount and libX11 XOpenDisplay readiness probe also passed without selecting
Xpra. Authorization revocation did not terminate the unrelated fixture client.

The cross-UID fixture requires an existing GUI-prepared image, not the minimal
Ubuntu base (which lacks libX11). Reproduce with:

```sh
/usr/lib/cyberlab/venv/bin/python tools/check_xwayland.py --guest \
  --guest-image <cached-cyberlab-software-image>
```

The image is inspected and used read-only by a disposable container; no pull,
package installation, production Lab or draft modification occurs. This run
used `cyberlab-software:8a4384f73e7e460e9ffdf104a12c0591`. Studio passed 6 GUI
settings tests and 100 editor tests/native offscreen loading; the extracted
wheel also passed 100 editor tests/native offscreen loading. Diff checks passed.

Guarded installation on 2026-11-11 used wheel SHA-256
`3dd00b5dbb656b83c325989223a199411061ef8c8a8e33a53debfd0a7b805382`
from `/tmp/cyberlab-relay-release-20261111-7x97vc`, with backup
`/var/tmp/cyberlab-runtime-backup-69ua5dqm`. All allowed users passed the
stopped-Session gate; no Studio/editor was open. All 292 installed package files
match the wheel. The daemon is active with unchanged capabilities and
`RestrictAddressFamilies=AF_UNIX`. Installed `cyberlab gui-status` reports
`backend=native-x11`, `display_server=Xwayland`, `native_ready=true` and no
fallback reason on the current Umbriel Wayland desktop, with preference `auto`.
Normal installed Studio mapped a native Wayland window; only that test window
was closed through the compositor, and the launcher exited successfully.
The existing `NodeSoftwareEditor.qml:122` null-property warning remains outside
this display change. User Sessions remain empty. Real user-Lab application
acceptance and latency measurement remain pending; the isolated window tests
and host readiness do not claim a Firefox/Wireshark performance result.

## Direct XWayland support (2026-11-07)

Auto may now select a direct X11 connection on a local Wayland login as well
as on Xorg. The wire/backend identifier remains `native-x11`; Settings identifies
the verified server as XWayland. Explicit Xpra still bypasses native probing and
authorization. An unsupported server, missing SECURITY extension, failed identity
check or failed authorization falls back to Xpra without changing the desktop.

Wayland validation requires the active local login and socket to belong to the
requesting user, a root-owned non-writable installed Xwayland executable and the
actual listening socket in its file descriptors. Compositor/socket-activated
listeners are supported only when an owner-matching descendant Xwayland inherits
that same listener. Discovery is bounded and allows one second for lazy startup.
Identity includes socket inode/device, server and listener-owner PID/start time.
These bind the lease to this particular server; they do not assert that all
same-user processes reside in a single logind session scope. Cleanup refuses to
revoke against a changed XWayland identity.

The existing per-node authorization, single X socket mount and shared daemon API
are reused. No host Wayland socket, login cookie, host home directory, Docker
socket, global xhost permission or new service privilege is introduced. This
shares the host X server and is not display isolation. Use Xpra for untrusted
Labs. The host's pre-existing X access policy still applies: generated-cookie
revocation must not be described as blocking all future access to an X server
that already permits unauthenticated local clients.

`tools/check_xwayland.py` runs real Xwayland windows inside a private headless
Cage compositor, with a temporary HOME/runtime and exact process-group cleanup.
Both server-created and inherited listeners exercise identity checks, generated
authorization, active-client revocation, invalid/stale credential rejection and
survival of unrelated windows. The fixture uses authenticated rootful Xwayland;
logind is mocked only for the production identity check. This is not acceptance
of seamless windows on the user's Niri/GNOME/KDE session, real Docker GUI apps,
keyboard/mouse/clipboard behavior or latency. Those require a later Wayland
desktop acceptance with the user's saved work and stopped Sessions.

Source verification passed 28 native/identity/updater tests, 11 safety tests,
69 desktop/private-D-Bus tests and 18 Session-state tests. The real headless
Xwayland fixture passed three authorization/active-window cleanup cycles for
each of the two listener modes. Studio passed 6 GUI-settings tests, 19 software
tests and 100 editor tests with native Quickshell loading; targeted Qt 6 lint
and diff checks passed. The packaged editor also passed 100 tests/native load.

Guarded installation on 2026-11-07 used wheel SHA-256
`84b46f4003745cf8491e6fc84b2bece852ca8a0b9459e897670e0dd1d5bf048d`
from `/tmp/cyberlab-xwayland-release-20261107`, with backup
`/var/tmp/cyberlab-runtime-backup-1l2fuauq`. All allowed users passed the updater's
stopped-Session gate and Studio was closed. All 290 installed package files
match the wheel; installed GUI-settings checks passed 6 cases. Normal installed
Studio opened on the current XFCE X11 desktop and its exact test window closed
gracefully. The daemon is active, retains `RestrictAddressFamilies=AF_UNIX`, and
the verification user's Sessions remain empty. No production Lab/draft or real
Docker Session was created or modified. User-desktop Wayland acceptance remains
pending; do not claim measured performance improvement from these checks.
The normal-launch log still reports a null `software_search` property warning
at `NodeSoftwareEditor.qml:122`; the window loads and closes successfully. That
existing software-picker initialization issue is outside this display change.

## Guest connectivity probe adjustment (deployed 2026-11-05)

Inspection of the live Session `89953062` revealed:
1. The daemon correctly prepared the per-node lease under `/run/cyberlab/native/...`.
2. The container mounted `/run/cyberlab-native/Xauthority` and `/tmp/.X11-unix/X0` read-only.
3. The guest container successfully opened the X display (`first_open: True`).
4. However, `verify_guest` previously attempted a second open with an intentionally invalid cookie
   to assert authorization rejection. On Xorg sessions running without host authentication (such as
   default `xinit` / startx without `-auth`), local Unix domain sockets are permitted by host access control.
   The deliberate negative test failed (returned exit code 2), causing CyberLab to mark the lease as failed
   and fall back to Xpra with "Guest X11 authentication could not be enforced; using Xpra".

The guest probe now validates that the container can successfully connect and open the native display
using its mounted authorization file.

## Effective-capability correction (deployed 2026-11-05)

The subsequent live Session reported fallback at `daemon-context`, after client
authorization generation. Read-only inspection found `CapBnd=0xc1` but
`CapPrm=CapEff=0x41`: the running daemon lacked CAP_SETUID despite the configured
bounding set. Earlier checks of `systemctl show` did not catch this discrepancy.
The systemd 262.1 executor's seccomp privilege-handling path drops CAP_SETUID
unless included in its ambient set (`src/core/exec-invoke.c`).

The reviewed unit now explicitly preserves `AmbientCapabilities=CAP_SETUID`,
without expanding the bounding set or disabling NoNewPrivileges, PrivateTmp or
other sandbox controls. The guarded updater verifies the running process's
permitted/effective/bounding capabilities and NoNewPrivs before reporting
success, retaining the same rollback on failure. The helper still changes UID
and GID to the desktop user; no privileged X11 operation is introduced.

The correction was deployed through the guarded updater after the Session was
STOPPED and Studio was closed. The receipt is retained in
`/var/tmp/cyberlab-app-install-44JNREvF`; the running daemon reports
`CapPrm=CapEff=CapBnd=0xc1` and `CapAmb=0x80`. This confirms the service
policy, but not yet a live native-X11 Lab acceptance. Do not use the
production display for authorization test scripts.

## Guarded service-policy deployment (2026-11-05)

The normal `install.sh --update` path now requests the reviewed service-policy
migration; previously it updated the package without enabling that migration.
The guarded update completed with all Sessions stopped and Studio closed.
Backup, wheel and verification receipt are retained in
`/var/tmp/cyberlab-app-install-YJBUZgCc`.
Installed wheel: `cyberlab_engine-0.9.0-py3-none-any.whl`, SHA256
`360b8e4b2fe33a8ceda19536afdc28d91ed0f45420a7f0687a617afa1e03c7aa`.

The receipt reports `service_policy_repaired: true` and preserved catalog
identity. The running unit has the X11 socket bind, `RuntimeDirectory=cyberlab`
with mode 0700, and CAP_CHOWN/CAP_SETUID/CAP_SETGID; PrivateTmp remains enabled.
Validation: 17 native/mock/updater tests, 10 safety tests and 69 desktop tests
passed. The installed launcher loaded its configuration without QML startup
errors; only that verification process group was closed afterward.

No real Lab or native authorization was started for this deployment. Live
Xorg acceptance and Wayland latency measurements remain unverified. The older
validation-wheel/not-installed statement below describes the earlier artifact,
not this deployment. Existing Xpra containers do not switch backend in place.

## Current delivery state

Native X11 is enabled for verified local Xorg and XWayland servers. Auto selects
native only after logind, UID, socket, process identity and SECURITY checks;
any failure falls back to Xpra. The XWayland extension and outstanding desktop
acceptance are described in the 2026-11-07 entry above. Xpra remains
available through Settings as the stronger display-isolation option.

The runtime now revokes a target authorization through a short-lived controller
connection rather than revoking from the connection authenticated with that
target. The controller uses an independently generated two-second authorization
and closes the target connection before calling `XSecurityRevokeAuthorization`.
This avoids the self-revocation crash pattern reproduced on the disposable
Xvfb fixture. It is still not a promise that all Xorg versions are bug-free.

The service policy binds only `/tmp/.X11-unix`, keeps private state in the
systemd runtime directory, and grants only the reviewed `CAP_CHOWN`,
`CAP_SETUID`, and `CAP_SETGID` needed to create the per-node lease and invoke
the helper as the desktop user. It does not expose Docker, home directories,
host networking or a global X11 ACL.

## Incident and evidence

The user reported two real Xorg session crashes on 2026-11-04, returning to
greetd. Previous development tests mistakenly ran authorization operations
against the desktop's inherited DISPLAY. Do not repeat those tests on Xorg
or on the user's XWayland server, even from a Wayland login.

On 2026-11-05 an isolated Xvfb fixture reproduced server termination with
SIGABRT (return code -6) when a connection authenticated with a generated
authorization revoked that same authorization. This matches the hazardous
self-revocation pattern in the unfinished native lifecycle. It is not an
independent analysis of the original host coredumps.

Revoking a generated authorization from a separate controller connection
passed three independent fixture runs, including active clients. The target
windows disconnected while an unrelated client remained usable.

The corrected fixture uses `-noreset` to retain authorizations between
short-lived helper connections; generated-cookie verification now passes.
No reset or authentication settings are changed on the real desktop.

## Isolated verification only

`tools/check_x11_safety.py` checks fail-closed behavior when native support is
explicitly disabled and confirms that the runtime fixture cannot mount a host
display. `tools/check_native_display.py` covers native lifecycle behavior with
mocked display operations; it does not connect to a real desktop.

`tools/check_x11_security.py --xvfb /absolute/path/to/Xvfb` uses:

- A fresh authenticated Xvfb with `-displayfd`, not a fixed display number.
- A sanitized environment, temporary HOME/config/authentication and no inherited
  DISPLAY, WAYLAND_DISPLAY, XAUTHORITY or user bus.
- Verification of server UID, parent process, executable, process start time
  and Unix-socket peer PID before each helper operation.
- Credentials only through private files or pipes, never printed as evidence.
- Disabled core dumps and cleanup of the exact owned process group.
- Explicit rejection tests for swapped display ownership and stale process IDs.

The security test deliberately uses only owned Xvfb instances. Do not
substitute DISPLAY or use a user's desktop authentication file in this command.

## Gates before native can return

Verification recorded on 2026-11-05:

| Check | Result |
| --- | --- |
| Native safety regression suite | 10 passed |
| Mocked native/preferences/relay/updater suite | 16 passed |
| Desktop and private D-Bus regressions | 69 passed |
| Session lifecycle regressions | 18 passed |
| GUI Settings offscreen | 5 passed |
| Isolated real Xpra | Two windows, detach preserving apps, reconnect passed |
| Isolated X SECURITY | Control revoke, active clients and cleanup passed; self-revoke path removed |
| Wheel build | Passed; Python syntax and native lifecycle included |

The validation wheel is
`/tmp/cyberlab-safety-build-20261105-nvo9pg48/wheels/cyberlab_engine-0.9.0-py3-none-any.whl`,
SHA256 `9bce4133f508351a4922f9cb2a2f45875b5752cfcf7530bd3c123040c8d3aab2`.
It is **not installed**. No daemon restart, live GUI acceptance or latency
benchmark was performed. Temporary artifact paths are not release locations.

Remaining gates:

1. Replace self-revocation with a reviewed control-authorization lifecycle.
   Simply using a different connection with the same cookie is not sufficient.
   Account for expiration, active guest clients, daemon restart and logout,
   without depending on a copied login credential or relaxing host ACLs.
2. Verify revocation with active guest clients, repeated cleanup and restart
   on isolated servers. Review the original crash evidence and the applicable
   X server implementation before claiming a fix.
3. Finish reconnect/file-permission handling, failed-native mount cleanup,
   context ownership/expiry and the private-bus lifecycle tests.
4. Complete isolated Docker application/checkpoint acceptance and repeatable
   Xpra performance measurements. Offscreen/mock checks are not latency tests.
5. Coordinate live desktop acceptance with the user only after the safety gates;
   then use the guarded updater with all Sessions STOPPED and editor work saved.

Do not deploy the unfinished native backend or ask the user to switch to X11
merely to reproduce the crash. The production catalog and learner data must
not be used as test fixtures.
