"""System installation maintenance, independent of the daemon API."""

import argparse
from contextlib import contextmanager
import gzip
import json
import os
import pwd
from pathlib import Path, PurePosixPath
import re
import shutil
import signal
import subprocess
import sys
import tarfile
import tempfile
import urllib.request

REPOSITORY = "sownteedev/CyberLab"
BRANCH = "master"
RECEIPT = Path("/usr/lib/cyberlab/installation.json")
MAX_DOWNLOAD = 128 * 1024 * 1024
MAX_EXPANDED = 512 * 1024 * 1024
MAX_MEMBERS = 20000


def valid_commit(value):
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{40}", value) is not None


def download(url, destination, limit, progress=None):
    request = urllib.request.Request(url, headers={"User-Agent": "CyberLab-installer", "Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(request, timeout=45) as response:
        if not response.url.startswith("https://"):
            raise ValueError("Máy chủ tải xuống không sử dụng HTTPS")
        size = response.headers.get("Content-Length") if progress else None
        expected = int(size) if size and size.isdecimal() else None
        if expected is not None and expected > limit:
            raise ValueError("Dữ liệu tải xuống vượt giới hạn")
        total = 0
        while True:
            content = response.read(min(1024 * 1024, limit + 1 - total))
            if not content:
                break
            total += len(content)
            if total > limit:
                raise ValueError("Dữ liệu tải xuống vượt giới hạn")
            destination.write(content)
            if progress:
                progress("download", received=total, total=expected,
                         percent=min(100, int(total * 100 / expected)) if expected else None)
        if expected is not None and total != expected:
            raise ValueError("Dữ liệu tải xuống bị cắt cụt")


def latest_commit():
    import io
    output = io.BytesIO()
    download(f"https://api.github.com/repos/{REPOSITORY}/git/ref/heads/{BRANCH}", output, 65536)
    document = json.loads(output.getvalue())
    reference = document.get("object", {}) if isinstance(document, dict) else {}
    commit = reference.get("sha") if isinstance(reference, dict) and reference.get("type") == "commit" else None
    if not valid_commit(commit):
        raise ValueError("GitHub không trả về commit hợp lệ")
    return commit


def installed_commit(path=None):
    path = path or RECEIPT
    try:
        with path.open("rb") as stream:
            content = stream.read(65537)
        if len(content) > 65536:
            return None
        document = json.loads(content)
        commit = document.get("commit")
        return commit if valid_commit(commit) else None
    except (OSError, ValueError, AttributeError):
        return None


@contextmanager
def bounded_tar(archive):
    with tempfile.TemporaryFile(dir=archive.parent) as expanded:
        with gzip.open(archive, "rb") as compressed:
            total = 0
            while True:
                chunk = compressed.read(min(1024 * 1024, MAX_EXPANDED + 1 - total))
                if not chunk:
                    break
                total += len(chunk)
                if total > MAX_EXPANDED:
                    raise ValueError("Snapshot giải nén vượt giới hạn")
                expanded.write(chunk)
        expanded.seek(0)
        with tarfile.open(fileobj=expanded, mode="r|") as bundle:
            yield bundle


def extract_snapshot(archive, destination, commit):
    if not valid_commit(commit):
        raise ValueError("Commit không hợp lệ")
    destination.mkdir(mode=0o700)
    prefix = f"CyberLab-{commit}"
    seen = set()
    total = 0
    count = 0
    with bounded_tar(archive) as bundle:
        for member in bundle:
            count += 1
            if count > MAX_MEMBERS:
                raise ValueError("Snapshot có quá nhiều tệp")
            name = member.name.rstrip("/") if member.isdir() else member.name
            parts = name.split("/")
            if parts[0] != prefix or any(part in {"", ".", ".."} for part in parts) or "\\" in name or any(ord(character) < 32 for character in name):
                raise ValueError("Đường dẫn snapshot không an toàn")
            if name in seen or not (member.isdir() or member.isreg()) or member.size < 0:
                raise ValueError("Snapshot chứa tệp trùng, liên kết hoặc tệp đặc biệt")
            seen.add(name)
            total += member.size
            if total > MAX_EXPANDED:
                raise ValueError("Snapshot giải nén vượt giới hạn")
            if len(parts) == 1:
                if not member.isdir():
                    raise ValueError("Gốc snapshot phải là thư mục")
                continue
            target = destination.joinpath(*PurePosixPath(*parts[1:]).parts)
            if member.isdir():
                target.mkdir(parents=True, exist_ok=True, mode=0o700)
            else:
                target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
                with bundle.extractfile(member) as source, target.open("xb") as output:
                    remaining = member.size
                    while remaining:
                        block = source.read(min(remaining, 1024 * 1024))
                        if not block:
                            raise ValueError("Snapshot bị cắt cụt")
                        output.write(block)
                        remaining -= len(block)

def root_probe_access(root, source, arguments):
    if os.geteuid() != 0:
        return
    username = os.environ.get("SUDO_USER")
    for index, argument in enumerate(arguments):
        if argument == "--user" and index + 1 < len(arguments):
            username = arguments[index + 1]
    if not username:
        raise ValueError("Khi chạy bằng root, cần --user TÊN_TÀI_KHOẢN")
    account = pwd.getpwnam(username)
    if account.pw_uid == 0:
        raise ValueError("Tài khoản chạy Studio không được là root")
    for entry in (root, source, *source.rglob("*")):
        os.chown(entry, 0, account.pw_gid, follow_symlinks=False)
        entry.chmod(0o750 if entry.is_dir() else 0o640)

def finish_interrupted(process, *, drain=False):
    previous = {signum: signal.signal(signum, signal.SIG_IGN) for signum in (signal.SIGINT, signal.SIGTERM)}
    try:
        if process.poll() is None:
            try:
                process.terminate()
            except PermissionError:
                pass
        print("Đang chờ bộ cài kết thúc hoặc phục hồi; chưa xóa vùng tạm...", file=sys.stderr)
        if drain and process.stdout is not None:
            while process.stdout.read(65536):
                pass
        while process.poll() is None:
            try:
                process.wait()
            except (KeyboardInterrupt, SystemExit):
                continue
    finally:
        for signum, handler in previous.items():
            signal.signal(signum, handler)


def install_snapshot(commit, arguments=(), *, progress=None, graphical=False):
    if not valid_commit(commit):
        raise ValueError("Commit không hợp lệ")
    if shutil.disk_usage("/var/tmp").free < MAX_EXPANDED * 3:
        raise ValueError("Không đủ dung lượng tạm để tải và build CyberLab")
    with tempfile.TemporaryDirectory(prefix="cyberlab-download-", dir="/var/tmp") as directory:
        root = Path(directory)
        archive = root / "source.tar.gz"
        if progress:
            progress("download", percent=None)
        else:
            print(f"Đang tải CyberLab ({commit[:12]})...", flush=True)
        with archive.open("xb") as output:
            url = f"https://codeload.github.com/{REPOSITORY}/tar.gz/{commit}"
            if progress:
                download(url, output, MAX_DOWNLOAD, progress)
            else:
                download(url, output, MAX_DOWNLOAD)
        if progress:
            progress("extract", percent=None)
        source = root / "source"
        extract_snapshot(archive, source, commit)
        (source / ".cyberlab-source.json").write_text(json.dumps({"repository": REPOSITORY, "commit": commit}))
        root_probe_access(root, source, arguments)
        installer = source / "tools/install/system.sh"
        if not installer.is_file():
            raise ValueError("Commit này chưa hỗ trợ bộ cài mới; chưa thay đổi bản cài")
        environment = os.environ.copy()
        for key in ("PYTHONPATH", "PYTHONHOME", "BASH_ENV", "ENV", "LD_PRELOAD", "LD_LIBRARY_PATH"):
            environment.pop(key, None)
        command = ["/bin/bash", str(installer), *arguments]
        if graphical:
            if os.geteuid() == 0 or not os.access("/usr/bin/pkexec", os.X_OK):
                raise ValueError("Cần chạy từ tài khoản thường và có pkexec để xác thực quản trị.")
            command = ["/usr/bin/pkexec", "--disable-internal-agent", *command, "--user", pwd.getpwuid(os.getuid()).pw_name]
        if progress:
            progress("authorize" if graphical else "install", percent=None)
        options = {"stdout": subprocess.PIPE, "stderr": subprocess.STDOUT} if progress else {}
        process = subprocess.Popen(command, cwd=source, env=environment, **options)
        try:
            if progress:
                phases = {"build", "install", "verify"}
                while True:
                    line = process.stdout.readline(8192)
                    if not line:
                        break
                    text = line.decode("utf-8", errors="replace").rstrip()
                    if text.startswith("CYBERLAB_UPDATE_PHASE:") and text.split(":", 1)[1] in phases:
                        progress(text.split(":", 1)[1], percent=None)
                    print(text, file=sys.stderr, flush=True)
            return process.wait()
        except BaseException:
            finish_interrupted(process, drain=bool(progress))
            raise


def run_update(check=False, *, json_output=False, commit=None, graphical=False):
    def report(event, **values):
        if json_output:
            print(json.dumps({"event": event, **values}, ensure_ascii=False), flush=True)

    previous_signal = signal.signal(signal.SIGTERM, lambda *_: sys.exit(143))
    try:
        if commit is not None and not valid_commit(commit):
            raise ValueError("Commit cập nhật không hợp lệ")
        current = installed_commit()
        latest = commit or latest_commit()
        if check and json_output:
            report("checked", installed=current, latest=latest, available=current is not None and current != latest)
            return 0
        if current == latest:
            if json_output:
                report("complete", commit=latest, changed=False)
            else:
                print(f"CyberLab đã ở commit mới nhất trên master: {latest[:12]}.")
            return 0
        if not json_output:
            print(f"Đang cài: {current[:12] if current else 'chưa xác định commit'}. Bản trên master: {latest[:12]}.")
        if check:
            if current is None:
                print("Chưa thể xác định có bản mới: bản cài chưa ghi nhận commit. Bản cài chưa thay đổi.")
            else:
                print("Chạy cyberlab update để cập nhật; bản cài chưa thay đổi.")
            return 0
        if json_output or graphical:
            code = install_snapshot(latest, ("--update",), progress=report if json_output else None, graphical=graphical)
            if code:
                message = "Đã hủy xác thực quản trị." if code == 126 else "Cập nhật chưa hoàn tất. Xem chi tiết; bộ cài giữ hoặc phục hồi bản cũ khi có thể."
                report("error", message=message, code=code)
                return code
            if installed_commit() != latest:
                raise ValueError("Chưa xác minh được commit đã cài. Không tự thử lại; kiểm tra log và bản sao phục hồi.")
            report("complete", commit=latest, changed=True)
            return 0
        return install_snapshot(latest, ("--update",))
    except (OSError, ValueError, EOFError, tarfile.TarError, subprocess.SubprocessError) as error:
        if json_output:
            report("error", message=f"Không thể cập nhật CyberLab: {error}")
        else:
            print(f"Không thể cập nhật CyberLab: {error}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("Đã hủy cập nhật. Nếu bước cài đã bắt đầu, xem log phục hồi của bộ cài.", file=sys.stderr)
        return 130
    finally:
        signal.signal(signal.SIGTERM, previous_signal)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--install", action="store_true")
    parser.add_argument("--commit")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--graphical", action="store_true")
    arguments, forwarded = parser.parse_known_args()
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(143))
    if arguments.install:
        try:
            return install_snapshot(arguments.commit, forwarded)
        except (OSError, ValueError, EOFError, tarfile.TarError) as error:
            print(f"Không thể chuẩn bị bộ cài: {error}", file=sys.stderr)
            return 1
    return run_update(json_output=arguments.json, commit=arguments.commit, graphical=arguments.graphical)


if __name__ == "__main__":
    raise SystemExit(main())
