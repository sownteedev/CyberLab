"""Compatibility entry point for existing development desktop shortcuts."""

from pathlib import Path
import subprocess
import sys

if __name__ == "__main__":
    if any(argument in {"--demo", "--smoke", "--screenshot", "--inside-demo"} for argument in sys.argv[1:]):
        raise SystemExit("The old fixture-based preview is archived; no daemon or Studio was started. Use tools/run_studio.sh for the real app")
    raise SystemExit(subprocess.call(["/bin/bash", str(Path(__file__).with_suffix(".sh")), *sys.argv[1:]]))
