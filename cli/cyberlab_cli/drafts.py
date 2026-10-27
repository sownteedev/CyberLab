import json
import os
import sys
from pathlib import Path
import re
import stat

from cyberlab_ipc import MAX_DRAFT_ASSET, MAX_DRAFT_DEFINITION, MAX_DRAFT_PACKAGE

def read_file(name, limit, parent=None):
    descriptor = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC, dir_fd=parent)
    with os.fdopen(descriptor, "rb") as source:
        before = os.fstat(source.fileno())
        if not stat.S_ISREG(before.st_mode) or before.st_size > limit or before.st_nlink != 1:
            raise ValueError("Draft input must be a bounded regular file without symlinks or hardlinks")
        data = source.read(limit + 1)
        after = os.fstat(source.fileno())
        if len(data) > limit or (before.st_size, before.st_mtime_ns, before.st_ctime_ns) != (after.st_size, after.st_mtime_ns, after.st_ctime_ns):
            raise ValueError("Draft input changed or exceeded its limit while reading")
        return data

def safe_asset(path):
    parts = path.split("/")
    if not path.startswith("assets/") or len(path) > 200 or len(parts) > 8 or not all(re.fullmatch(r"[A-Za-z0-9_][A-Za-z0-9_.-]{0,63}", part) for part in parts):
        raise ValueError("Use safe relative asset paths under assets/; hidden files are not imported")

def read_tree(source, prefix):
    safe_asset(prefix + "/file")
    entries = []
    count = 0
    total = 0
    root = os.open(source, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)
    device = os.fstat(root).st_dev
    def walk(directory, target):
        nonlocal count, total
        with os.scandir(directory) as iterator:
            names = []
            for entry in iterator:
                count += 1
                if count > 128:
                    raise ValueError("Asset folder exceeds 128 entries")
                names.append(entry.name)
        for name in sorted(names):
            destination = target + "/" + name
            safe_asset(destination)
            before = os.stat(name, dir_fd=directory, follow_symlinks=False)
            if before.st_dev != device:
                raise ValueError("Asset folder crosses a filesystem boundary")
            if stat.S_ISDIR(before.st_mode):
                child = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=directory)
                try:
                    actual = os.fstat(child)
                    if (actual.st_dev, actual.st_ino) != (before.st_dev, before.st_ino):
                        raise ValueError("Asset folder changed while reading")
                    walk(child, destination)
                finally:
                    os.close(child)
            elif stat.S_ISREG(before.st_mode):
                data = read_file(name, min(MAX_DRAFT_ASSET, MAX_DRAFT_PACKAGE - total), directory)
                total += len(data)
                entries.append([destination, data])
            else:
                raise ValueError("Asset folders cannot contain symlinks or special files")
    try:
        walk(root, prefix)
    finally:
        os.close(root)
    if not entries:
        raise ValueError("Folder contains no regular files; empty directories are not represented")
    return entries

def add_parser(commands):
    parser = commands.add_parser("draft", help="Author Labs through the same daemon API used by future UI clients")
    actions = parser.add_subparsers(dest="draft_action", required=True)
    for action in ("info", "list"):
        actions.add_parser(action)
    create = actions.add_parser("create", help="Create an incomplete, private draft; never starts a Lab")
    create.add_argument("lab_id")
    create.add_argument("--title", required=True)
    clone = actions.add_parser("clone", help="Clone an installed Lab into a private draft")
    clone.add_argument("source_lab_id")
    clone.add_argument("--as", dest="target_lab_id", required=True)
    clone.add_argument("--title", required=True)
    edit = actions.add_parser("edit", help="Create a private editing draft with the installed Lab's reviewed digest")
    edit.add_argument("id", help="Installed Lab ID")
    update = actions.add_parser("update", help="Replace one installed Lab after exact review; never use while its Sessions run")
    update.add_argument("lab_id")
    update.add_argument("draft_id")
    update.add_argument("--revision", type=int, required=True)
    update.add_argument("--digest", required=True)
    update.add_argument("--catalog-digest", required=True)
    update.add_argument("--yes", action="store_true", help="Confirm replacement of this exact installed Lab")
    for action in ("show", "save", "put-file", "put-tree", "asset", "remove-asset", "check", "runtime-check", "publish", "delete"):
        command = actions.add_parser(action, **({"help": "Save your validated draft as a new Lab in the local library; no sudo required"} if action == "publish" else {}))
        command.add_argument("id", help="Draft ID, not Lab or Session ID")
        if action != "show":
            command.add_argument("--revision", type=int, required=True, help="Expected revision from the last response; stale writes are rejected")
        if action == "show":
            command.add_argument("--definition", action="store_true", help="Output only YAML/JSON definition for editing")
        if action in {"save", "put-file", "put-tree"}:
            command.add_argument("source", help="Local file/folder; save also accepts - for bounded UTF-8 stdin")
        if action in {"put-file", "remove-asset", "asset"}:
            command.add_argument("path", help="Logical asset path under assets/, never a host mount")
        if action == "put-tree":
            command.add_argument("--prefix", default="assets", help="Logical destination prefix; the batch is applied atomically")
        if action == "asset":
            destination = command.add_mutually_exclusive_group(required=True)
            destination.add_argument("--output", help="New local output file; refuses overwrite")
            destination.add_argument("--text", action="store_true", help="Return bounded UTF-8 asset text as JSON")
        if action == "publish":
            command.add_argument("--digest", required=True, help="Exact digest of the draft revision you checked")

def prepare(arguments):
    action = arguments.draft_action
    if action == "update" and not getattr(arguments, "yes", False):
        raise ValueError("Updating replaces an installed Lab; pass --yes after reviewing both digests")
    if action in {"clone", "update"}:
        return None
    if action == "save":
        if arguments.source == "-":
            if sys.stdin.isatty():
                raise ValueError("Pipe a definition to stdin; interactive stdin is not supported")
            data = sys.stdin.buffer.read(MAX_DRAFT_DEFINITION + 1)
            if len(data) > MAX_DRAFT_DEFINITION:
                raise ValueError("Draft definition exceeds 64 KiB")
            return data.decode("utf-8")
        return read_file(arguments.source, MAX_DRAFT_DEFINITION).decode("utf-8")
    if action == "put-file":
        safe_asset(arguments.path)
        if arguments.source == "-":
            if sys.stdin.isatty():
                raise ValueError("Pipe asset bytes to stdin; interactive stdin is not supported")
            data = sys.stdin.buffer.read(MAX_DRAFT_ASSET + 1)
            if len(data) > MAX_DRAFT_ASSET:
                raise ValueError("Draft asset exceeds its byte limit")
        else:
            data = read_file(arguments.source, MAX_DRAFT_ASSET)
        return [[arguments.path, data]]
    if action == "put-tree":
        return read_tree(arguments.source, arguments.prefix)
    return None

async def run(bus, request, arguments, prepared):
    action = arguments.draft_action
    methods = {"info": "GetAuthoringInfo", "list": "ListDrafts", "create": "CreateDraft", "clone": "CloneLab", "edit": "EditLab", "show": "GetDraft",
               "save": "SaveDraft", "put-file": "PutDraftAssets", "put-tree": "PutDraftAssets", "asset": "GetDraftAsset",
               "remove-asset": "RemoveDraftAsset", "check": "ValidateDraft", "runtime-check": "CheckDraftRuntime", "publish": "PublishDraft", "delete": "DeleteDraft"}
    body = []
    if action == "create":
        body = [arguments.lab_id, arguments.title]
    elif action == "clone":
        body = [arguments.source_lab_id, arguments.target_lab_id, arguments.title]
    elif action == "update":
        body = [arguments.lab_id, arguments.draft_id, arguments.revision, arguments.digest, arguments.catalog_digest]
    elif action not in {"info", "list"}:
        body = [arguments.id]
        if action not in {"show", "edit"}:
            body.append(arguments.revision)
        if action in {"save", "put-file", "put-tree"}:
            body.append(prepared)
        elif action in {"asset", "remove-asset"}:
            body.append(arguments.path)
        elif action == "publish":
            body.append(arguments.digest)
    if action == "update":
        result = await request(bus, "UpdateLab", body)
    else:
        result = await request(bus, methods[action], body)
    if action == "asset":
        if getattr(arguments, "text", False):
            if len(result) > 64 * 1024:
                raise ValueError("Text preview exceeds 64 KiB")
            text = bytes(result).decode("utf-8")
            if "\x00" in text:
                raise ValueError("Text preview cannot contain NUL bytes")
            return {"path": arguments.path, "content": text}
        descriptor = os.open(arguments.output, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC, 0o600)
        with os.fdopen(descriptor, "wb") as output:
            output.write(result)
        return {"saved": True, "bytes": len(result), "output": str(arguments.output)}
    if action == "delete":
        return {"deleted": result}
    return json.loads(result)
