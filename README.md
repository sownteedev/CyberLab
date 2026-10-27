# CyberLab

CyberLab is a graduation thesis project for creating and running isolated,
container-based learning labs on Linux desktops, physical machines or VMs. Studio provides the Quickshell
interface; the CLI exposes the same daemon API.

## Architecture

```text
Studio (Quickshell) / CLI
           |
      System D-Bus
           |
       cyberlabd
           |
    CyberLab Engine
           |
     Docker Engine
```

Studio may invoke the unprivileged CLI with explicit arguments. Neither client
controls Docker directly. A Lab is a template; a Session is an instance of it.

## Repository

| Directory | Purpose |
| --- | --- |
| `engine/` | Lab definitions, authoring, Session lifecycle and runtime adapters. |
| `daemon/` | Shared D-Bus API, authorization and installation configuration. |
| `cli/` | Command-line client and terminal-window integration. |
| `ui/` | Quickshell Studio, shared components, icons and bundled Inter fonts. |
| `schemas/` | Versioned lab-definition schemas. |
| `tools/` | Native installer helpers, source UI launcher and guarded updates. |
| `docs/` | Feature documentation, architecture decisions and deployment history. |
| `.agents/` | Development guidance and third-party agent skills. |

Production labs live outside the repository at
`/home/<user>/CyberLab-labs`. Do not copy tests or examples into that catalog
as part of development, cleanup or installation verification. Drafts, saved
practice, Docker images and installed services are also not part of a Git clone.
The optional test suite and example Labs are not included in this checkout.
They are not required to install or run the application. Keep `schemas/`: the
engine uses it to validate Lab definitions and exposes it to the editor.

## Install On Another Machine

Ubuntu is the primary installation and development target. The other Linux
package-manager adapters remain available, but expanding distro coverage is
not the current priority. See the verified releases and limitations in
`docs/install-mvp.md`; an adapter alone does not mean a release is supported.
In particular, the inspected Ubuntu 24.04 optional repository does not supply
the required native Quickshell package. Do not remove a working legacy runtime
or assume this script upgrades Ubuntu to resolve that limitation.

After cloning this repository, the verified Ubuntu 26.04 native-package path is:

```sh
bash install.sh --plan --enable-quickshell-repo  # Review the optional source/key
bash install.sh --enable-quickshell-repo         # Explicitly accept that source
```

These commands opt in to the third-party native Quickshell repository. If a
compatible Quickshell package is already available in enabled repositories,
omit `--enable-quickshell-repo`: use `bash install.sh --plan`, then
`bash install.sh`. The installer still reviews the dependency transaction.

The script requests sudo, detects the calling desktop user, builds the app as
that unprivileged user and installs the Python runtime, System D-Bus policy,
`cyberlabd` service, CLI and application-menu shortcut. Quickshell, Qt, Docker
and Konsole come from the target distribution's enabled package repositories;
the installer does not download an AppImage.
It creates an empty `~/CyberLab-labs` only when absent, preserves an existing
catalog and does not copy example Labs. It preloads the approved BusyBox base
image; other Lab images must be prepared and allowed separately.

The installer has adapters for Arch-based systems (`pacman`), Debian/Ubuntu
and derivatives (`apt`), Fedora (`dnf`) and openSUSE (`zypper`). The host needs
systemd, System D-Bus, Python 3.12+, native Quickshell 0.3.1+ with its matching
Qt/QML packages, and a normal graphical desktop. Support depends on the packages
available for that distro/release; this is not a claim that every Linux OS is
certified. Immutable systems, NixOS and non-systemd distributions are not covered.

If `quickshell` is missing from enabled repositories, installation stops with
instructions; no PPA/COPR/OBS/AUR is silently enabled. Review the upstream native
package instructions referenced in `docs/install-mvp.md` before enabling an
additional repository. `bash install.sh --plan --enable-quickshell-repo`
shows the optional source and signing key; installing with
`--enable-quickshell-repo` explicitly opts in to that third-party source.
This source-only plan does not resolve packages until the source is enabled.
The installer does not perform a whole-OS upgrade or
replace the system Python. Use `--no-deps` for manually prepared prerequisites.
Python libraries still come from pip into a **private venv**, never system pip;
distro Python package versions do not necessarily meet `pyproject.toml`.
Initial installation requires internet for missing packages, wheels and images.

```sh
bash install.sh --check          # Versions/QML check; no package/service changes
sudo bash install.sh --check --user "$USER"  # Also verify privileged Docker API health
bash install.sh --deps-only      # Only prepare native host dependencies
bash install.sh --update         # After git pull; guarded app-only update
cyberlab info                    # Run as the desktop user, without sudo
cyberlab-studio
```

Updates require all users' Sessions to be stopped, preserve drafts/catalog/config
and do not upgrade Quickshell/Qt or close Studio. Save editor work and reopen
Studio yourself after an update. Use `--user NAME` when invoking from a root
shell. Details and failure recovery: [installation guide](docs/install-mvp.md).

On a daily-use machine the installer reuses existing system Docker/Qt/Python
packages instead of switching providers. It displays the resolved package
transaction and asks before installing it (`--yes` for explicit unattended
approval). Existing package upgrades require `--allow-dependency-upgrades`;
removals/downgrades are rejected. Missing repository packages, incompatible
native runtimes and conflicting Docker setups stop with a diagnostic rather
than silently replacing the user's environment. An unprivileged `--check`
returns 2 when Docker health still needs an administrator check.

## Development Setup

Moving from a VM to a physical machine does not change the application
architecture. Install host dependencies and the daemon using `install.sh` on
the new machine. Do not copy the old `.venv`, root runtime or OS configuration.
The default development workflow uses native Quickshell; the launcher retains
compatibility with an already-installed legacy runtime only to avoid breaking
the old VM's shortcuts. A new installation neither needs nor fetches one.

Create a fresh development environment rather than copying another VM's venv:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -e .
```

This installs the Python package in editable mode, not the privileged daemon or
desktop dependencies. With the daemon and native Quickshell runtime already
installed, launch the source UI as the ordinary desktop user:

```sh
bash tools/run_studio.sh --require-native
```

This connects to the real daemon. Save work before changing Sessions or drafts;
it is not an isolated preview. QML edits use the source tree; Python backend/API
changes require `bash install.sh --update` so the root daemon always runs
root-owned installed code, never a user-writable checkout. After `git pull`,
refresh the development venv with `.venv/bin/python -m pip install -e .` when
dependencies change. Recreate that venv after a system Python minor-version
change (especially on rolling-release distributions).

See `docs/quickshell-studio.md` for Studio setup. Installation and
historical upgrade details are in `docs/install-mvp.md`; do not rerun an initial
installer on an existing installation without reviewing the current state.

## Repository Hygiene

`tools/` now contains only the maintained installation/development helpers and
explicit Lab/image validation tools; see `tools/README.md`.
Old MVP/OVA/AppImage-download/migration tools were archived outside the checkout.
The test suite and example Labs were archived outside the repository at the
user's request; they are not part of the runtime package. `.venv/`, `build/`,
`dist/` and Python caches are local and excluded from Git. Old local artifacts are archived
under `~/.local/state/cyberlab/development-archives/`; historical `dist/` paths in
the documentation refer to those local runs, not files included in a Git clone.

Never commit passwords, keys, tokens, production catalogs, personal drafts or VM
disk images. Inter's bundled license and provenance are in
`ui/studio/assets/fonts/`; the locally installed SFMono font is not bundled.
Do not add users to the Docker group or expose its socket to clients or labs.
Read `AGENTS.md` before changing architecture, deployment or security policy.
