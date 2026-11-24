"""Daemon-side editing authorization; this does not encrypt published labs."""
from hashlib import scrypt
from hmac import compare_digest
import json
import re
import secrets
import time
from uuid import uuid4


class EditLocked(PermissionError):
    def __init__(self, kind, identifier):
        super().__init__(json.dumps({"kind": kind, "id": identifier,
                                    "message": "Bài đã khóa chỉnh sửa. Hãy nhập mật khẩu."}))


class EditPassword(PermissionError):
    pass


def validate_verifier(value):
    if (not isinstance(value, dict) or set(value) != {"version", "algorithm", "salt", "hash"}
            or type(value["version"]) is not int or value["version"] != 1
            or value["algorithm"] != "scrypt-131072-8-1"
            or not isinstance(value["salt"], str) or not re.fullmatch(r"[0-9a-f]{32}", value["salt"])
            or not isinstance(value["hash"], str) or not re.fullmatch(r"[0-9a-f]{64}", value["hash"])):
        raise ValueError("Invalid editing protection metadata")
    return value


def password_bytes(password):
    if not isinstance(password, str) or not 1 <= len(password.encode("utf-8")) <= 1024:
        raise EditPassword("Mật khẩu cần từ 1 đến 1024 byte.")
    return password.encode("utf-8")


def password_hash(password, salt):
    return scrypt(password_bytes(password), salt=bytes.fromhex(salt), n=131072,
                  r=8, p=1, dklen=32, maxmem=192 * 1024 * 1024).hex()


class EditProtection:
    def __init__(self, store):
        self.store = store
        self.grants = {}
        self.failures = {}
        with store.transaction() as connection:
            connection.execute("CREATE TABLE IF NOT EXISTS edit_families (id TEXT PRIMARY KEY, verifier TEXT NOT NULL, version INTEGER NOT NULL)")
            connection.execute("CREATE TABLE IF NOT EXISTS edit_links (resource TEXT PRIMARY KEY, family TEXT NOT NULL REFERENCES edit_families(id))")

    def key(self, kind, identifier):
        pattern = r"[a-f0-9]{32}" if kind == "draft" else r"[a-z][a-z0-9]*(-[a-z0-9]+)*"
        if kind not in {"lab", "draft"} or not isinstance(identifier, str) or len(identifier) > 64 or not re.fullmatch(pattern, identifier):
            raise ValueError("Invalid editing resource")
        return kind + ":" + identifier

    def record(self, kind, identifier, uid):
        resource = self.key(kind, identifier)
        origin = None
        if kind == "draft":
            origin = self.store.get(identifier, uid).get("origin")
        with self.store.transaction() as connection:
            row = connection.execute("SELECT f.* FROM edit_links l JOIN edit_families f ON f.id=l.family WHERE l.resource=?", (resource,)).fetchone()
            if row is None and origin:
                row = connection.execute("SELECT f.* FROM edit_links l JOIN edit_families f ON f.id=l.family WHERE l.resource=?", (self.key("lab", origin["lab_id"]),)).fetchone()
            return dict(row) if row else None

    def protected(self, kind, identifier, uid=0):
        record = self.record(kind, identifier, uid)
        return bool(record and json.loads(record["verifier"]))

    def verifier(self, kind, identifier, uid):
        record = self.record(kind, identifier, uid)
        return json.loads(record["verifier"]) if record else None

    def family_id(self, kind, identifier, uid=0):
        record = self.record(kind, identifier, uid)
        return record["id"] if record else None

    def link(self, kind, identifier, family):
        with self.store.transaction() as connection:
            resource = self.key(kind, identifier)
            if family:
                connection.execute("INSERT OR REPLACE INTO edit_links VALUES (?,?)", (resource, family))
            else:
                if kind == "lab":
                    connection.execute("INSERT OR IGNORE INTO edit_links SELECT 'draft:' || o.draft,l.family FROM origins o JOIN edit_links l ON l.resource=? WHERE o.lab_id=?", (resource, identifier))
                old = connection.execute("SELECT family FROM edit_links WHERE resource=?", (resource,)).fetchone()
                connection.execute("DELETE FROM edit_links WHERE resource=?", (resource,))
                if old:
                    connection.execute("DELETE FROM edit_families WHERE id=? AND NOT EXISTS (SELECT 1 FROM edit_links WHERE family=?)", (old[0], old[0]))

    def install(self, kind, identifier, verifier):
        validate_verifier(verifier)
        family = uuid4().hex
        with self.store.transaction() as connection:
            connection.execute("INSERT INTO edit_families VALUES (?,?,1)", (family, json.dumps(verifier)))
            connection.execute("INSERT OR REPLACE INTO edit_links VALUES (?,?)", (self.key(kind, identifier), family))
        return family

    def inherit(self, source_kind, source_id, target_kind, target_id, uid):
        record = self.record(source_kind, source_id, uid)
        self.link(target_kind, target_id, record["id"] if record else None)

    def require(self, kind, identifier, uid, token=""):
        record = self.record(kind, identifier, uid)
        if not record or not json.loads(record["verifier"]):
            return
        grant = self.grants.get(token)
        if (not grant or grant[0] != uid or grant[1] != record["id"]
                or grant[2] != record["version"] or grant[3] <= time.monotonic()):
            raise EditLocked(kind, identifier)

    def grant(self, record, uid):
        now = time.monotonic()
        self.grants = {token: grant for token, grant in self.grants.items() if grant[3] > now}
        if len(self.grants) >= 256:
            self.grants.pop(next(iter(self.grants)))
        token = secrets.token_urlsafe(32)
        self.grants[token] = (uid, record["id"], record["version"], now + 12 * 60 * 60)
        return token

    def verify(self, record, password, uid):
        verifier = json.loads(record["verifier"]) if record else None
        if not verifier:
            return
        key = (uid, record["id"])
        now = time.monotonic()
        self.failures = {key: value for key, value in self.failures.items() if now - value[1] < 300}
        count, attempted = self.failures.get(key, (0, 0))
        if count >= 5 and now - attempted < 30:
            raise EditPassword("Nhập sai quá nhiều lần. Vui lòng thử lại sau 30 giây.")
        validate_verifier(verifier)
        if not compare_digest(password_hash(password, verifier["salt"]), verifier["hash"]):
            self.failures[key] = (count + 1 if now - attempted < 30 else 1, now)
            raise EditPassword("Mật khẩu chỉnh sửa không đúng.")
        self.failures.pop(key, None)

    def unlock(self, kind, identifier, password, uid):
        record = self.record(kind, identifier, uid)
        self.verify(record, password, uid)
        protected = bool(record and json.loads(record["verifier"]))
        return {"token": self.grant(record, uid) if protected else "", "edit_protected": protected}

    def change(self, kind, identifier, current, password, uid):
        record = self.record(kind, identifier, uid)
        self.verify(record, current, uid)
        verifier = None
        if password:
            salt = secrets.token_hex(16)
            verifier = {"version": 1, "algorithm": "scrypt-131072-8-1", "salt": salt,
                        "hash": password_hash(password, salt)}
        if record:
            with self.store.transaction() as connection:
                connection.execute("UPDATE edit_families SET verifier=?,version=version+1 WHERE id=?", (json.dumps(verifier), record["id"]))
        elif verifier:
            self.install(kind, identifier, verifier)
        if kind == "draft":
            origin = self.store.get(identifier, uid).get("origin")
            if origin:
                self.inherit(kind, identifier, "lab", origin["lab_id"], uid)
        record = self.record(kind, identifier, uid)
        return {"token": self.grant(record, uid) if verifier else "", "edit_protected": bool(verifier)}

    def revoke(self, token, uid):
        grant = self.grants.get(token)
        if grant and grant[0] == uid:
            self.grants.pop(token, None)
        return True
