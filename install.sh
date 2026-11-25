#!/usr/bin/env bash
set -Eeuo pipefail
export PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
unset PYTHONPATH PYTHONHOME LD_PRELOAD LD_LIBRARY_PATH BASH_ENV ENV

entry="${BASH_SOURCE[0]:-}"
if [[ -n "$entry" && -f "$entry" ]]; then
    root="$(CDPATH='' cd -- "$(dirname -- "$entry")" && pwd -P)"
    if [[ -f "$root/tools/install/system.sh" && -f "$root/pyproject.toml" ]]; then
        exec /bin/bash "$root/tools/install/system.sh" "$@"
    fi
fi
command -v python3 >/dev/null || { printf '%s\n' 'CyberLab cần Python 3 để tải bộ cài. Hãy cài python3 bằng trình quản lý gói của máy.' >&2; exit 1; }
python3 -I - "$@" <<'PY'
import io
import json
from pathlib import Path
import re
import signal
import subprocess
import sys
import tempfile
import urllib.request

def fetch(url, limit):
    request = urllib.request.Request(url, headers={"User-Agent": "CyberLab-installer"})
    with urllib.request.urlopen(request, timeout=45) as response:
        if not response.url.startswith("https://"):
            raise ValueError("HTTPS required")
        content = response.read(limit + 1)
    if len(content) > limit:
        raise ValueError("Download limit exceeded")
    return content

signal.signal(signal.SIGTERM, lambda *_: sys.exit(143))
try:
    reference = json.loads(fetch("https://api.github.com/repos/sownteedev/CyberLab/git/ref/heads/master", 65536))["object"]
    if reference.get("type") != "commit":
        raise ValueError("Expected a commit reference")
    commit = reference["sha"]
    if not isinstance(commit, str) or not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise ValueError("Invalid commit")
    with tempfile.TemporaryDirectory(prefix="cyberlab-bootstrap-", dir="/var/tmp") as directory:
        helper = Path(directory) / "bootstrap.py"
        helper.write_bytes(fetch(f"https://raw.githubusercontent.com/sownteedev/CyberLab/{commit}/cli/cyberlab_cli/system_update.py", 128 * 1024))
        try:
            terminal = open("/dev/tty", "rb")
        except OSError:
            terminal = open("/dev/null", "rb")
        with terminal:
            process = subprocess.Popen([sys.executable, "-I", str(helper), "--install", "--commit", commit, *sys.argv[1:]], stdin=terminal)
            try:
                result = process.wait()
            except BaseException:
                previous = {signum: signal.signal(signum, signal.SIG_IGN) for signum in (signal.SIGINT, signal.SIGTERM)}
                try:
                    if process.poll() is None:
                        process.terminate()
                    while process.poll() is None:
                        try:
                            process.wait()
                        except (KeyboardInterrupt, SystemExit):
                            continue
                finally:
                    for signum, handler in previous.items():
                        signal.signal(signum, handler)
                raise
    raise SystemExit(result)
except (OSError, ValueError, KeyError) as error:
    raise SystemExit(f"Không thể tải bộ cài CyberLab: {error}")
except KeyboardInterrupt:
    raise SystemExit(130)
PY
