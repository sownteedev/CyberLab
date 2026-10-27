#!/usr/bin/env bash

configure_quickshell_repository() {
    repository_name=cyberlab-quickshell
    repository_format=
    case "$family" in
        arch)
            printf '%s\n' 'Arch uses its enabled stable quickshell package; no extra repository is needed.'
            return
            ;;
        debian)
            repository_format=apt
            repository_destination=/etc/apt/sources.list.d/cyberlab-quickshell.sources
            if [[ ${ID:-} == ubuntu || -n ${UBUNTU_CODENAME:-} ]]; then
                repository_suite=${UBUNTU_CODENAME:-${VERSION_CODENAME:-}}
                [[ $repository_suite =~ ^[a-z]+$ ]] || fail 'Cannot determine the Ubuntu base codename safely.'
                repository_url=https://ppa.launchpadcontent.net/avengemedia/danklinux/ubuntu
                repository_component=main
                repository_fingerprint=45FECBE587307AAA3F0A4BE9FC44813D2A7788B7
                repository_key_url="https://keyserver.ubuntu.com/pks/lookup?op=get&search=0x$repository_fingerprint"
            elif [[ ${ID:-} == debian && ${VERSION_ID:-} == 13 ]]; then
                repository_url=https://download.opensuse.org/repositories/home:/AvengeMedia:/danklinux/Debian_13
                repository_suite=/
                repository_component=
                repository_fingerprint=20CA3E5804CA75009B3671A4284778483BC86115
                repository_key_url="$repository_url/Release.key"
            else
                fail 'No reviewed external Quickshell source for this Debian derivative/release. Enable a compatible repository yourself; no guessed Ubuntu/Debian base will be used.'
            fi
            ;;
        fedora)
            [[ ${ID:-} == fedora && ${VERSION_ID:-} =~ ^[0-9]+$ && ${VERSION_ID:-0} -ge 42 ]] || fail 'The reviewed COPR source is for Fedora 42+ only, not RHEL/other derivatives.'
            repository_format=rpm
            repository_destination=/etc/yum.repos.d/cyberlab-quickshell.repo
            repository_url='https://download.copr.fedorainfracloud.org/results/errornointernet/quickshell/fedora-$releasever-$basearch/'
            repository_key_url=https://download.copr.fedorainfracloud.org/results/errornointernet/quickshell/pubkey.gpg
            repository_fingerprint=C1D4C77749293CFD57F5DBEC069A483BB13958D3
            ;;
        suse)
            case ${ID:-}:${VERSION_ID:-} in
                opensuse-tumbleweed:*) repository_suite=openSUSE_Tumbleweed ;;
                opensuse-slowroll:*) repository_suite=openSUSE_Slowroll ;;
                opensuse-leap:16.0|opensuse-leap:16.1) repository_suite=$VERSION_ID ;;
                *) fail 'No reviewed external Quickshell source for this openSUSE release.' ;;
            esac
            repository_format=rpm
            repository_destination=/etc/zypp/repos.d/cyberlab-quickshell.repo
            repository_url="https://download.opensuse.org/repositories/home:/AvengeMedia:/danklinux/$repository_suite/"
            repository_key_url="${repository_url}repodata/repomd.xml.key"
            repository_fingerprint=20CA3E5804CA75009B3671A4284778483BC86115
            ;;
    esac
}

write_repository_file() {
    local source=$1 destination=$2
    [[ ! -L $destination && ! -L $(dirname -- "$destination") ]] || fail "Unsafe repository destination: $destination"
    if [[ -e $destination ]]; then
        cmp -s "$source" "$destination" || fail "Existing repository file differs: $destination. It was not overwritten."
        return
    fi
    install -d -m 755 "$(dirname -- "$destination")"
    (set -o noclobber; umask 022; cat "$source" > "$destination") || fail "Could not exclusively create $destination"
}

enable_quickshell_repository() {
    local stage fingerprint key_destination package
    configure_quickshell_repository
    [[ -n $repository_format ]] || return
    printf 'Optional third-party native source: %s\nSigning key: %s\n' "$repository_url" "$repository_fingerprint"
    if [[ ${mode:-install} == plan ]]; then
        printf '%s\n' 'Repository plan only; no source/key was installed. Rerun with --enable-quickshell-repo to approve adding this source.'
        return
    fi
    if [[ -e $repository_destination || -L $repository_destination ]]; then
        printf 'Existing %s will be checked, never overwritten.\n' "$repository_destination"
    fi
    missing_packages=()
    case "$family" in
        debian) repository_tools=(ca-certificates curl gnupg) ;;
        fedora) repository_tools=(ca-certificates curl gnupg2) ;;
        suse) repository_tools=(ca-certificates curl gpg2) ;;
    esac
    for package in "${repository_tools[@]}"; do
        if [[ $package == curl ]] && command -v curl >/dev/null; then continue; fi
        if [[ $package == gnupg || $package == gnupg2 || $package == gpg2 ]] && command -v gpg >/dev/null; then continue; fi
        if ! package_installed "$package"; then missing_packages+=("$package"); fi
    done
    if ((${#missing_packages[@]})); then guarded_package_install; fi
    confirm_package_transaction
    stage="$(mktemp -d /var/tmp/cyberlab-repository-XXXXXXXX)"
    mkdir -m 700 "$stage/gpg"
    curl --fail --silent --show-error --location --proto '=https' --proto-redir '=https' \
        --connect-timeout 15 --max-time 90 --max-filesize 1048576 "$repository_key_url" -o "$stage/key.asc"
    fingerprint="$(gpg --batch --no-options --homedir "$stage/gpg" --show-keys --with-colons "$stage/key.asc" | awk -F: '$1 == "pub" {primary=1; next} primary && $1 == "fpr" {print $10; primary=0}')"
    [[ $fingerprint == "$repository_fingerprint" ]] || fail "Repository key changed. Expected $repository_fingerprint, received $fingerprint; no repository was enabled. Review upstream key rotation explicitly."
    if [[ $repository_format == apt ]]; then
        key_destination=/etc/apt/keyrings/cyberlab-quickshell.asc
        printf 'Types: deb\nURIs: %s\nSuites: %s\n' "$repository_url" "$repository_suite" > "$stage/repository"
        if [[ -n $repository_component ]]; then printf 'Components: %s\n' "$repository_component" >> "$stage/repository"; fi
        printf 'Signed-By: %s\n' "$key_destination" >> "$stage/repository"
    else
        key_destination=/etc/pki/rpm-gpg/RPM-GPG-KEY-cyberlab-quickshell
        printf '[%s]\nname=Explicitly approved CyberLab Quickshell source\nbaseurl=%s\nenabled=1\ngpgcheck=1\ngpgkey=file://%s\n' "$repository_name" "$repository_url" "$key_destination" > "$stage/repository"
        if [[ $family == fedora ]]; then printf 'includepkgs=quickshell,cpptrace,cpptrace-devel\n' >> "$stage/repository"; fi
    fi
    write_repository_file "$stage/key.asc" "$key_destination"
    write_repository_file "$stage/repository" "$repository_destination"
    if [[ $repository_format == rpm ]]; then rpm --import "$key_destination"; fi
    printf '%s\n%s\n' "$repository_url" "$repository_fingerprint" > "$stage/verification.txt"
    printf 'Repository enabled explicitly; receipt: %s\n' "$stage"
}
