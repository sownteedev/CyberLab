#!/usr/bin/env bash
set -euo pipefail

root="$(CDPATH='' cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)"
if [[ $EUID -eq 0 ]]; then
    printf '%s\n' 'Run Studio as the desktop user, not with sudo.' >&2
    exit 1
fi
if [[ ! -x "$root/.venv/bin/python" ]]; then
    printf '%s\n' 'Create a fresh development venv: python3 -m venv .venv && .venv/bin/python -m pip install -e .' >&2
    exit 1
fi
exec "$root/.venv/bin/python" -I -m cyberlab_studio.launcher "$@"
