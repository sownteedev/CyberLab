"""Stage an independent, non-root update window before Studio exits."""
import argparse
import fcntl
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time

PYTHON = "/usr/bin/python3"
STUDIO = "/usr/local/bin/cyberlab-studio"


def process_identity(pid):
    if pid <= 1:
        raise ValueError("PID Studio không hợp lệ")
    process = Path("/proc") / str(pid)
    try:
        if process.stat().st_uid != os.getuid():
            raise ValueError("Studio không thuộc tài khoản hiện tại")
        return (process / "stat").read_text().rsplit(") ", 1)[1].split()[19]
    except FileNotFoundError:
        return None


def safe_environment():
    environment = os.environ.copy()
    for key in ("PYTHONPATH", "PYTHONHOME", "LD_PRELOAD", "LD_LIBRARY_PATH", "QML_IMPORT_PATH",
                "QML2_IMPORT_PATH", "QT_PLUGIN_PATH", "CYBERLAB_STUDIO_SMOKE", "CYBERLAB_STUDIO_TEST_BUS"):
        environment.pop(key, None)
    return environment


def launch_window(commit, wait_pid, theme="system"):
    from importlib.resources import files
    from cyberlab_cli import system_update
    from cyberlab_studio.launcher import resolve_quickshell

    if os.geteuid() == 0:
        raise ValueError("Không chạy cửa sổ cập nhật bằng root")
    if not system_update.valid_commit(commit):
        raise ValueError("Commit cập nhật không hợp lệ")
    if not os.access("/usr/bin/pkexec", os.X_OK):
        raise ValueError("Máy chưa có pkexec. Hãy cập nhật bằng cyberlab update trong terminal.")
    identity = process_identity(wait_pid)
    if identity is None:
        raise ValueError("Studio đã đóng; hãy chạy cyberlab update trong terminal.")
    executable = resolve_quickshell(require_native=True)
    stage = Path(tempfile.mkdtemp(prefix="cl-updater-", dir="/var/tmp"))
    supervisor = None
    try:
        shutil.copytree(Path(str(files("cyberlab_studio").joinpath("studio"))), stage / "studio",
                        ignore=shutil.ignore_patterns("testing", "__pycache__"))
        shutil.copyfile(stage / "studio/update.qml", stage / "studio/shell.qml")
        shutil.copyfile(__file__, stage / "window.py")
        shutil.copyfile(system_update.__file__, stage / "engine.py")
        (stage / "config.json").write_text(json.dumps({"commit": commit, "pid": wait_pid,
            "identity": identity, "quickshell": str(executable),
            "theme": theme if theme in {"light", "dark", "system"} else "system"}))
        with (stage / "window.log").open("wb") as log:
            supervisor = subprocess.Popen([PYTHON, "-I", "-B", str(stage / "window.py"), "supervise", str(stage)],
                stdin=subprocess.DEVNULL, stdout=log, stderr=log, start_new_session=True, env=safe_environment())
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            if (stage / "ready").is_file() and supervisor.poll() is None:
                return {"ready": True}
            if supervisor.poll() is not None:
                break
            time.sleep(0.1)
        raise ValueError("Không mở được cửa sổ cập nhật. Studio vẫn giữ nguyên; thử cyberlab update trong terminal.")
    except BaseException:
        if supervisor is not None and supervisor.poll() is None:
            (stage / "cancel").touch()
        else:
            shutil.rmtree(stage, ignore_errors=True)
        raise


def supervise(stage):
    config = json.loads((stage / "config.json").read_text())
    environment = safe_environment()
    environment.update(CYBERLAB_UPDATE_STAGE=str(stage), CYBERLAB_UPDATE_THEME=config["theme"],
                       XDG_CACHE_HOME=str(stage / "cache"), XDG_STATE_HOME=str(stage / "state"),
                       XDG_DATA_HOME=str(stage / "data"))
    try:
        process = subprocess.Popen([config["quickshell"], "--path", str(stage / "studio")], env=environment)
        process.wait()
        return 0
    finally:
        with (stage / "worker.lock").open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            shutil.rmtree(stage, ignore_errors=True)


def run_worker(stage):
    config = json.loads((stage / "config.json").read_text())
    print(json.dumps({"event": "waiting"}), flush=True)
    deadline = time.monotonic() + 120
    while process_identity(config["pid"]) == config["identity"]:
        if (stage / "cancel").exists() or time.monotonic() > deadline:
            raise ValueError("Studio chưa đóng. Không thay đổi bản cài; đóng cửa sổ cập nhật rồi thử lại.")
        time.sleep(0.2)
    time.sleep(0.5)
    spec = importlib.util.spec_from_file_location("update_engine", stage / "engine.py")
    engine = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(engine)
    return engine.run_update(json_output=True, commit=config["commit"], graphical=True)


def restart_studio():
    process = subprocess.Popen([STUDIO], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                               stderr=subprocess.DEVNULL, start_new_session=True, env=safe_environment())
    time.sleep(0.8)
    if process.poll() is not None:
        raise ValueError("CyberLab chưa mở được. Hãy kiểm tra bản cài từ terminal.")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("operation", choices=["supervise", "run", "ready", "restart"])
    parser.add_argument("stage", type=Path)
    arguments = parser.parse_args()
    stage = arguments.stage
    try:
        if stage.is_symlink() or stage.parent != Path("/var/tmp") or not stage.name.startswith("cl-updater-") or stage.stat().st_uid != os.getuid():
            raise ValueError("Thư mục cập nhật không hợp lệ")
        if arguments.operation == "supervise":
            return supervise(stage)
        if arguments.operation == "run":
            with (stage / "worker.lock").open("a") as lock:
                fcntl.flock(lock, fcntl.LOCK_EX)
                return run_worker(stage)
        if arguments.operation == "restart":
            restart_studio()
            return 0
        (stage / arguments.operation).touch(mode=0o600)
        return 0
    except (OSError, ValueError, IndexError) as error:
        print(json.dumps({"event": "error", "message": str(error)}, ensure_ascii=False), flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
