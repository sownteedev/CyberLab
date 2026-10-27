#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(CDPATH='' cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
export PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
export LC_ALL=C
export PYTHONDONTWRITEBYTECODE=1
unset PYTHONPATH PYTHONHOME LD_PRELOAD LD_LIBRARY_PATH
source "$ROOT/tools/install/packages.sh"
source "$ROOT/tools/install/docker.sh"
source "$ROOT/tools/install/transactions.sh"
source "$ROOT/tools/install/repositories.sh"

usage() {
    cat <<'EOF'
Usage: bash install.sh [OPTIONS]

No options: install missing native packages and CyberLab on a new machine.
  --plan           Resolve and show the package plan; no package/service changes
  --check          Check versions, native QML and Docker readiness; never start services
  --no-deps        Use existing packages; do not call a package manager
  --install-deps   Same as the default (kept for existing instructions)
  --deps-only      Install prerequisites, but not CyberLab or its service
  --update         Guarded app-only update; never changes Qt or host packages
  --allow-dependency-upgrades  Permit reviewed dependency upgrades, never removals/downgrades
  --enable-quickshell-repo     Opt in to the reviewed native PPA/COPR/OBS source for this distro
  --yes            Accept the displayed package plan (upgrades still need the flag above)
  --user NAME      Desktop account (defaults to the sudo caller)
  --help           Show this help

Uses enabled distro repositories only: pacman, apt, dnf or zypper.
An optional third-party Quickshell source requires --enable-quickshell-repo.
No AppImage, automatic repository additions or whole-OS upgrades.
Python packages are installed in a private venv, not the system Python.
EOF
}

fail() { printf 'ERROR: %s\n' "$*" >&2; exit 1; }
mode=install
dependencies=yes
allow_dependency_upgrades=no
assume_yes=no
enable_quickshell_repo=no
desktop_user="${SUDO_USER:-$(id -un)}"
original_arguments=("$@")
mode_selected=no
deps_selected=no
while (($#)); do
    case "$1" in
        --help|-h) usage; exit 0 ;;
        --plan|--check|--deps-only|--update)
            [[ $mode_selected == no ]] || fail 'Choose only one operation.'
            mode="${1#--}"; mode_selected=yes ;;
        --no-deps|--install-deps)
            [[ $deps_selected == no ]] || fail 'Choose only one dependency option.'
            deps_selected=yes
            if [[ $1 == --no-deps ]]; then dependencies=no; else dependencies=yes; fi ;;
        --user)
            (($# >= 2)) && [[ -n $2 && $2 != -* ]] || fail '--user needs an account name.'
            desktop_user=$2; shift ;;
        --allow-dependency-upgrades) allow_dependency_upgrades=yes ;;
        --yes) assume_yes=yes ;;
        --enable-quickshell-repo) enable_quickshell_repo=yes ;;
        *) fail "Unknown option: $1 (see --help)" ;;
    esac
    shift
done
if [[ $mode == update || $mode == check || $mode == plan ]]; then
    [[ $deps_selected == no ]] || fail "--$mode cannot be combined with dependency options."
    dependencies=no
fi
[[ $mode != deps-only || $dependencies == yes ]] || fail '--deps-only cannot use --no-deps.'
if [[ $mode == update || $mode == check || $dependencies == no && $mode != plan ]]; then
    [[ $allow_dependency_upgrades == no && $assume_yes == no && $enable_quickshell_repo == no ]] || fail 'Dependency approval flags require a dependency installation operation or --plan.'
fi

detect_distribution
configure_packages
if [[ $mode == plan ]]; then
    print_package_plan
    if [[ $enable_quickshell_repo == yes ]]; then enable_quickshell_repository; exit 0; fi
    collect_native_packages
    if ((${#missing_packages[@]})); then guarded_package_install; fi
    exit 0
fi
[[ $(uname -s) == Linux ]] || fail 'CyberLab requires Linux.'
[[ -d /run/systemd/system && -S /run/dbus/system_bus_socket ]] || fail 'A running systemd host and System D-Bus are required (not a chroot/container).'
[[ ! -e /run/ostree-booted && ! -d /sysroot/ostree ]] || fail 'Immutable/OSTree hosts need native packaging; this installer does not modify their base system.'
desktop_uid="$(id -u -- "$desktop_user")" || fail 'Unknown desktop account.'
[[ $desktop_uid != 0 ]] || fail 'Select the non-root desktop account using --user NAME.'
if getent group docker >/dev/null && [[ " $(id -Gn -- "$desktop_user") " == *' docker '* ]]; then
    fail 'The desktop account belongs to docker. Review that access first; CyberLab must use its daemon.'
fi

if [[ $mode != check && $EUID != 0 ]]; then
    command -v sudo >/dev/null || fail 'Run as administrator with --user YOUR_DESKTOP_USER.'
    exec sudo -- /bin/bash "$ROOT/install.sh" "${original_arguments[@]}" --user "$desktop_user"
fi
if [[ $mode != check ]]; then
    [[ ! -L /run/cyberlab-installer.lock ]] || fail 'Unsafe installer lock path.'
    exec 9>/run/cyberlab-installer.lock
    flock -n 9 || fail 'Another CyberLab installation/update is active; wait for its result instead of running twice.'
fi
if command -v python3 >/dev/null && python3 -I -c 'import sys; sys.exit(sys.version_info < (3, 9))'; then
    python3 -B -I "$ROOT/tools/runtime_admin.py" --user "$desktop_user" account
fi

if [[ $mode == install ]]; then
    for target in /usr/lib/cyberlab /etc/cyberlab /var/lib/cyberlab \
        /etc/systemd/system/cyberlabd.service /etc/systemd/system/cyberlabd.service.d \
        /etc/dbus-1/system.d/org.ptit.CyberLab1.conf /usr/local/bin/cyberlab \
        /usr/local/bin/cyberlab-studio /usr/share/applications/cyberlab-studio.desktop; do
        [[ ! -e $target && ! -L $target ]] || fail "Existing installation: $target. Use --update for a healthy installation; do not overwrite a partial install."
    done
    [[ $(systemctl show cyberlabd.service --property=LoadState --value) == not-found ]] || fail 'A CyberLab service already exists.'
fi

if [[ $dependencies == yes ]]; then
    if [[ $enable_quickshell_repo == yes ]]; then enable_quickshell_repository; fi
    install_native_packages
fi
python="$(select_python)" || fail 'Python 3.12+ with venv/ensurepip is required; use a supported release. The installer will not replace system Python.'
printf 'Desktop account: %s (UID %s); Python: %s\n' "$desktop_user" "$desktop_uid" "$python"
admin=("$python" -I "$ROOT/tools/runtime_admin.py" --user "$desktop_user")
if [[ $mode == update ]]; then
    "${admin[@]}" check --backend-only
elif [[ $mode == install || $mode == deps-only ]]; then
    "${admin[@]}" check --allow-stopped-docker
else
    "${admin[@]}" check
fi
if [[ $mode == check || $mode == deps-only ]]; then
    printf '%s\n' 'DONE: prerequisites checked. No CyberLab runtime or catalog was installed/updated.'
    exit 0
fi

umask 022
stage="$(mktemp -d /var/tmp/cyberlab-app-install-XXXXXXXX)"
service_started=no
on_exit() {
    local status=$?
    if ((status)); then
        if [[ $service_started == yes ]]; then
            systemctl disable --now cyberlabd.service || true
        fi
        printf 'Installation incomplete. Preserve %s and installed files for review; do not blindly rerun.\n' "$stage" >&2
    fi
}
trap on_exit EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
printf 'Build artifacts and verification: %s\n' "$stage"
"${admin[@]}" stage --stage "$stage"
shopt -s nullglob
wheels=("$stage"/cyberlab_engine-*-py3-none-any.whl)
((${#wheels[@]} == 1)) || fail 'Expected exactly one validated app wheel.'
wheel=${wheels[0]}

if [[ $mode == update ]]; then
    "${admin[@]}" update --stage "$stage" --wheel "$wheel"
    printf '%s\n' 'DONE: guarded app update completed; host packages, Qt, catalog and config preserved.'
else
    systemctl start docker.service
    "${admin[@]}" prepare --stage "$stage"
    mkdir -m 755 /usr/lib/cyberlab
    "$python" -I -m venv /usr/lib/cyberlab/venv
    runtime_python=/usr/lib/cyberlab/venv/bin/python
    "$runtime_python" -I -m pip --isolated install --no-index --no-cache-dir \
        --only-binary=:all: --find-links "$stage/wheels" "$wheel"
    "$runtime_python" -I -m pip --isolated check
    install -d -m 700 /var/lib/cyberlab /var/lib/cyberlab/authoring
    install -d -m 755 /etc/cyberlab /etc/systemd/system/cyberlabd.service.d
    for directory in /etc/dbus-1/system.d /usr/local/bin /usr/share/applications; do
        [[ -d $directory ]] || install -d -m 755 "$directory"
    done
    install -m 644 "$stage/config/daemon.toml" /etc/cyberlab/daemon.toml
    install -m 644 "$stage/config/authoring.conf" /etc/systemd/system/cyberlabd.service.d/authoring.conf
    install -m 644 "$stage/config/cyberlabd.service" /etc/systemd/system/cyberlabd.service
    install -m 644 "$stage/config/org.ptit.CyberLab1.conf" /etc/dbus-1/system.d/org.ptit.CyberLab1.conf
    install -m 755 "$stage/config/cyberlab" /usr/local/bin/cyberlab
    install -m 755 "$stage/config/cyberlab-studio" /usr/local/bin/cyberlab-studio
    install -m 644 "$stage/config/cyberlab-studio.desktop" /usr/share/applications/cyberlab-studio.desktop
    "$runtime_python" -I -c 'from pathlib import Path; from cyberlabd.config import load_config; load_config(Path("/etc/cyberlab/daemon.toml"))'
    systemd-analyze verify /etc/systemd/system/cyberlabd.service
    dbus-send --system --type=method_call --print-reply --dest=org.freedesktop.DBus \
        /org/freedesktop/DBus org.freedesktop.DBus.ReloadConfig
    systemctl daemon-reload
    service_started=yes
    systemctl enable --now cyberlabd.service
    "${admin[@]}" verify --stage "$stage" --wheel "$wheel"
    service_started=no
    printf '%s\n' 'DONE: CyberLab installed with native Quickshell. No sample Labs were added.'
fi
printf '%s\n' 'As the desktop user: cyberlab info; cyberlab-studio' \
    'Save editor work and reopen Studio yourself; no existing windows were closed.'
