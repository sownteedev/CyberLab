#!/usr/bin/env bash
set -euo pipefail

directory="$(CDPATH='' cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
while IFS= read -r archive; do
    [[ -f $archive && ! -L $archive && $archive == *.deb ]] || { printf 'Unexpected APT hook input: %s\n' "$archive" >&2; exit 1; }
    package="$(dpkg-deb -f "$archive" Package)"
    version="$(dpkg-deb -f "$archive" Version)"
    architecture="$(dpkg-deb -f "$archive" Architecture)"
    awk -F '\t' -v package="$package" -v version="$version" -v architecture="$architecture" '
        ($2 == package || $2 == package ":" architecture) && $3 == version { found=1 }
        END { exit !found }
    ' "$directory/approved.tsv" || { printf 'APT transaction changed after review: %s %s\n' "$package" "$version" >&2; exit 1; }
done
