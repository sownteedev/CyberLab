#!/usr/bin/env bash

detect_distribution() {
    [[ -r /etc/os-release ]] || fail 'Missing /etc/os-release.'
    unset ID ID_LIKE PRETTY_NAME VERSION_ID VERSION_CODENAME UBUNTU_CODENAME
    source /etc/os-release
    distro_name=${PRETTY_NAME:-${ID:-unknown}}
    case " ${ID:-} ${ID_LIKE:-} " in
        *' arch '*|*' archlinux '*) family=arch; manager=pacman ;;
        *' debian '*|*' ubuntu '*) family=debian; manager=apt-get ;;
        *' fedora '*|*' rhel '*|*' centos '*) family=fedora; manager=dnf ;;
        *' opensuse '*|*' opensuse-tumbleweed '*|*' opensuse-leap '*|*' suse '*|*' sles '*) family=suse; manager=zypper ;;
        *) fail "No package adapter for $distro_name. Supported families: Arch, Debian/Ubuntu, Fedora, openSUSE (systemd, mutable host)." ;;
    esac
    command -v "$manager" >/dev/null || fail "Expected package manager: $manager"
}

configure_packages() {
    case "$family" in
        arch) host_packages=(python python-pip systemd dbus konsole util-linux qt6-declarative qt6-svg qt6-wayland) ;;
        debian)
            host_packages=(python3 python3-venv systemd dbus util-linux konsole libqt6svg6 qt6-wayland
                qml6-module-qtcore qml6-module-qtqml qml6-module-qtqml-models qml6-module-qtqml-workerscript
                qml6-module-qtquick qml6-module-qtquick-window qml6-module-qtquick-controls
                qml6-module-qtquick-dialogs qml6-module-qtquick-layouts qml6-module-qtquick-templates) ;;
        fedora) host_packages=(python3 python3-pip systemd dbus dbus-tools dbus-daemon util-linux konsole qt6-qtdeclarative qt6-qtsvg qt6-qtwayland) ;;
        suse) host_packages=(systemd dbus-1 util-linux qt6-declarative-imports libQt6Svg6 qt6-wayland) ;;
    esac
}

select_python() {
    local candidate
    for candidate in /usr/bin/python3 /usr/bin/python3.{14,13,12}; do
        if [[ -x $candidate ]] && "$candidate" -I -c 'import sys, venv, ensurepip; sys.exit(sys.version_info < (3, 12))' 2>/dev/null; then
            printf '%s\n' "$candidate"
            return 0
        fi
    done
    return 1
}

native_quickshell_present() {
    [[ -x /usr/bin/qs || -x /usr/bin/quickshell ]]
}

package_version() {
    case "$family" in
        arch) pacman -Q "$1" 2>/dev/null | awk '{print $2}' ;;
        debian) dpkg-query -W -f='${Version}' "$1" 2>/dev/null ;;
        fedora|suse) rpm -q --qf '%{EPOCHNUM}:%{VERSION}-%{RELEASE}\n' "$1" 2>/dev/null ;;
    esac
}

package_installed() {
    case "$family" in
        arch) pacman -Q "$1" >/dev/null 2>&1 ;;
        debian) [[ $(dpkg-query -W -f='${Status}' "$1" 2>/dev/null) == 'install ok installed' ]] ;;
        fedora|suse) rpm -q "$1" >/dev/null 2>&1 ;;
    esac
}

package_available() {
    case "$family" in
        arch) pacman -Si "$1" >/dev/null 2>&1 ;;
        debian) apt-cache policy "$1" | awk '/Candidate:/ { found = ($2 != "(none)") } END { exit !found }' ;;
        fedora) dnf -q list --available "$1" >/dev/null 2>&1 ;;
        suse) zypper --non-interactive search --match-exact --type package "$1" | awk -F'|' -v package="$1" '
            {name=$2; gsub(/^[ \t]+|[ \t]+$/, "", name); if (name == package) found=1}
            END {exit !found}' ;;
    esac
}

check_python_candidate() {
    local candidate bootstrap
    if select_python >/dev/null; then return; fi
    bootstrap="$(command -v python3 || true)"
    case "$family" in
        debian)
            candidate="$(apt-cache policy python3 | awk '/Candidate:/ {print $2}')"
            [[ -n $candidate && $candidate != '(none)' ]] && dpkg --compare-versions "$candidate" ge 3.12 || fail 'This release does not provide Python >=3.12 in enabled repositories. No packages were installed; use a supported distro release rather than replacing system Python.'
            ;;
        arch)
            candidate="$(pacman -Si python | awk '/^Version[[:space:]]*:/ {print $3}')"
            [[ -n $candidate ]] && (( $(vercmp "$candidate" 3.12) >= 0 )) || fail 'The enabled Arch snapshot lacks Python >=3.12. Prepare a coherent up-to-date system before installing.'
            ;;
        fedora)
            candidate="$(dnf -q repoquery --latest-limit=1 --qf '%{version}' python3 | sort -V | tail -n 1)"
            [[ $candidate =~ ^3\.([0-9]+)(\.|$) ]] && (( BASH_REMATCH[1] >= 12 )) || fail 'The enabled RPM repositories lack Python >=3.12. Use a supported release; system Python will not be replaced.'
            ;;
        suse) return ;;
    esac
    if [[ -n $bootstrap ]] && "$bootstrap" -I -c 'import sys; sys.exit(sys.version_info >= (3, 12))'; then
        [[ $allow_dependency_upgrades == yes || ${mode:-install} == plan ]] || fail 'The installed Python is older than 3.12. Updating it needs explicit --allow-dependency-upgrades after reviewing the package plan.'
        case "$family" in
            arch) forced_packages+=(python) ;;
            debian) forced_packages+=(python3) ;;
            fedora) collect_fedora_upgrades python3 ;;
        esac
    fi
}

collect_fedora_upgrades() {
    local selected package requested matched
    selected="$(dnf -q repoquery --upgrades --qf '%{name}-%{epoch}:%{version}-%{release}.%{arch}\n' "$@")" || fail 'Cannot resolve native runtime updates.'
    while IFS= read -r package; do
        [[ -n $package ]] || continue
        matched=no
        for requested in "$@"; do
            if [[ $package == "$requested"-* ]]; then matched=yes; fi
        done
        [[ $matched == yes && $package =~ ^[A-Za-z0-9][A-Za-z0-9+_.:~^%-]*$ ]] || fail "Unexpected runtime upgrade candidate: $package"
        forced_packages+=("$package")
    done <<< "$selected"
}

choose_available() {
    local package
    for package in "$@"; do
        if package_installed "$package" || package_available "$package"; then
            printf '%s\n' "$package"
            return 0
        fi
    done
    return 1
}

print_package_plan() {
    printf 'Distro: %s\nPackage manager: %s\n' "$distro_name" "$manager"
    printf 'Base packages: %s\n' "${host_packages[*]}"
    printf '%s\n' 'Quickshell: native package quickshell (not quickshell-git or an AppImage).' \
        'Docker: existing engine, otherwise docker.io / moby-engine / docker by distro.' \
        'Python: >=3.12 with venv; openSUSE selects an available python3XX + pip pair.' \
        'Python libraries: isolated venv via pip, never pip into the system Python.' \
        'Only enabled repositories are used. No PPA, COPR, OBS or AUR is added automatically.' \
        'No whole-system upgrade; --update does not invoke a package manager.'
}

collect_native_packages() {
    local package selected version bootstrap_python
    local refresh_quickshell=no
    missing_packages=()
    forced_packages=()
    configure_packages
    printf 'Checking native packages for %s...\n' "$distro_name"
    check_python_candidate
    if [[ $family == debian ]] && package_available qt6-svg-plugins; then
        host_packages+=(qt6-svg-plugins)
    fi
    if [[ $family == fedora && $allow_dependency_upgrades == yes ]]; then
        collect_fedora_upgrades libgcc 'libstdc++'
    fi
    if [[ $family == suse ]]; then
        selected="$(choose_available konsole konsole-qt6)" || fail 'Konsole is missing from enabled openSUSE repositories.'
        host_packages+=("$selected")
        if ! select_python >/dev/null; then
            for version in 314 313 312; do
                if package_available "python${version}" && package_available "python${version}-pip"; then
                    host_packages+=("python${version}" "python${version}-pip")
                    break
                fi
            done
            [[ ${host_packages[*]} == *python* ]] || fail 'Enabled openSUSE repositories need Python >=3.12 and its pip package.'
        fi
    fi
    if native_quickshell_present; then
        bootstrap_python="$(command -v python3 || true)"
        if [[ -n $bootstrap_python ]] && "$bootstrap_python" -I -c 'import sys; sys.exit(sys.version_info < (3, 9))'; then
            if ! "$bootstrap_python" -B -I "$ROOT/tools/runtime_admin.py" --user "$desktop_user" native-version; then
                [[ $allow_dependency_upgrades == yes ]] || fail 'The installed native Quickshell is incompatible. No host packages were changed. Review --plan --allow-dependency-upgrades before upgrading its dependencies.'
                package_installed quickshell || fail 'The incompatible Quickshell is not the stable distro package; repair that installation explicitly. Custom/git runtimes will not be replaced.'
                refresh_quickshell=yes
            fi
        fi
    else
        package_available quickshell || fail "No native quickshell package in the enabled repositories for $distro_name. Review bash install.sh --plan --enable-quickshell-repo for an explicit native-source option, or enable a compatible repository yourself. No AppImage fallback or repository changes were made."
        host_packages+=(quickshell)
    fi
    select_docker_packages
    host_packages+=("${docker_packages[@]}")
    for package in "${host_packages[@]}"; do
        if ! package_installed "$package"; then
            package_available "$package" || fail "Required package unavailable: $package. Use a current compatible distro/repository; no packages were installed."
            missing_packages+=("$package")
        fi
    done
    if [[ $refresh_quickshell == yes ]]; then
        if [[ $family == fedora ]]; then collect_fedora_upgrades quickshell; else missing_packages+=(quickshell); fi
    fi
    missing_packages+=("${forced_packages[@]}")
}

install_native_packages() {
    if [[ $family == debian ]]; then apt-get update; fi
    if [[ $family == suse ]]; then zypper --non-interactive refresh; fi
    collect_native_packages
    if ((${#missing_packages[@]} == 0)); then
        printf '%s\n' 'Native dependencies are already installed.'
        return
    fi
    guarded_package_install
}
