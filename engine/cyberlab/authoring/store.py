from contextlib import contextmanager
import json
from pathlib import Path
import re
import sqlite3
from threading import RLock
from uuid import uuid4

from cyberlab.lab.package import (
    MAX_DEFINITION, MAX_ASSET, MAX_PACKAGE, MAX_PATHS, PackageLimit as DraftLimit,
    definition_text, asset_path, check_package, digest,
)

class DraftNotFound(Exception):
    pass

class DraftConflict(Exception):
    pass

class DraftStore:
    def __init__(self, database):
        self.database = str(database)
        self.lock = RLock()
        with self.transaction() as connection:
            if connection.execute("PRAGMA user_version").fetchone()[0] not in (0, 1, 2):
                raise ValueError("Unsupported draft database version; administrator migration required")
            connection.execute("CREATE TABLE IF NOT EXISTS drafts (id TEXT PRIMARY KEY, owner INTEGER NOT NULL, revision INTEGER NOT NULL, definition TEXT NOT NULL)")
            connection.execute("CREATE TABLE IF NOT EXISTS assets (draft TEXT NOT NULL REFERENCES drafts(id) ON DELETE CASCADE, path TEXT NOT NULL, data BLOB NOT NULL, PRIMARY KEY(draft,path))")
            connection.execute("CREATE TABLE IF NOT EXISTS directories (draft TEXT NOT NULL REFERENCES drafts(id) ON DELETE CASCADE, path TEXT NOT NULL, PRIMARY KEY(draft,path))")
            connection.execute("CREATE TABLE IF NOT EXISTS origins (draft TEXT PRIMARY KEY REFERENCES drafts(id) ON DELETE CASCADE, lab_id TEXT NOT NULL, digest TEXT NOT NULL)")
            connection.execute("PRAGMA user_version=2")

    @contextmanager
    def transaction(self):
        with self.lock:
            connection = sqlite3.connect(self.database, timeout=5)
            connection.row_factory = sqlite3.Row
            try:
                connection.execute("PRAGMA foreign_keys=ON")
                connection.execute("PRAGMA max_page_count=65536")
                connection.execute("BEGIN IMMEDIATE")
                yield connection
                connection.commit()
            except BaseException:
                connection.rollback()
                raise
            finally:
                connection.close()

    def _row(self, connection, identifier, uid, revision=None):
        if not isinstance(identifier, str) or not re.fullmatch(r"[a-f0-9]{32}", identifier):
            raise DraftNotFound("Draft not found")
        row = connection.execute("SELECT * FROM drafts WHERE id=?", (identifier,)).fetchone()
        if row is None or (uid != 0 and row["owner"] != uid):
            raise DraftNotFound("Draft not found")
        if revision is not None and (type(revision) is not int or revision != row["revision"]):
            raise DraftConflict("Draft changed; reload it before saving or publishing")
        return dict(row)

    def _snapshot(self, connection, row):
        assets = {item["path"]: bytes(item["data"]) for item in connection.execute("SELECT path,data FROM assets WHERE draft=? ORDER BY path", (row["id"],))}
        assets.update({item["path"]: None for item in connection.execute("SELECT path FROM directories WHERE draft=? ORDER BY path", (row["id"],))})
        row["assets"] = assets
        row["digest"] = digest(row["definition"], assets)
        origin = connection.execute("SELECT lab_id,digest FROM origins WHERE draft=?", (row["id"],)).fetchone()
        row["origin"] = dict(origin) if origin else None
        return row

    def create(self, lab_id, title, uid):
        if not isinstance(lab_id, str) or len(lab_id) > 64 or not re.fullmatch(r"[a-z][a-z0-9]*(-[a-z0-9]+)*", lab_id):
            raise ValueError("Invalid Lab ID")
        if not isinstance(title, str) or not title.strip() or len(title) > 128 or any(ord(char) < 32 for char in title):
            raise ValueError("Title requires 1-128 printable characters")
        definition = json.dumps({"apiVersion": "cyberlab.ptit/v1", "kind": "Lab", "metadata": {"id": lab_id, "name": title, "version": "1.0.0"}, "nodes": [], "networks": [], "terminals": []}, indent=2)
        with self.transaction() as connection:
            total = connection.execute("SELECT COUNT(*) FROM drafts").fetchone()[0]
            owned = connection.execute("SELECT COUNT(*) FROM drafts WHERE owner=?", (uid,)).fetchone()[0]
            if total >= 100 or owned >= 10:
                raise DraftLimit("Draft quota reached (10 per owner, 100 total); delete unused drafts")
            identifier = uuid4().hex
            connection.execute("INSERT INTO drafts VALUES (?,?,?,?)", (identifier, uid, 1, definition))
            return self._snapshot(connection, self._row(connection, identifier, uid))

    def clone(self, lab_id, title, definition, assets, uid, origin=None):
        definition_text(definition)
        if not isinstance(assets, (tuple, list)):
            raise ValueError("Draft assets must be a bounded sequence")
        check_package(definition, dict(assets))
        if not isinstance(lab_id, str) or len(lab_id) > 64 or not re.fullmatch(r"[a-z][a-z0-9]*(-[a-z0-9]+)*", lab_id):
            raise ValueError("Invalid Lab ID")
        if not isinstance(title, str) or not title.strip() or len(title) > 128 or any(ord(char) < 32 for char in title):
            raise ValueError("Title requires 1-128 printable characters")
        with self.transaction() as connection:
            total = connection.execute("SELECT COUNT(*) FROM drafts").fetchone()[0]
            owned = connection.execute("SELECT COUNT(*) FROM drafts WHERE owner=?", (uid,)).fetchone()[0]
            if total >= 100 or owned >= 10:
                raise DraftLimit("Draft quota reached (10 per owner, 100 total); delete unused drafts")
            identifier = uuid4().hex
            connection.execute("INSERT INTO drafts VALUES (?,?,?,?)", (identifier, uid, 1, definition))
            self._write_assets(connection, identifier, dict(assets))
            if origin:
                connection.execute("INSERT INTO origins VALUES (?,?,?)", (identifier, origin["lab_id"], origin["digest"]))
            return self._snapshot(connection, self._row(connection, identifier, uid))

    def _write_assets(self, connection, identifier, assets):
        connection.execute("DELETE FROM assets WHERE draft=?", (identifier,))
        connection.execute("DELETE FROM directories WHERE draft=?", (identifier,))
        connection.executemany("INSERT INTO assets VALUES (?,?,?)", [(identifier, path, data) for path, data in assets.items() if data is not None])
        connection.executemany("INSERT INTO directories VALUES (?,?)", [(identifier, path) for path, data in assets.items() if data is None])

    def set_origin(self, identifier, revision, uid, origin):
        with self.transaction() as connection:
            self._row(connection, identifier, uid, revision)
            connection.execute("INSERT OR REPLACE INTO origins VALUES (?,?,?)", (identifier, origin["lab_id"], origin["digest"]))

    def get(self, identifier, uid, revision=None):
        with self.transaction() as connection:
            return self._snapshot(connection, self._row(connection, identifier, uid, revision))

    def list(self, uid, include_definition=False):
        with self.transaction() as connection:
            fields = "id,owner,revision,definition" if include_definition else "id,owner,revision"
            rows = connection.execute(f"SELECT {fields} FROM drafts WHERE ?=0 OR owner=? ORDER BY id", (uid, uid)).fetchall()
            return [dict(row) for row in rows]

    def change(self, identifier, uid, revision, definition=None, additions=(), removals=()):
        with self.transaction() as connection:
            snapshot = self._snapshot(connection, self._row(connection, identifier, uid, revision))
            assets = snapshot["assets"]
            if definition is None:
                definition = snapshot["definition"]
            seen = set()
            for path, data in additions:
                if not isinstance(data, bytes):
                    raise ValueError("Uploaded assets must be files")
                if path in seen:
                    raise ValueError("Duplicate asset path in one update")
                seen.add(path)
                assets[path] = data
            for path in removals:
                if path != "assets":
                    asset_path(path)
                if path not in assets:
                    raise DraftNotFound("Asset not found")
                del assets[path]
            check_package(definition, assets)
            connection.execute("UPDATE drafts SET definition=?,revision=revision+1 WHERE id=?", (definition, identifier))
            self._write_assets(connection, identifier, assets)
            return self._snapshot(connection, self._row(connection, identifier, uid))

    def delete(self, identifier, uid, revision):
        with self.transaction() as connection:
            self._row(connection, identifier, uid, revision)
            connection.execute("DELETE FROM drafts WHERE id=?", (identifier,))
        return True
