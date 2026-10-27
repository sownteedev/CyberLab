#!/usr/bin/env bash

docker_unit_state() {
    systemctl show docker.service --property=LoadState --value 2>/dev/null
}

docker_cli_present() {
    [[ -x /usr/bin/docker ]]
}

docker_cli_version() {
    /usr/bin/docker --version 2>&1
}

unmanaged_docker_present() {
    [[ -x /usr/bin/docker || -x /usr/bin/dockerd || -e /var/run/docker.sock ]] || command -v docker >/dev/null
}

select_docker_packages() {
    local package unit_state version
    local ce_present=no distro_present=no
    docker_packages=()
    unit_state="$(docker_unit_state)" || fail 'Cannot inspect the system Docker service.'
    [[ $unit_state != masked ]] || fail 'docker.service is masked. It will not be unmasked or replaced; review your existing Docker setup first.'
    if package_installed podman-docker; then
        fail 'podman-docker owns the Docker command. It will not be removed or replaced. CyberLab needs a real system Docker Engine; use a separate compatible host/account setup.'
    fi
    for package in docker-ce docker-ce-cli containerd.io; do
        if package_installed "$package"; then ce_present=yes; fi
    done
    for package in docker.io moby-engine docker; do
        if package_installed "$package"; then distro_present=yes; fi
    done
    [[ $ce_present != yes || $distro_present != yes ]] || fail 'Mixed Docker CE and distro engine packages need administrator review; CyberLab will not switch providers.'
    if docker_cli_present; then
        version="$(docker_cli_version)" || fail 'The existing Docker CLI is broken; it will not be replaced automatically.'
        [[ $version == 'Docker version '* ]] || fail "Unsupported Docker CLI: $version. Podman aliases/wrappers are not Docker Engine."
    elif command -v docker >/dev/null; then
        fail 'A custom Docker CLI exists outside /usr/bin/docker. Install a compatible system Docker package explicitly; CyberLab will not replace your custom setup.'
    fi
    if [[ $unit_state == loaded ]]; then
        docker_cli_present || fail 'docker.service exists but /usr/bin/docker is missing. Repair that installation without replacing its provider.'
        printf '%s\n' 'Reusing the existing system Docker Engine; no Docker package replacement.'
        return
    fi
    [[ $unit_state == not-found ]] || fail "Unsupported Docker service state: $unit_state"
    if package_installed docker-ce || [[ $distro_present == yes ]]; then
        fail 'A Docker Engine package is installed but docker.service is missing. Repair the existing service; no replacement will be attempted.'
    fi
    if [[ $ce_present == yes ]]; then
        package_available docker-ce || fail 'Existing Docker CE components detected, but docker-ce is unavailable in enabled repositories. Restore the matching Docker repository; docker.io will not be substituted.'
        docker_packages=(docker-ce)
        printf '%s\n' 'Completing the existing Docker CE provider (preserving docker-ce-cli/containerd.io).'
        return
    fi
    if unmanaged_docker_present; then
        fail 'An unrecognized Docker/standalone/rootless setup already exists. CyberLab requires the system Docker service; existing binaries and sockets will not be replaced.'
    fi
    case "$family" in
        arch|suse) package=docker ;;
        debian) package=docker.io ;;
        fedora) package="$(choose_available moby-engine docker-ce)" || fail 'No supported Docker Engine in enabled repositories.' ;;
    esac
    package_available "$package" || fail "Docker Engine package unavailable: $package"
    docker_packages=("$package")
}
