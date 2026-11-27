#!/usr/bin/env bash

detect_distribution() {
    [[ -r /etc/os-release ]] || fail 'Missing /etc/os-release.'
    unset ID ID_LIKE PRETTY_NAME VERSION_ID VERSION_CODENAME UBUNTU_CODENAME
    source /etc/os-release
    distro_name=${PRETTY_NAME:-${ID:-unknown}}
    classify_distribution
    command -v "$manager" >/dev/null || fail "Expected package manager: $manager"
}

classify_distribution() {
    case " ${ID:-} ${ID_LIKE:-} " in
        *' arch '*|*' archlinux '*) family=arch; manager=pacman ;;
        *' debian '*|*' ubuntu '*) family=debian; manager=apt-get ;;
        *' fedora '*|*' rhel '*|*' centos '*) family=fedora; manager=dnf ;;
        *' opensuse '*|*' opensuse-tumbleweed '*|*' opensuse-leap '*|*' suse '*|*' sles '*) family=suse; manager=zypper ;;
        *) fail "No package adapter for $distro_name. Supported families: Arch, Debian/Ubuntu, Fedora, openSUSE (systemd, mutable host)." ;;
    esac
}

configure_packages() {
    if [[ ${gui_runtime:-native} == private ]]; then
        host_packages=(python3 python3-venv systemd dbus util-linux ca-certificates curl
            cmake ninja-build g++ pkg-config p7zip-full patchelf libcli11-dev libdrm-dev
            libjemalloc-dev libgl-dev libegl-dev libopengl-dev libvulkan-dev
            libxkbcommon-dev libfontconfig1 libfreetype6 libx11-xcb1 libxcb-cursor0
            libxcb-icccm4 libxcb-image0 libxcb-keysyms1 libxcb-render-util0 libxcb-xkb1 libxcb-shape0
            libxkbcommon-x11-0 libwayland-client0 libwayland-cursor0 libwayland-egl1)
        return
    fi
    case "$family" in
        arch) host_packages=(python python-pip systemd dbus util-linux qt6-declarative qt6-svg qt6-wayland) ;;
        debian)
            host_packages=(python3 python3-venv systemd dbus util-linux libqt6svg6 qt6-wayland
                qml6-module-qtcore qml6-module-qtqml qml6-module-qtqml-models qml6-module-qtqml-workerscript
                qml6-module-qtquick qml6-module-qtquick-window qml6-module-qtquick-controls
                qml6-module-qtquick-dialogs qml6-module-qtquick-layouts qml6-module-qtquick-templates
                qml6-module-qt-labs-folderlistmodel) ;;
        fedora) host_packages=(python3 python3-pip systemd dbus dbus-tools dbus-daemon util-linux qt6-qtdeclarative qt6-qtsvg qt6-qtwayland) ;;
        suse) host_packages=(systemd dbus-1 util-linux qt6-declarative-imports libQt6Svg6 qt6-wayland) ;;
    esac
}

native_terminals_present() {
    local probe_python account_home response
    probe_python="$(command -v python3 || command -v python || true)"
    [[ -n $probe_python ]] || return 2
    account_home="$(getent passwd "$desktop_user" | cut -d: -f6)"
    [[ $account_home == /* ]] || return 2
    local -a probe=(/usr/bin/env "HOME=$account_home" "PATH=$account_home/.local/bin:/usr/local/bin:/usr/bin:/bin"
        "$probe_python" -B -I "$ROOT/cli/cyberlab_cli/terminal_apps.py" --probe)
    if [[ $EUID == 0 ]]; then
        [[ $(id -u -- "$desktop_user") != 0 ]] || return 2
        command -v runuser >/dev/null || return 2
        probe=(runuser -u "$desktop_user" -- "${probe[@]}")
    elif [[ $(id -un) != "$desktop_user" ]]; then
        return 2
    fi
    response="$("${probe[@]}")" || return 2
    printf '%s' "$response" | "$probe_python" -I -c '
import json, sys
try:
    options = json.load(sys.stdin)["options"]
    if not isinstance(options, list):
        raise ValueError("Invalid terminal inventory")
except (ValueError, KeyError, TypeError):
    sys.exit(2)
sys.exit(0 if options else 1)'
}

collect_terminal_package() {
    local probe_status
    terminal_probe_pending=no
    if native_terminals_present; then
        printf '%s\n' 'Native terminal found for the desktop user; no terminal package will be added.'
    else
        probe_status=$?
        if [[ $probe_status == 1 ]]; then
            package_available xfce4-terminal || fail 'No compatible terminal was found and xfce4-terminal is unavailable in enabled repositories. Install a supported native terminal explicitly; no repository is added.'
            host_packages+=(xfce4-terminal)
            printf '%s\n' 'No compatible terminal found: adding only xfce4-terminal and its dependencies as fallback.'
        else
            terminal_probe_pending=yes
            printf '%s\n' 'Terminal discovery is not available yet. After Python is installed, recheck before proposing xfce4-terminal; do not assume the terminal is missing.'
        fi
    fi
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
    [[ -x /usr/bin/qs || -x /usr/bin/quickshell || -x /usr/local/bin/qs || -x /usr/local/bin/quickshell ]]
}

private_quickshell_present() {
    [[ -e /usr/lib/cyberlab/gui-runtime || -L /usr/lib/cyberlab/gui-runtime ]]
}

private_runtime_supported() {
    local suite=${UBUNTU_CODENAME:-${VERSION_CODENAME:-}}
    [[ ${family:-} == debian && $suite == noble && $(uname -m) == x86_64 ]]
}

select_gui_runtime() {
    gui_runtime=native
    if private_quickshell_present; then
        gui_runtime=private
    elif ! native_quickshell_present && ! package_available quickshell && private_runtime_supported; then
        gui_runtime=private
    fi
}

native_pkexec_present() {
    [[ -x /usr/bin/pkexec ]]
}

collect_gui_package() {
    local package
    if package="$(choose_available xpra xpra-client)"; then
        host_packages+=("$package")
    else
        printf '%s\n' 'WARNING: kho hiện tại không có Xpra; vẫn cài được CyberLab nhưng GUI không có đường dự phòng Xpra. Native X11/XWayland cần được kiểm tra trong phiên desktop. Không tự thêm repository bên thứ ba.'
    fi
}

collect_update_package() {
    local package
    local -a candidates
    if native_pkexec_present; then return; fi
    case "$family" in
        debian) candidates=(pkexec) ;;
        arch) candidates=(polkit) ;;
        fedora) candidates=(polkit-pkexec polkit) ;;
        suse) candidates=(polkit-pkexec polkit polkit-1) ;;
    esac
    package="$(choose_available "${candidates[@]}")" || fail 'Không tìm thấy gói cung cấp pkexec để cập nhật bằng giao diện. Chuẩn bị dependency phù hợp; không tự thêm repository.'
    if package_installed "$package"; then
        fail "Gói $package đã cài nhưng thiếu /usr/bin/pkexec. Hãy kiểm tra gói hệ thống; CyberLab không tự thay thế bản cài này."
    fi
    host_packages+=("$package")
}

quickshell_install_hint() {
    local suite=${UBUNTU_CODENAME:-}
    if [[ ${ID:-} == ubuntu ]]; then suite=${suite:-${VERSION_CODENAME:-}}; fi
    if [[ $suite == noble ]]; then
        printf '%s\n' 'Ubuntu 24.04 / Linux Mint 22.x: chưa có đường cài tự động Quickshell được xác minh cho máy này. Cài lại hoặc thêm PPA thiếu gói không khắc phục được. Build thủ công theo upstream cần Qt >=6.6 và private headers khớp ABI; installer không thay Qt hệ thống. Xem https://quickshell.org/docs/v0.3.2/guide/install-setup/ và docs/installation/platforms.md.'
    else
        printf '%s\n' "No native quickshell package in the enabled repositories for $distro_name. Review bash install.sh --plan --enable-quickshell-repo for an explicit native-source option, or enable a compatible repository yourself. No AppImage fallback or repository changes were made."
    fi
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
    printf 'GUI provider: %s\n' "${gui_runtime:-native}"
    printf '%s\n' 'Quickshell: native package, or pinned private runtime on supported Ubuntu 24.04 x86_64 bases.' \
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
    collect_terminal_package
    collect_update_package
    collect_gui_package
    if [[ $family == debian && ${gui_runtime:-native} != private ]] && package_available qt6-svg-plugins; then
        host_packages+=(qt6-svg-plugins)
    fi
    if [[ $family == fedora && $allow_dependency_upgrades == yes ]]; then
        collect_fedora_upgrades libgcc 'libstdc++'
    fi
    if [[ $family == suse ]]; then
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
    if [[ ${gui_runtime:-native} == private ]]; then
        printf '%s\n' 'GUI: Qt 6.10.3 + Quickshell 0.3.2 riêng, không thay Qt hệ thống; build không đặc quyền, cần 5 GiB tạm.'
    elif native_quickshell_present; then
        bootstrap_python="$(command -v python3 || true)"
        if [[ -n $bootstrap_python ]] && "$bootstrap_python" -I -c 'import sys; sys.exit(sys.version_info < (3, 9))'; then
            if ! "$bootstrap_python" -B -I "$ROOT/tools/install/runtime_admin.py" --user "$desktop_user" native-version; then
                package_installed quickshell || fail 'The incompatible Quickshell is not the stable distro package; repair that installation explicitly. Custom/git runtimes will not be replaced.'
                refresh_quickshell=yes
            fi
        fi
    else
        package_available quickshell || fail "$(quickshell_install_hint)"
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

refresh_native_metadata() {
    if [[ $family == debian ]]; then apt-get update --error-on=any; fi
    if [[ $family == suse ]]; then zypper --non-interactive refresh; fi
}

install_native_packages() {
    refresh_native_metadata
    forced_packages=()
    check_python_candidate
    select_gui_runtime
    ensure_quickshell_source
    collect_native_packages
    if ((${#missing_packages[@]} == 0)); then
        printf '%s\n' 'Native dependencies are already installed.'
    else
        guarded_package_install
    fi
    if [[ $terminal_probe_pending == yes ]]; then
        host_packages=(); missing_packages=(); forced_packages=()
        collect_terminal_package
        [[ $terminal_probe_pending == no ]] || fail 'Cannot inspect terminals as the desktop user. Resolve the discovery error; no fallback terminal was installed.'
        if ((${#host_packages[@]})); then
            missing_packages=("${host_packages[@]}")
            guarded_package_install
        fi
    fi
    if [[ ${gui_runtime:-native} == private ]] && ! private_quickshell_present; then
        "$(select_python)" -B -I "$ROOT/tools/install/private_runtime.py" --user "$desktop_user" --lock-fd 9
    fi
}
