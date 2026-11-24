"""Bounded, atomic edits to a draft's definition and seed resources."""

import json
import base64

from cyberlab.lab.package import MAX_PACKAGE, MAX_PATHS, asset_path, check_package
from .store import DraftNotFound

MAX_WORKSPACE_REQUEST = MAX_PACKAGE * 6
MAX_TEXT = 64 * 1024


def save_workspace(store, identifier, revision, payload, uid):
    if not isinstance(payload, str) or len(payload.encode("utf-8")) > MAX_WORKSPACE_REQUEST:
        raise ValueError("Workspace request exceeds its byte limit")
    update = json.loads(payload)
    if not isinstance(update, dict) or set(update) != {"definition", "entries", "removals"}:
        raise ValueError("Expected definition, entries and removals")
    entries, removals = update["entries"], update["removals"]
    if (not isinstance(entries, dict) or not isinstance(removals, list)
            or len(entries) > MAX_PATHS or len(removals) > MAX_PATHS):
        raise ValueError("Workspace edits exceed the path limit")
    with store.transaction() as connection:
        snapshot = store._snapshot(connection, store._row(connection, identifier, uid, revision))
        original = snapshot["assets"]
        assets = dict(original)
        for path in removals:
            asset_path(path)
            if path not in original:
                raise DraftNotFound("Removed asset no longer exists")
            assets.pop(path, None)
        for path, entry in entries.items():
            asset_path(path)
            if not isinstance(entry, dict) or len(entry) != 1:
                raise ValueError("Each resource needs exactly one content type")
            if "text" in entry:
                text = entry["text"]
                if not isinstance(text, str) or "\x00" in text or len(text.encode("utf-8")) > MAX_TEXT:
                    raise ValueError("Editable files must be UTF-8 text up to 64 KiB without NUL")
                assets[path] = text.encode("utf-8")
            elif entry.get("directory") is True:
                assets[path] = None
            elif "bytes" in entry:
                if not isinstance(entry["bytes"], str):
                    raise ValueError("Binary resource must be base64 text")
                assets[path] = base64.b64decode(entry["bytes"], validate=True)
            elif "copy" in entry:
                asset_path(entry["copy"])
                if entry["copy"] not in original:
                    raise DraftNotFound("Copied asset no longer exists")
                assets[path] = original[entry["copy"]]
            else:
                raise ValueError("Unknown resource content type")
        check_package(update["definition"], assets)
        connection.execute("UPDATE drafts SET definition=?,revision=revision+1 WHERE id=?",
                           (update["definition"], identifier))
        store._write_assets(connection, identifier, assets)
        return store._snapshot(connection, store._row(connection, identifier, uid))
