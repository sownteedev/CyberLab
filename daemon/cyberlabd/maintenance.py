"""Shared request lease preventing runtime replacement during application work."""

from contextlib import contextmanager
import fcntl
import os
import stat

from cyberlab.service import SessionBusy


@contextmanager
def request_lease(path):
    descriptor = os.open(path, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600)
    try:
        status = os.fstat(descriptor)
        if not stat.S_ISREG(status.st_mode) or status.st_uid != os.geteuid() or status.st_nlink != 1 or status.st_mode & 0o077:
            raise SessionBusy("Khóa bảo trì không an toàn; cần quản trị viên kiểm tra")
        try:
            fcntl.flock(descriptor, fcntl.LOCK_SH | fcntl.LOCK_NB)
        except BlockingIOError:
            raise SessionBusy("CyberLab đang cập nhật. Vui lòng thử lại sau") from None
        yield
    finally:
        os.close(descriptor)
