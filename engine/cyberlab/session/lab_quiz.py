import json
import re

from .quiz import QuizLimit

MAX_PAYLOAD = 256 * 1024
MAX_USER_ATTEMPTS = 100
MAX_TOTAL_ATTEMPTS = 250
MAX_USER_BYTES = 8 * 1024 * 1024
MAX_TOTAL_BYTES = 32 * 1024 * 1024


def migrate_lab_quizzes(connection):
    connection.execute("""
        CREATE TABLE IF NOT EXISTS lab_quiz_attempts (
            lab_id TEXT NOT NULL,
            owner INTEGER NOT NULL,
            digest TEXT NOT NULL,
            payload TEXT NOT NULL,
            PRIMARY KEY (lab_id, owner)
        )
    """)


class LabQuizStore:
    def __init__(self, transaction):
        self.transaction = transaction

    def save(self, lab_id, owner, digest, report):
        if (not isinstance(lab_id, str) or len(lab_id) > 64
                or not re.fullmatch(r"[a-z][a-z0-9]*(?:-[a-z0-9]+)*", lab_id)
                or type(owner) is not int or not 0 <= owner < 2 ** 32
                or not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest)):
            raise ValueError("Invalid Lab quiz attempt identity")
        if (not isinstance(report, dict) or report.get("format") != "cyberlab-lab-quiz/v1"
                or report.get("lab_id") != lab_id or report.get("lab_digest") != digest):
            raise ValueError("Lab quiz attempt identity does not match its contents")
        payload = json.dumps(report, ensure_ascii=True, separators=(",", ":"))
        size = len(payload.encode("utf-8"))
        if size > MAX_PAYLOAD:
            raise QuizLimit("Lab quiz attempt exceeds its size limit")
        with self.transaction() as connection:
            user_totals = connection.execute(
                "SELECT count(*), coalesce(sum(length(CAST(payload AS BLOB))), 0) FROM lab_quiz_attempts "
                "WHERE owner=? AND lab_id!=?", (owner, lab_id),
            ).fetchone()
            totals = connection.execute(
                "SELECT count(*), coalesce(sum(length(CAST(payload AS BLOB))), 0) FROM lab_quiz_attempts "
                "WHERE NOT (lab_id=? AND owner=?)", (lab_id, owner),
            ).fetchone()
            if user_totals[0] >= MAX_USER_ATTEMPTS or user_totals[1] + size > MAX_USER_BYTES:
                raise QuizLimit("Lab quiz attempts exceed the user's storage quota")
            if totals[0] >= MAX_TOTAL_ATTEMPTS or totals[1] + size > MAX_TOTAL_BYTES:
                raise QuizLimit("Lab quiz attempt storage is full")
            connection.execute(
                "INSERT OR REPLACE INTO lab_quiz_attempts (lab_id, owner, digest, payload) VALUES (?, ?, ?, ?)",
                (lab_id, owner, digest, payload),
            )

    def get(self, lab_id, owner, digest):
        with self.transaction() as connection:
            row = connection.execute(
                "SELECT payload FROM lab_quiz_attempts WHERE lab_id=? AND owner=? AND digest=?",
                (lab_id, owner, digest),
            ).fetchone()
            return json.loads(row["payload"]) if row else None

    def delete(self, lab_id, owner):
        with self.transaction() as connection:
            return connection.execute(
                "DELETE FROM lab_quiz_attempts WHERE lab_id=? AND owner=?", (lab_id, owner),
            ).rowcount == 1

    def delete_lab(self, lab_id):
        with self.transaction() as connection:
            connection.execute("DELETE FROM lab_quiz_attempts WHERE lab_id=?", (lab_id,))
