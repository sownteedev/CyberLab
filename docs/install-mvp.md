# Ubuntu-First Installation and Development

CyberLab can be developed on a physical Linux machine or in a VM. The
architecture remains Studio/CLI -> System D-Bus -> cyberlabd -> Engine -> Docker.
Do not copy the old machine's venv, `/usr/lib/cyberlab`, service files, UID or
home paths to a new host. Clone the source and install for its actual account.

Ubuntu is the primary target. Keep the existing adapters for other distributions
as secondary paths; do not treat their presence as a promise of universal Linux
support. New work prioritizes reliable Ubuntu installation and dependency reuse
on both clean VMs and existing desktops.

## Installer Families and Verification

| Family | Package manager | Requirements and limits |
| --- | --- | --- |
| Ubuntu (primary), Debian and compatible derivatives | `apt` | Python 3.12+; all Qt/QML modules and `quickshell` must be available in enabled repositories. |
| Arch, EndeavourOS, compatible Arch derivatives | `pacman` | Native `quickshell`, Python and Qt from a coherent distro repository snapshot. |
| Fedora and compatible mutable RPM hosts | `dnf` | Python 3.12+, native Quickshell, and Docker Engine (`moby-engine`, or `docker-ce` if its repo is already enabled). |
| openSUSE Tumbleweed / compatible Leap releases | `zypper` | An available Python 3.12+ and pip pair, Qt 6 QML modules, native Quickshell and Docker. |

These are package-manager adapters, not results of installation certification
on every release or derivative. Requirements: systemd, System D-Bus, Bash,
Python >=3.12 with venv/ensurepip, Quickshell >=0.3.1, matching native Qt/QML
packages, Docker Engine, Konsole and a graphical session (X11 or Wayland).
The installer probes the needed QML imports and SVG icon decoding offscreen
before registering the app service. On APT releases with a separate
`qt6-svg-plugins` package, it includes that plugin as well as `libqt6svg6`;
the library alone does not guarantee image decoding. Python/image/native-package
availability still depends on CPU architecture; removing AppImage is not a
promise of support for every CPU.

Verification on 2026-10-27 uses disposable x86_64 cloud VMs, not the production
catalog. Ubuntu 26.04.1 passed native installation with the explicit PPA, missing
SVG-plugin detection/installation, daemon/System D-Bus readiness, draft
publication, two-node Docker start/reset/stop, preservation of unrelated Docker
resources, dependency reuse, refusal to overwrite an installation and guarded
app updates. The updated installed Studio loads offscreen with SVG icons.
The guest used Quickshell 0.3.2, Qt 6.10.2 and Docker 29.1.3. No Qt or Quickshell
upgrade was performed on the user's existing development VM.

Arch previously passed the installation/lifecycle/update path, including
private-home authoring. Fedora dependency installation passed, but the app
service did not start in that disposable guest; Fedora is not certified.
Debian and openSUSE have not completed end-to-end verification. These checks
are not physical-GPU/VMware display acceptance, interactive terminal testing
or certification of every release, derivative or daily-use machine.

Old releases with Python <3.12, non-systemd distributions, immutable/OSTree
hosts, NixOS, containers and chroots are not supported by this installer.
Podman and `podman-docker` are not substitutes for the reviewed Docker adapter.
SELinux/AppArmor remain enabled: if a host policy denies access, inspect its
audit logs and review a narrow policy; do not disable the host protection.

The installer queries **enabled repositories only**. If `quickshell` or another
package is unavailable, it stops before installing packages and explains what
is missing (package metadata may already have been refreshed). It never enables
PPA, COPR, OBS or AUR automatically and never downloads an AppImage or builds
arbitrary upstream source as root. Review the current upstream native-package
guide for your distro before adding a repository:

<https://quickshell.org/docs/v0.3.2/guide/install-setup/>

If your enabled repositories lack Quickshell, an explicit native-source option
is available. This is a third-party trust decision, not a requirement on Arch:

```sh
bash install.sh --plan --enable-quickshell-repo
bash install.sh --enable-quickshell-repo
```

The first command shows the source and signing-key fingerprint without adding
it. It cannot resolve packages from a source that has not yet been enabled.
The second verifies the key, adds only CyberLab-named source/key files and then
resolves the dependency transaction for confirmation. It never overwrites a
different existing file. Repository files remain if later installation fails;
the receipt is retained in `/var/tmp/cyberlab-repository-*`. Only this flag
authorizes adding a source; `--yes` alone does not.

| Host | Explicit optional source |
| --- | --- |
| Ubuntu / derivatives with a declared Ubuntu base codename | AvengeMedia DankLinux PPA. |
| Debian 13 | AvengeMedia DankLinux OBS Debian 13 repository. |
| Fedora 42+ | errornointernet/quickshell COPR, scoped to `quickshell` and its `cpptrace` packages. |
| openSUSE Tumbleweed, Slowroll, Leap 16.0/16.1 | AvengeMedia DankLinux OBS target for that release. |

Source availability is still checked by the package manager; the table is not
a claim that every release has compatible packages. Keys are fingerprint-pinned
in `tools/install/repositories.sh`; upstream key rotation requires review.
APT uses a source-specific signing key. RPM uses package signature checking.
Adding a third-party source affects future package-manager operations too;
review it before opting in. Unsupported derivative bases are not guessed.
The inspected Ubuntu 24.04 (`noble`) PPA did not provide `quickshell` on
2026-10-27; adding it does not make that release installable. A compatible native
runtime/repository or newer OS is needed; CyberLab never upgrades the OS for you.
Fedora 44's inspected official package was below the 0.3.1 minimum; the explicit
COPR source provided 0.3.2 with a required `cpptrace` runtime dependency.

Repository availability and Qt ABI compatibility are external requirements.
Use a native Quickshell package built against that distro's Qt, not a binary
copied from another machine. On Arch, prepare an up-to-date coherent system
yourself; the installer uses `pacman -S --needed`, never a partial `pacman -Sy`
or an unsolicited whole-system update. Dependency installation is reviewed
before execution. Existing packages are reused; upgrades are blocked unless
`--allow-dependency-upgrades` is explicitly supplied. Removals, replacements
and downgrades are rejected even with that option. Save work in other apps
before approving upgrades to shared libraries such as Qt on a daily-use desktop.
On Fedora, that approval also includes reviewed `libgcc`/`libstdc++` runtime
updates when available. The native Konsole check catches C++ symbol mismatches
before registering the application; no automatic library upgrade occurs without
the flag. DNF5 stores a download-only plan without sudo, then replays exactly
the reviewed transaction with weak dependencies disabled and signature checks
enabled. Large first-time desktop dependency sets can take several minutes.
After a kernel upgrade, reboot yourself first. If modules for the running
kernel are missing and Docker is stopped, the installer stops early with a
reboot diagnostic instead of proceeding into a broken Docker network startup.
It never reboots the machine for you.

## Install

From a trusted checkout as the desktop user:

```sh
bash install.sh --plan
bash install.sh
cyberlab info
cyberlab-studio
```

The Bash entry point elevates with sudo for installation. From a root shell,
select the desktop account explicitly with `--user NAME`. Studio itself must
never run as root. Additional modes:

```sh
bash install.sh --check        # Native versions/QML probe; no package/service changes
bash install.sh --deps-only    # Host packages only; no CyberLab service/catalog
bash install.sh --no-deps      # Install with manually prepared prerequisites
bash install.sh --update       # Guarded app-only update, no package-manager calls
sudo bash install.sh --check --user "$USER"  # Include privileged Docker API health
```

`--install-deps` is an alias for the default fresh-install behavior, retained
for older instructions. Operations are mutually exclusive. `--appimage` is no
longer an installer option. `--check` checks native versions, offscreen QML
imports, Konsole and the system Docker service. It never starts a service.
Run it as root with `--user` to include Docker socket/API health; an unprivileged
check reports that gate as unverified and returns status 2 rather than claiming
full readiness. These checks run before app installation/registration. Only the
application installation path explicitly starts a stopped Docker service after
the UI checks pass. Distro package maintainer scripts may independently start or
restart services while installing dependencies; CyberLab does not override the
host's package/service policy. Use `--plan` before changes on a daily-use host.

`--plan` resolves dependencies without installing packages or changing services.
Metadata, artifacts and plan receipts may be cached; it is not a zero-write
command. Review the transaction before confirming installation. For intentional
upgrades use `bash install.sh --allow-dependency-upgrades`; `--yes` only skips
the confirmation prompt, never the upgrade/removal guards. Receipts remain in
`/var/tmp/cyberlab-dependencies-*`. Candidate Quickshell packages are verified
against the >=0.3.1 minimum before installation. APT checks actual .deb inputs
before dpkg;
pacman uses a temporary pre-transaction removal/upgrade guard; DNF5 replays its
reviewed stored transaction. Unknown transaction formats fail closed.

The installer builds the application and downloads binary Python dependency
wheels **as the desktop user**, copies bounded checked artifacts to private
root-owned staging, and installs them offline into `/usr/lib/cyberlab/venv`.
`pip` is intentional: distro Python library versions may not meet the package's
declared constraints. It never uses `sudo pip` on the system interpreter or
`--break-system-packages`. Keep the root daemon separate from editable code.

The script generates account-specific configuration, registers System D-Bus
policy and the existing systemd service, preloads the approved BusyBox image,
starts the daemon and verifies the API as the non-root account. It creates no
verification Lab/Session and installs no examples.

| Installed path | Purpose |
| --- | --- |
| `/usr/lib/cyberlab/venv` | Root-owned application, libraries and Studio resources. |
| `/usr/bin/qs` or `/usr/bin/quickshell` | Native Quickshell managed by the distribution, not copied by CyberLab. |
| `/usr/local/bin/cyberlab`, `/usr/local/bin/cyberlab-studio` | CLI and desktop launcher. |
| `/usr/share/applications/cyberlab-studio.desktop` | Application-menu entry. |
| `/etc/cyberlab/daemon.toml` | Per-machine catalog, user/image allowlists and authoring configuration. |
| `/etc/systemd/system/cyberlabd.service` and its drop-in | Privileged service and reviewed catalog-write policy. |
| `/etc/dbus-1/system.d/org.ptit.CyberLab1.conf` | Shared System D-Bus policy. |
| `/home/<user>/CyberLab-labs` | Persistent catalog, created empty only when absent. |
| `/var/lib/cyberlab/authoring` | Private drafts and saved practice; never a build fixture. |

New catalogs are root-owned with the desktop user's primary group and mode
2775, so the bounded daemon and the selected user can both manage the library.
Existing catalogs are preserved byte-for-byte, without chmod/chown of their
contents. Their referenced images must still be separately allowed/preloaded;
the initial allowlist is only `busybox:1.37.0`. Personal shortcuts are preserved
and may shadow the global one; use `/usr/local/bin/cyberlab-studio` to select
the installed app explicitly. Existing legacy VM launchers can reuse their
already-installed AppImage for compatibility, but new installations never
need or fetch one. Use `--require-native` on the Studio launcher to forbid that.

The service exposes only the catalog in a private home-directory mount namespace
(`ProtectHome=tmpfs` plus a bounded `BindPaths` entry). It does not chmod the
user's home or expose other private home files. Existing catalog permissions
that prevent bounded daemon writes are reported for administrator review, not
silently changed. Publication uses the caller's actual primary group, not a
guess that the numeric GID equals the UID.

Docker HTTP requests have a finite 30-second timeout to accommodate slower VMs.
Transport failures, including socket errors and read timeouts, are reported as
runtime failures rather than unexpected Python errors. Cleanup still attempts
the remaining owned resources and reports incomplete cleanup; it never retries
Lab creation blindly or removes another application's resources.

Existing system Docker CE or distro Engine installations are reused. A partial
Docker CE setup is completed only from its matching enabled repository;
`docker.io` is never substituted. Podman shims, masked/broken/custom/rootless or
Desktop-only installations are not silently removed or reconfigured.
Installation rejects Docker-group membership, user write access to the Docker
socket, unsafe paths, existing app paths or leftover CyberLab-managed resources.
It never removes Docker containers/networks to make a check pass. Artifacts,
hashes and receipts stay in the printed `/var/tmp/cyberlab-app-install-*`
directory. On failure, files remain for review and a newly started CyberLab
service is disabled. Review `journalctl -u cyberlabd`; do not delete state or
rerun blindly. Host packages/Docker startup are not automatically rolled back.

## Develop and Update

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -e .
bash tools/run_studio.sh --require-native
```

On a distro with multiple Python versions, use the same >=3.12 interpreter
chosen for installation rather than an older default `python3`.
The source launcher uses the editable package's QML with the real shared
daemon API; it is not an isolated preview. QML reloads do not deploy Python
backend changes. Save work and stop Sessions, then deploy those changes with:

```sh
bash install.sh --update
```

The guarded updater checks **all allowed users' Sessions are STOPPED**, retains
runtime/private-state backups and rolls back on verification failure. It never
force-stops a Lab, overwrites the catalog/config/image allowlist, changes Qt,
installs host packages or kills a Studio window. Save editor work before an
update and reopen Studio yourself afterward. Keep the printed backup and
verification record. It requires a healthy existing runtime; after a rolling
distribution changes system Python's minor version, repair/rebuild the installed
venv under administrator review, not a blind app update. Recreate `.venv` for
development as well; venvs are not portable between machines/Python versions.

Old MVP bundle repairs, OVA packaging, catalog migrations and AppImage installers
have been archived outside the checkout. They are not part of this workflow.
Maintained helpers are listed in `tools/README.md`.
