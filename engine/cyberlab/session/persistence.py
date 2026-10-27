from contextlib import contextmanager
import base64
import json
import logging
import os
from pathlib import Path
import sqlite3
import stat
from threading import RLock
import yaml

from cyberlab.lab.loader import _LabYamlLoader, validate_lab
from cyberlab.lab.package import MAX_PACKAGE, check_package, load_snapshot
from cyberlab.parameters import resolve_parameters
from cyberlab.workspace import MAX_ARCHIVE
from . import Session, SessionState
from .reports import ReportStore, migrate_reports
from .quiz import QuizStore
from .lab_quiz import LabQuizStore, migrate_lab_quizzes

MAX_SAVED_SESSIONS_PER_USER = 10
MAX_TOTAL_SAVED_SESSIONS = 50
SCHEMA_VERSION = 7


class PracticeLimit(Exception):
    pass


def encode_package(package, definition):
    if package["definition"] != definition:
        raise ValueError("Checkpoint definition differs from its captured package")
    check_package(definition, package["assets"])
    return json.dumps({"version": 1, "assets": {
        path: base64.b64encode(data).decode("ascii") if data is not None else None
        for path, data in package["assets"].items()
    }}, sort_keys=True)


def decode_package(encoded, definition):
    if not isinstance(encoded, str) or len(encoded) > 4 * MAX_PACKAGE:
        raise ValueError("Saved Lab package exceeds its limit")
    document = json.loads(encoded)
    if not isinstance(document, dict) or document.get("version") != 1 or not isinstance(document.get("assets"), dict):
        raise ValueError("Unsupported saved Lab package")
    assets = {path: base64.b64decode(data, validate=True) if data is not None else None
              for path, data in document["assets"].items()}
    check_package(definition, assets)
    return {"definition": definition, "assets": assets}


class PracticeStore:
    def __init__(self, database_path: str | Path):
        self.database = str(database_path)
        self.lock = RLock()
        descriptor = os.open(self.database, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC, 0o600)
        try:
            status = os.fstat(descriptor)
            if not stat.S_ISREG(status.st_mode) or status.st_nlink != 1 or status.st_uid != os.geteuid():
                raise ValueError("Practice database must be an owned regular file without hardlinks")
            os.fchmod(descriptor, 0o600)
        finally:
            os.close(descriptor)
        with self.transaction() as conn:
            if conn.execute("PRAGMA user_version").fetchone()[0] not in range(SCHEMA_VERSION + 1):
                raise ValueError("Unsupported practice database version; administrator migration required")
            conn.execute("""
                CREATE TABLE IF NOT EXISTS saved_sessions (
                    id TEXT PRIMARY KEY,
                    owner INTEGER NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    checkpoint_at TEXT NOT NULL,
                    state TEXT NOT NULL,
                    definition TEXT NOT NULL,
                    package TEXT,
                    parameters TEXT NOT NULL DEFAULT '{}'
                )
            """)
            if "package" not in {column[1] for column in conn.execute("PRAGMA table_info(saved_sessions)")}:
                conn.execute("ALTER TABLE saved_sessions ADD COLUMN package TEXT")
            if "parameters" not in {column[1] for column in conn.execute("PRAGMA table_info(saved_sessions)")}:
                conn.execute("ALTER TABLE saved_sessions ADD COLUMN parameters TEXT NOT NULL DEFAULT '{}'")
            conn.execute("""
                CREATE TABLE IF NOT EXISTS saved_workspaces (
                    session_id TEXT NOT NULL REFERENCES saved_sessions(id) ON DELETE CASCADE,
                    node_id TEXT NOT NULL,
                    archive BLOB NOT NULL,
                    PRIMARY KEY (session_id, node_id)
                )
            """)
            migrate_reports(conn)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS quiz_attempts (
                    session_id TEXT PRIMARY KEY,
                    owner INTEGER NOT NULL,
                    created_at TEXT NOT NULL,
                    payload TEXT NOT NULL
                )
            """)
            migrate_lab_quizzes(conn)
            conn.execute(f"PRAGMA user_version={SCHEMA_VERSION}")
        self.reports = ReportStore(self.transaction)
        self.quizzes = QuizStore(self.transaction)
        self.lab_quizzes = LabQuizStore(self.transaction)

    @contextmanager
    def transaction(self):
        with self.lock:
            conn = sqlite3.connect(self.database, timeout=5)
            conn.row_factory = sqlite3.Row
            try:
                conn.execute("PRAGMA foreign_keys=ON")
                conn.execute("BEGIN IMMEDIATE")
                yield conn
                conn.commit()
            except BaseException:
                conn.rollback()
                raise
            finally:
                conn.close()

    def save_checkpoint(self, session_id: str, owner: int, created_at: str, updated_at: str,
                        checkpoint_at: str, state: str, definition: str, workspaces: dict[str, bytes], package: dict,
                        parameters: dict | None = None, *, check_report: dict | None = None):
        encoded = encode_package(package, definition)
        for node_id, data in workspaces.items():
            if not isinstance(data, bytes) or len(data) > MAX_ARCHIVE:
                raise ValueError(f"Workspace archive for node {node_id} exceeds size limit")
        with self.transaction() as conn:
            count = conn.execute("SELECT COUNT(*) FROM saved_sessions WHERE owner=?", (owner,)).fetchone()[0]
            existing = conn.execute("SELECT id FROM saved_sessions WHERE id=?", (session_id,)).fetchone()
            if not existing and count >= MAX_SAVED_SESSIONS_PER_USER:
                raise PracticeLimit("Saved practice quota reached (10 per user); discard an old checkpoint to free space")
            total = conn.execute("SELECT COUNT(*) FROM saved_sessions").fetchone()[0]
            if not existing and total >= MAX_TOTAL_SAVED_SESSIONS:
                raise PracticeLimit("Total saved practice limit reached; discard an old checkpoint to free space")
            conn.execute("""
                INSERT OR REPLACE INTO saved_sessions (id, owner, created_at, updated_at, checkpoint_at, state, definition, package, parameters)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (session_id, owner, created_at, updated_at, checkpoint_at, state, definition, encoded,
                   json.dumps(parameters or {}, ensure_ascii=True, sort_keys=True)))
            conn.execute("DELETE FROM saved_workspaces WHERE session_id=?", (session_id,))
            conn.executemany("""
                INSERT INTO saved_workspaces (session_id, node_id, archive)
                VALUES (?, ?, ?)
            """, [(session_id, node_id, archive) for node_id, archive in workspaces.items()])
            if check_report is not None:
                self.reports.save(check_report["id"], session_id, owner, check_report["created_at"],
                                  json.dumps(check_report, ensure_ascii=True, separators=(",", ":")),
                                  connection=conn)

    def load_sessions(self) -> list[tuple[Session, dict | None]]:
        """Restore captured packages; never substitute the current catalog for missing assets."""
        with self.transaction() as conn:
            rows = conn.execute("SELECT * FROM saved_sessions").fetchall()
            results = []
            for row in rows:
                try:
                    document = yaml.load(row["definition"], Loader=_LabYamlLoader)
                    lab = validate_lab(document)
                    package = None
                    error = ""
                    parameters = json.loads(row["parameters"] or "{}") if "parameters" in row.keys() else {}
                    if not isinstance(parameters, dict):
                        raise ValueError("Saved Session parameters are invalid")
                    if row["package"] is not None:
                        try:
                            package = decode_package(row["package"], row["definition"])
                            lab = load_snapshot(package)
                        except Exception:
                            package = None
                            error = "Saved Lab package is invalid; resume/reset is unavailable. The checkpoint is retained."
                    elif lab.documentation is not None or any(node.files for node in lab.nodes):
                        error = "Legacy checkpoint has no Lab package snapshot; resume/reset is unavailable. The checkpoint is retained."
                    else:
                        package = {"definition": row["definition"], "assets": {}}
                    lab, _ = resolve_parameters(lab, parameters, row["id"])
                    session = Session(
                        id=row["id"],
                        lab=lab,
                        owner_uid=row["owner"],
                        state=SessionState.SUSPENDED,
                        created_at=row["created_at"],
                        updated_at=row["updated_at"],
                        checkpoint_at=row["checkpoint_at"],
                        error=error,
                        parameters=tuple((str(key), str(value)) for key, value in sorted(parameters.items())),
                    )
                    results.append((session, package))
                except Exception:
                    logging.warning("Cannot load saved Session %s; checkpoint retained for administrator recovery", row["id"])
                    continue
            return results

    def get_checkpoint(self, session_id: str) -> dict | None:
        with self.transaction() as conn:
            row = conn.execute("SELECT * FROM saved_sessions WHERE id=?", (session_id,)).fetchone()
            if not row:
                return None
            workspaces = {
                w["node_id"]: bytes(w["archive"])
                for w in conn.execute("SELECT node_id, archive FROM saved_workspaces WHERE session_id=?", (session_id,)).fetchall()
            }
            return {
                "id": row["id"],
                "owner": row["owner"],
                "checkpoint_at": row["checkpoint_at"],
                "definition": row["definition"],
                "state": row["state"],
                "parameters": json.loads(row["parameters"] or "{}") if "parameters" in row.keys() else {},
                "workspaces": workspaces,
            }

    def delete_checkpoint(self, session_id: str) -> bool:
        with self.transaction() as conn:
            conn.execute("DELETE FROM saved_sessions WHERE id=?", (session_id,))
            return True

    def save_check_report(self, report_id, session_id, owner, created_at, payload):
        return self.reports.save(report_id, session_id, owner, created_at, payload)

    def list_check_reports(self, owner, session_id=None):
        return self.reports.list(owner, session_id)

    def get_check_report(self, report_id, owner):
        return self.reports.get(report_id, owner)

    def delete_check_report(self, report_id, owner):
        return self.reports.delete(report_id, owner)

    def save_quiz_attempt(self, session_id, owner, created_at, payload):
        return self.quizzes.save(session_id, owner, created_at, payload)

    def get_quiz_attempt(self, session_id, owner):
        return self.quizzes.get(session_id, owner)

    def delete_quiz_attempt(self, session_id, owner):
        return self.quizzes.delete(session_id, owner)

    def discard_unsaved_quizzes(self):
        self.quizzes.discard_unsaved()
