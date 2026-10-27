from io import BytesIO
import json
import stat
import zipfile
import zlib

from cyberlab.workspace import relative_path


def read_zip(data, *, max_archive, max_entries, max_content):
    if not isinstance(data, bytes) or not data or len(data) > max_archive:
        raise ValueError("Archive exceeds its byte limit or is empty")
    try:
        with zipfile.ZipFile(BytesIO(data)) as archive:
            infos = archive.infolist()
            if len(infos) > max_entries or sum(info.file_size for info in infos) > max_content:
                raise ValueError("Archive exceeds its entry or uncompressed byte limit")
            entries = {}
            for info in infos:
                name = info.filename
                if info.orig_filename != name:
                    raise ValueError("Archive contains a NUL path")
                path = name[:-1] if info.is_dir() else name
                relative_path(path)
                if path in entries:
                    raise ValueError("Archive contains duplicate entries")
                mode = stat.S_IFMT(info.external_attr >> 16)
                expected = stat.S_IFDIR if info.is_dir() else stat.S_IFREG
                if mode not in (0, expected):
                    raise ValueError("Archive contains a link, special file or conflicting type")
                if info.flag_bits & 1 or info.compress_type not in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED):
                    raise ValueError("Encrypted or unsupported archive compression")
                if info.is_dir() and info.file_size:
                    raise ValueError("Archive directory contains data")
                with archive.open(info) as source:
                    content = source.read(info.file_size + 1)
                if len(content) != info.file_size:
                    raise ValueError("Archive entry size is inconsistent")
                entries[path] = None if info.is_dir() else content
            for path in entries:
                parts = path.split("/")
                for count in range(1, len(parts)):
                    parent = "/".join(parts[:count])
                    if parent in entries and entries[parent] is not None:
                        raise ValueError("Archive path traverses a file")
            return entries
    except (OSError, EOFError, RuntimeError, NotImplementedError, zipfile.BadZipFile,
            zipfile.LargeZipFile, zlib.error) as error:
        raise ValueError("Invalid or damaged ZIP archive") from error


def json_object(data, limit):
    if not isinstance(data, bytes) or len(data) > limit:
        raise ValueError("JSON member is missing or exceeds its byte limit")

    def unique_pairs(pairs):
        value = {}
        for key, item in pairs:
            if key in value:
                raise ValueError("JSON contains duplicate keys")
            value[key] = item
        return value

    def invalid_constant(value):
        raise ValueError("JSON contains a non-finite number")

    try:
        value = json.loads(data.decode("utf-8"), object_pairs_hook=unique_pairs,
                           parse_constant=invalid_constant)
    except (UnicodeError, RecursionError) as error:
        raise ValueError("JSON is not bounded UTF-8 data") from error
    if not isinstance(value, dict):
        raise ValueError("JSON member must contain an object")
    return value
