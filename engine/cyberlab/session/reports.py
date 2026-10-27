import json
from contextlib import nullcontext

MAX_REPORT_BYTES = 8 * 1024 * 1024
MAX_SESSION_REPORTS = 5
MAX_USER_REPORTS = 50
MAX_TOTAL_REPORTS = 250
MAX_USER_BYTES = 32 * 1024 * 1024
MAX_TOTAL_BYTES = 128 * 1024 * 1024


class ReportLimit(Exception):
    pass


def report_summary(payload):
    if not isinstance(payload, str) or len(payload.encode("utf-8")) > MAX_REPORT_BYTES:
        raise ReportLimit("Checkwork report exceeds 8 MiB")
    report = json.loads(payload)
    if not isinstance(report, dict) or report.get("status") not in {"PASS", "FAIL", "ERROR", "NO_CRITERIA"}:
        raise ValueError("Invalid Checkwork report")
    return {"lab_id": report.get("lab_id", ""), "lab_name": report.get("lab_name", ""),
            "lab_version": report.get("lab_version", ""), "status": report["status"],
            "submission_ready": report.get("submission_ready", False),
            "result_count": len(report.get("results", [])), "goal_count": len(report.get("goals", []))}


def migrate_reports(connection):
    connection.execute("""
        CREATE TABLE IF NOT EXISTS check_reports (
            id TEXT PRIMARY KEY, session_id TEXT NOT NULL, owner INTEGER NOT NULL,
            created_at TEXT NOT NULL, payload TEXT NOT NULL, summary TEXT NOT NULL
        )
    """)
    if "summary" not in {row[1] for row in connection.execute("PRAGMA table_info(check_reports)")}:
        connection.execute("ALTER TABLE check_reports ADD COLUMN summary TEXT NOT NULL DEFAULT '{}'")
        for row in connection.execute("SELECT id, payload FROM check_reports").fetchall():
            summary = json.dumps(report_summary(row["payload"]), ensure_ascii=True)
            connection.execute("UPDATE check_reports SET summary=? WHERE id=?", (summary, row["id"]))
    connection.execute("CREATE INDEX IF NOT EXISTS check_reports_owner_created ON check_reports(owner, created_at)")
    connection.execute("CREATE INDEX IF NOT EXISTS check_reports_session_created ON check_reports(session_id, created_at)")


class ReportStore:
    def __init__(self, transaction):
        self.transaction = transaction

    def save(self, report_id, session_id, owner, created_at, payload, *, connection=None):
        if (not all(isinstance(value, str) and 0 < len(value) <= 64 for value in (report_id, session_id, created_at))
                or type(owner) is not int or not 0 <= owner < 2 ** 32):
            raise ValueError("Invalid Checkwork report metadata")
        summary = json.dumps(report_summary(payload), ensure_ascii=True)
        report = json.loads(payload)
        if any(report.get(key) != value for key, value in (
                ("id", report_id), ("session_id", session_id), ("created_at", created_at))):
            raise ValueError("Checkwork report metadata does not match its contents")
        size = len(payload.encode("utf-8"))
        with (self.transaction() if connection is None else nullcontext(connection)) as connection:
            if connection.execute("SELECT id FROM check_reports WHERE id=?", (report_id,)).fetchone():
                raise ValueError("Checkwork reports are immutable")
            rows = list(connection.execute(
                "SELECT id, session_id, length(CAST(payload AS BLOB)) AS size FROM check_reports "
                "WHERE owner=? ORDER BY created_at, id", (owner,)))
            removed = []
            same_session = [row for row in rows if row["session_id"] == session_id]
            for row in same_session[:max(0, len(same_session) + 1 - MAX_SESSION_REPORTS)]:
                rows.remove(row)
                removed.append(row["id"])
            while rows and (len(rows) >= MAX_USER_REPORTS or size + sum(row["size"] for row in rows) > MAX_USER_BYTES):
                removed.append(rows.pop(0)["id"])
            if size > MAX_USER_BYTES:
                raise ReportLimit("Report exceeds the user's evidence quota")
            connection.executemany("DELETE FROM check_reports WHERE id=? AND owner=?", [(identifier, owner) for identifier in removed])
            totals = connection.execute("SELECT count(*), coalesce(sum(length(CAST(payload AS BLOB))), 0) FROM check_reports").fetchone()
            if totals[0] >= MAX_TOTAL_REPORTS or totals[1] + size > MAX_TOTAL_BYTES:
                raise ReportLimit("Checkwork storage is full; delete an owned report before retrying")
            connection.execute("INSERT INTO check_reports (id, session_id, owner, created_at, payload, summary) VALUES (?, ?, ?, ?, ?, ?)",
                               (report_id, session_id, owner, created_at, payload, summary))

    def list(self, owner, session_id=None):
        with self.transaction() as connection:
            rows = connection.execute(
                "SELECT id, session_id, owner, created_at, summary FROM check_reports "
                "WHERE (?=0 OR owner=?) AND (? IS NULL OR session_id=?) ORDER BY created_at DESC, id DESC",
                (owner, owner, session_id, session_id))
            return [{"id": row["id"], "session_id": row["session_id"], "owner": row["owner"],
                     "created_at": row["created_at"], **json.loads(row["summary"])} for row in rows]

    def get(self, report_id, owner):
        with self.transaction() as connection:
            row = connection.execute("SELECT owner, payload FROM check_reports WHERE id=? AND (?=0 OR owner=?)",
                                     (report_id, owner, owner)).fetchone()
            return {**json.loads(row["payload"]), "owner": row["owner"]} if row else None

    def delete(self, report_id, owner):
        with self.transaction() as connection:
            return connection.execute("DELETE FROM check_reports WHERE id=? AND (?=0 OR owner=?)",
                                      (report_id, owner, owner)).rowcount == 1
