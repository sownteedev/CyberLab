#!/usr/bin/env bash

package_inventory() {
    case "$family" in
        arch) pacman -Q | sort ;;
        debian) dpkg-query -W -f='${binary:Package}\t${Version}\t${Status}\n' | sort ;;
        fedora|suse) rpm -qa --qf '%{NAME}.%{ARCH}\t%{EPOCHNUM}:%{VERSION}-%{RELEASE}\n' | sort ;;
    esac
}

resolve_package_transaction() {
    local output=$1 status=0
    case "$family" in
        debian)
            apt-get --simulate --no-remove --no-install-recommends install "${missing_packages[@]}" > "$output" 2>&1 || status=$?
            ;;
        arch)
            pacman -Sp --needed --color never --print-format '%n %v' "${missing_packages[@]}" > "$output" 2> "$output.stderr" || status=$?
            ;;
        fedora)
            if command -v dnf5 >/dev/null; then
                dnf5 -y --setopt=obsoletes=False --setopt=install_weak_deps=False \
                    install --downloadonly --no-allow-downgrade --store="$output.transaction" "${missing_packages[@]}" > "$output" 2>&1 || status=$?
            else
                dnf --assumeno --setopt=obsoletes=False --setopt=install_weak_deps=False \
                    install "${missing_packages[@]}" > "$output" 2>&1 || status=$?
                if ((status == 1)) && grep -q '^Transaction Summary' "$output"; then status=0; fi
            fi
            ;;
        suse)
            zypper --xmlout --non-interactive --no-refresh install --dry-run --no-recommends \
                --no-allow-downgrade --no-allow-vendor-change --no-force-resolution \
                "${missing_packages[@]}" > "$output" 2> "$output.stderr" || status=$?
            ;;
    esac
    if ((status)); then
        cat "$output" >&2
        [[ ! -f $output.stderr ]] || cat "$output.stderr" >&2
        fail 'The native resolver cannot install these dependencies safely. No packages were changed; existing providers will not be removed to make it pass.'
    fi
}

transaction_records() {
    local output=$1
    case "$family" in
        debian)
            awk '
                /^Remv / {print "remove\t" $2 "\t-"; next}
                /^Inst / {
                    name=$2; action=($3 ~ /^\[/ ? "upgrade" : "install")
                    sub(/^[^(]*\(/, ""); split($0, fields, " ")
                    print action "\t" name "\t" fields[1]
                }' "$output"
            ;;
        arch)
            awk 'NF == 2 && $1 !~ /^::/ {print "install\t" $1 "\t" $2; next}
                 NF {print "unknown\t-\t-"}' "$output"
            ;;
        fedora)
            if [[ -f $output.transaction/transaction.json ]]; then
                python3 -B -I "$ROOT/tools/runtime_admin.py" --user "$desktop_user" dnf-plan --manifest "$output.transaction/transaction.json"
                return
            fi
            awk '
                /^[[:space:]]*(Removing|Erasing|Downgrading|Obsoleting|Replacing)[[:space:]:]/ || /[[:space:]]replacing[[:space:]]/ {print "remove\t-\t-"}
                /^Transaction Summary/ {summary=1; action=""; next}
                !summary && /^[[:space:]]*(Installing|Upgrading|Reinstalling)( dependencies| weak dependencies)?:/ {
                    action=($1 ~ /Upgrading/ ? "upgrade" : "install"); next
                }
                action && $2 ~ /^(noarch|x86_64|aarch64|i[3-6]86|armv[5-8].*|ppc64.*|s390x|riscv64)$/ {
                    print action "\t" $1 "." $2 "\t" $3; pending=""; next
                }
                action && NF == 1 && $1 ~ /^[A-Za-z0-9][A-Za-z0-9+_.-]*$/ {pending=$1; next}
                action && pending != "" && $1 ~ /^(noarch|x86_64|aarch64|i[3-6]86|armv[5-8].*|ppc64.*|s390x|riscv64)$/ {
                    print action "\t" pending "." $1 "\t" $2; pending=""
                }
                END {if (!summary) print "unknown\t-\t-"}' "$output"
            ;;
        suse)
            sed 's/></>\n</g' "$output" | awk '
                function attribute(line, name, value) {
                    value=line
                    if (!match(value, name "=\"[^\"]*\"")) return ""
                    value=substr(value, RSTART, RLENGTH)
                    sub(/^[^=]*="/, "", value); sub(/"$/, "", value)
                    return value
                }
                /<install-summary[ >]/ {summary=1}
                /<to-install[ >]/ {action="install"}
                /<to-upgrade[ >]/ {action="upgrade"}
                /<to-reinstall[ >]/ {action="install"}
                /<to-(remove|downgrade|change-vendor|change-arch)[ >]/ {action="remove"}
                /<solvable[ >]/ && action != "" {
                    print action "\t" attribute($0, "name") "\t" attribute($0, "edition")
                }
                /<\/to-/ {action=""}
                END {if (!summary) print "unknown\t-\t-"}'
            ;;
    esac
}

review_package_transaction() {
    local records=$1 action package version previous comparison
    local count=0
    local upgrades_needed=no
    approved_packages=()
    while IFS=$'\t' read -r action package version; do
        [[ $action == install || $action == upgrade ]] || fail "Package removal/replacement/downgrade or unknown transaction detected ($action). No packages were installed."
        [[ $package =~ ^[A-Za-z0-9][A-Za-z0-9+_.:-]*$ && $version =~ ^[A-Za-z0-9][A-Za-z0-9+_.:~^%-]*$ ]] || fail 'Cannot safely parse the package transaction; refusing to apply it.'
        if [[ ${package%%:*} == quickshell || $family == fedora && ${package%.*} == quickshell ]]; then
            [[ ${version#*:} =~ ^([0-9]+)\.([0-9]+)\.([0-9]+) ]] || fail "Cannot verify the native Quickshell candidate version: $version"
            ((10#${BASH_REMATCH[1]} > 0 || 10#${BASH_REMATCH[2]} > 3 ||
                (10#${BASH_REMATCH[2]} == 3 && 10#${BASH_REMATCH[3]} >= 1))) || fail "Native Quickshell candidate $version is too old (>=0.3.1 required). No packages were installed; use a compatible distro/repository."
        fi
        if package_installed "$package"; then
            previous="$(package_version "$package")" || fail "Cannot inspect installed version: $package"
            case "$family" in
                debian)
                    if dpkg --compare-versions "$version" lt "$previous"; then fail "Downgrade rejected: $package $previous -> $version"; fi
                    if dpkg --compare-versions "$version" eq "$previous"; then continue; fi
                    ;;
                arch)
                    comparison="$(vercmp "$version" "$previous")" || fail 'pacman vercmp is required.'
                    ((comparison >= 0)) || fail "Downgrade rejected: $package $previous -> $version"
                    if ((comparison == 0)); then continue; fi
                    ;;
                fedora|suse)
                    if [[ $version == "$previous" || "0:$version" == "$previous" ]]; then continue; fi
                    [[ $action == upgrade ]] || fail "Unexpected replacement of installed package: $package $previous -> $version"
                    ;;
            esac
            printf 'UPGRADE %s: %s -> %s\n' "$package" "$previous" "$version"
            upgrades_needed=yes
        else
            printf 'INSTALL %s %s\n' "$package" "$version"
        fi
        case "$family" in
            debian|suse) approved_packages+=("$package=$version") ;;
            fedora) approved_packages+=("${package%.*}-$version.${package##*.}") ;;
            arch) approved_packages+=("$package=$version") ;;
        esac
        count=$((count + 1))
    done < "$records"
    ((count > 0)) || fail 'The requested transaction has no readable package changes. Refresh repository metadata and retry; nothing was installed.'
    if [[ $upgrades_needed == yes && $allow_dependency_upgrades != yes ]]; then
        if [[ ${mode:-install} == plan ]]; then
            printf '%s\n' 'REQUIRES APPROVAL: applying this plan needs --allow-dependency-upgrades.'
        else
            fail 'The displayed transaction upgrades existing packages. Nothing was installed. Review it and use --allow-dependency-upgrades only if intended.'
        fi
    fi
}

confirm_package_transaction() {
    local answer
    if [[ $assume_yes == yes ]]; then return; fi
    [[ -t 0 ]] || fail 'No interactive terminal. Review --plan first; use --yes to approve the package transaction explicitly.'
    printf 'Install exactly the reviewed dependencies? [y/N] '
    read -r answer || fail 'Package installation cancelled.'
    [[ $answer == y || $answer == Y || $answer == yes ]] || fail 'Package installation cancelled; no packages were changed.'
}

apply_package_transaction() {
    local stage=$1 hook_dir
    local hook_arguments=()
    case "$family" in
        debian)
            install -m 700 "$ROOT/tools/install/apt-transaction-guard.sh" "$stage/apt-transaction-guard.sh"
            DEBIAN_FRONTEND=noninteractive apt-get install -y --no-remove --no-install-recommends \
                -o APT::Get::allow-Downgrades=false \
                -o "DPkg::Pre-Install-Pkgs::=$stage/apt-transaction-guard.sh" "${approved_packages[@]}"
            ;;
        arch)
            mkdir "$stage/hooks"
            {
                printf '[Trigger]\nOperation=Remove\n'
                if [[ $allow_dependency_upgrades != yes ]]; then printf 'Operation=Upgrade\n'; fi
                printf 'Type=Package\nTarget=*\n\n[Action]\nDescription=Reject unapproved CyberLab dependency changes\nWhen=PreTransaction\nExec=/usr/bin/false\nAbortOnFail\n'
            } > "$stage/hooks/cyberlab-guard.hook"
            command -v pacman-conf >/dev/null || fail 'pacman-conf is required to preserve existing transaction hooks.'
            while IFS= read -r hook_dir; do
                if [[ -d $hook_dir ]]; then hook_arguments+=(--hookdir "$hook_dir"); fi
            done < <(pacman-conf HookDir)
            pacman -S --needed --noconfirm "${hook_arguments[@]}" --hookdir "$stage/hooks" "${approved_packages[@]}"
            ;;
        fedora)
            if command -v dnf5 >/dev/null; then
                [[ -f $stage/plan.txt.transaction/transaction.json ]] || fail 'Missing reviewed DNF5 transaction; refusing an unreviewed resolver fallback.'
                dnf5 -y --setopt=obsoletes=False --setopt=install_weak_deps=False \
                    --setopt=localpkg_gpgcheck=True replay "$stage/plan.txt.transaction"
            else
                dnf install -y --setopt=obsoletes=False --setopt=install_weak_deps=False "${approved_packages[@]}"
            fi
            ;;
        suse)
            zypper --non-interactive --no-refresh install --no-recommends --no-allow-downgrade \
                --no-allow-vendor-change --no-force-resolution "${approved_packages[@]}"
            ;;
    esac
}

guarded_package_install() {
    local stage
    stage="$(mktemp -d /var/tmp/cyberlab-dependencies-XXXXXXXX)"
    printf 'Dependency plan and receipts: %s\n' "$stage"
    package_inventory > "$stage/installed-before.txt"
    resolve_package_transaction "$stage/plan.txt"
    transaction_records "$stage/plan.txt" > "$stage/approved.tsv"
    cat "$stage/plan.txt"
    review_package_transaction "$stage/approved.tsv"
    if [[ ${mode:-install} == plan ]]; then
        printf '%s\n' 'Plan only. No packages, services or catalog were changed.'
        return
    fi
    confirm_package_transaction
    package_inventory > "$stage/installed-reviewed.txt"
    cmp -s "$stage/installed-before.txt" "$stage/installed-reviewed.txt" || fail "Installed packages changed during review. Plan retained at $stage; rerun without forcing."
    resolve_package_transaction "$stage/rechecked.txt"
    transaction_records "$stage/rechecked.txt" > "$stage/rechecked.tsv"
    cmp -s "$stage/approved.tsv" "$stage/rechecked.tsv" || fail "Dependency resolution changed during review. Plan retained at $stage; no packages were installed."
    apply_package_transaction "$stage"
    package_inventory > "$stage/installed-after.txt"
    printf 'Native dependency transaction completed; receipt retained at %s\n' "$stage"
}
