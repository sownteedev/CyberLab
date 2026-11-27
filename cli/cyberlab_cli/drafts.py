import json
import base64
import os
import sys
from pathlib import Path
import re
import stat
import errno

from cyberlab_ipc import MAX_DRAFT_ASSET, MAX_DRAFT_DEFINITION, MAX_DRAFT_PACKAGE

def read_file(name, limit, parent=None):
    try:
        descriptor = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC, dir_fd=parent)
    except OSError as error:
        if error.errno == errno.ELOOP:
            raise ValueError("Draft input cannot be a symbolic link") from None
        raise
    with os.fdopen(descriptor, "rb") as source:
        before = os.fstat(source.fileno())
        if not stat.S_ISREG(before.st_mode):
            raise ValueError("Draft input must be a regular file")
        if before.st_nlink != 1:
            raise ValueError("Draft input cannot have hardlinks")
        if before.st_size > limit:
            raise ValueError(f"Draft input exceeds the byte limit: {before.st_size} > {limit}")
        data = source.read(limit + 1)
        after = os.fstat(source.fileno())
        if len(data) > limit or (before.st_size, before.st_mtime_ns, before.st_ctime_ns) != (after.st_size, after.st_mtime_ns, after.st_ctime_ns):
            raise ValueError("Draft input changed or exceeded its limit while reading")
        return data

def safe_asset(path):
    parts = path.split("/")
    if not path.startswith("assets/") or len(path) > 200 or len(parts) > 8 or not all(re.fullmatch(r"[A-Za-z0-9_][A-Za-z0-9_.-]{0,63}", part) for part in parts):
        raise ValueError("Use safe relative asset paths under assets/; hidden files are not imported")

def read_tree(source, prefix, include_directories=False):
    safe_asset(prefix + "/file")
    entries = []
    count = 0
    total = 0
    root = os.open(source, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)
    device = os.fstat(root).st_dev
    def walk(directory, target):
        nonlocal count, total
        if include_directories:
            entries.append([target, None])
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
    password = actions.add_parser("account-password", help="Replace or lock a draft account password using bounded JSON stdin only")
    password.add_argument("id")
    password.add_argument("node")
    password.add_argument("--revision", type=int, required=True)
    local = actions.add_parser("read-local", help="Read bounded local resources for the draft editor without modifying a draft")
    local.add_argument("source")
    local.add_argument("--folder", action="store_true")
    search = actions.add_parser("software-search", help="Search Ubuntu package names and descriptions")
    search.add_argument("query")
    search.add_argument("--refresh", action="store_true")
    for action in ("software-plan", "software-prepare"):
        operation = actions.add_parser(action)
        operation.add_argument("id")
        operation.add_argument("node")
        operation.add_argument("--revision", type=int, required=True)
    for action in ("software-status", "software-cancel", "software-apply"):
        operation = actions.add_parser(action)
        operation.add_argument("job")
    for action in ("info", "list"):
        actions.add_parser(action)
    create = actions.add_parser("create", help="Create an incomplete, private draft; never starts a Lab")
    create.add_argument("lab_id")
    create.add_argument("--title", required=True)
    create.add_argument("--tag", action="append", required=True, help="Topic ID from draft info; repeat for multiple topics")
    create.add_argument("--difficulty", choices=("easy", "medium", "hard"), required=True)
    clone = actions.add_parser("clone", help="Clone an installed Lab into a private draft")
    clone.add_argument("source_lab_id")
    clone.add_argument("--as", dest="target_lab_id", required=True)
    clone.add_argument("--title", required=True)
    edit = actions.add_parser("edit", help="Resume an editing draft; return choices if several exist, create only if none exist")
    edit.add_argument("id", help="Installed Lab ID")
    edit_choice = edit.add_mutually_exclusive_group()
    edit_choice.add_argument("--draft", help="Resume this existing editing draft")
    edit_choice.add_argument("--new", action="store_true", help="Explicitly create a separate draft; preserve existing drafts")
    update = actions.add_parser("update", help="Replace one installed Lab after exact review; never use while its Sessions run")
    update.add_argument("lab_id")
    update.add_argument("draft_id")
    update.add_argument("--revision", type=int, required=True)
    update.add_argument("--digest", required=True)
    update.add_argument("--catalog-digest", required=True)
    update.add_argument("--yes", action="store_true", help="Confirm replacement of this exact installed Lab")
    for action in ("show", "save", "save-workspace", "put-file", "put-tree", "asset", "remove-asset", "check", "runtime-check", "publish", "delete"):
        command = actions.add_parser(action, **({"help": "Save your validated draft as a new Lab in the local library; no sudo required"} if action == "publish" else {}))
        command.add_argument("id", help="Draft ID, not Lab or Session ID")
        if action != "show":
            command.add_argument("--revision", type=int, required=True, help="Expected revision from the last response; stale writes are rejected")
        if action == "show":
            command.add_argument("--definition", action="store_true", help="Output only YAML/JSON definition for editing")
        if action in {"save", "save-workspace", "put-file", "put-tree"}:
            command.add_argument("source", help="Local file/folder; save also accepts - for bounded UTF-8 stdin")
        if action in {"put-file", "remove-asset", "asset"}:
            command.add_argument("path", help="Logical asset path under assets/, never a host mount")
        if action == "put-tree":
            command.add_argument("--prefix", default="assets", help="Logical destination prefix; the batch is applied atomically")
        if action == "asset":
            destination = command.add_mutually_exclusive_group(required=True)
            destination.add_argument("--output", help="New local output file; refuses overwrite")
            destination.add_argument("--text", action="store_true", help="Return bounded UTF-8 asset text as JSON")
            destination.add_argument("--preview", action="store_true", help="Preview text or identify a binary resource")
        if action == "publish":
            command.add_argument("--digest", required=True, help="Exact digest of the draft revision you checked")

def prepare(arguments):
    action = arguments.draft_action
    if action == "account-password":
        if sys.stdin.isatty():
            raise ValueError("Pipe a password request as bounded JSON stdin")
        data = sys.stdin.buffer.read(8193)
        try:
            if len(data) > 8192:
                raise ValueError()
            payload = data.decode("utf-8")
            if not isinstance(json.loads(payload), dict):
                raise ValueError()
        except (ValueError, UnicodeError, RecursionError):
            raise ValueError("Invalid password request") from None
        return payload
    if action == "read-local":
        resources = (read_tree(arguments.source, "assets/input", True) if arguments.folder else
                     [("assets/input/" + Path(arguments.source).name, read_file(arguments.source, MAX_DRAFT_ASSET))])
        result = []
        for path, data in resources:
            relative = path.removeprefix("assets/input").lstrip("/")
            if data is None:
                result.append({"path": relative, "kind": "directory", "content": {"directory": True}})
                continue
            try:
                text = data.decode("utf-8") if len(data) <= 64 * 1024 else None
            except UnicodeDecodeError:
                text = None
            content = {"text": text} if text is not None and "\x00" not in text else {"bytes": base64.b64encode(data).decode("ascii")}
            result.append({"path": relative, "kind": "file", "content": content, "size": len(data)})
        return result
    if action == "save-workspace":
        limit = MAX_DRAFT_PACKAGE * 6
        if arguments.source == "-":
            if sys.stdin.isatty():
                raise ValueError("Pipe workspace JSON to stdin")
            data = sys.stdin.buffer.read(limit + 1)
        else:
            data = read_file(arguments.source, limit)
        if len(data) > limit:
            raise ValueError("Workspace request exceeds its byte limit")
        return data.decode("utf-8")
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
    if action == "account-password":
        return json.loads(await request(bus, "SetNodeAccountPassword",
                                        [arguments.id, arguments.revision, arguments.node, prepared]))
    if action == "read-local":
        return {"resources": prepared}
    if action == "software-search":
        from .package_search import search
        info = json.loads(await request(bus, "GetAuthoringInfo", []))
        if not info.get("software_search"):
            raise ValueError("Package search requires an updated software-enabled daemon")
        return search(arguments.query, arguments.refresh)
    if action.startswith("software-"):
        methods = {"software-plan": "PlanNodeSoftware", "software-prepare": "PrepareNodeSoftware", "software-status": "GetSoftwareJob", "software-cancel": "CancelSoftwareJob", "software-apply": "ApplySoftwareJob"}
        body = [arguments.id, arguments.revision, arguments.node] if action in {"software-plan", "software-prepare"} else [arguments.job]
        return json.loads(await request(bus, methods[action], body))
    methods = {"info": "GetAuthoringInfo", "list": "ListDrafts", "create": "CreateDraft", "clone": "CloneLab", "edit": "EditLab", "show": "GetDraft",
               "save": "SaveDraft", "save-workspace": "SaveDraftWorkspace", "put-file": "PutDraftAssets", "put-tree": "PutDraftAssets", "asset": "GetDraftAsset",
               "remove-asset": "RemoveDraftAsset", "check": "ValidateDraft", "runtime-check": "CheckDraftRuntime", "publish": "PublishDraft", "delete": "DeleteDraft"}
    body = []
    if action == "create":
        methods[action] = "CreateTaggedDraft"
        body = [arguments.lab_id, arguments.title, arguments.tag, arguments.difficulty]
    elif action == "clone":
        body = [arguments.source_lab_id, arguments.target_lab_id, arguments.title]
    elif action == "update":
        body = [arguments.lab_id, arguments.draft_id, arguments.revision, arguments.digest, arguments.catalog_digest]
    elif action not in {"info", "list"}:
        body = [arguments.id]
        if action not in {"show", "edit"}:
            body.append(arguments.revision)
        if action in {"save", "save-workspace", "put-file", "put-tree"}:
            body.append(prepared)
        elif action in {"asset", "remove-asset"}:
            body.append(arguments.path)
        elif action == "publish":
            body.append(arguments.digest)
    if action == "edit" and (arguments.draft or arguments.new):
        result = await request(bus, "ResolveLabDraft", [arguments.id, arguments.draft or "", arguments.new])
    elif action == "update":
        result = await request(bus, "UpdateLab", body)
    else:
        result = await request(bus, methods[action], body)
    if action == "asset":
        if getattr(arguments, "preview", False):
            try:
                text = bytes(result).decode("utf-8") if len(result) <= 64 * 1024 else None
            except UnicodeDecodeError:
                text = None
            editable = text is not None and "\x00" not in text
            return {"path": arguments.path, "editable": editable, "content": text if editable else "", "size": len(result)}
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
