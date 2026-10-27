import json

MAX_QUIZ_PAYLOAD = 256 * 1024
MAX_USER_ATTEMPTS = 100
MAX_TOTAL_ATTEMPTS = 250
MAX_USER_BYTES = 8 * 1024 * 1024
MAX_TOTAL_BYTES = 32 * 1024 * 1024


class QuizLimit(Exception):
    pass


class QuizStore:
    def __init__(self, transaction):
        self.transaction = transaction

    def save(self, session_id, owner, created_at, payload):
        if (not isinstance(session_id, str) or not session_id or len(session_id) > 64
                or type(owner) is not int or owner < 0 or owner >= 2 ** 32
                or not isinstance(created_at, str) or not created_at):
            raise ValueError("Invalid quiz attempt metadata")
        if not isinstance(payload, str) or len(payload.encode("utf-8")) > MAX_QUIZ_PAYLOAD:
            raise QuizLimit("Quiz attempt exceeds its size limit")
        document = json.loads(payload)
        if not isinstance(document, dict) or document.get("session_id") != session_id:
            raise ValueError("Quiz attempt metadata does not match its contents")
        with self.transaction() as connection:
            existing = connection.execute(
                "SELECT owner FROM quiz_attempts WHERE session_id=?", (session_id,)
            ).fetchone()
            if existing is not None and existing["owner"] != owner:
                raise ValueError("Quiz attempt is owned by another user")
            size = len(payload.encode("utf-8"))
            user_totals = connection.execute(
                "SELECT count(*), coalesce(sum(length(CAST(payload AS BLOB))), 0) FROM quiz_attempts "
                "WHERE owner=? AND session_id!=?", (owner, session_id),
            ).fetchone()
            totals = connection.execute(
                "SELECT count(*), coalesce(sum(length(CAST(payload AS BLOB))), 0) FROM quiz_attempts "
                "WHERE session_id!=?", (session_id,),
            ).fetchone()
            if user_totals[0] >= MAX_USER_ATTEMPTS or user_totals[1] + size > MAX_USER_BYTES:
                raise QuizLimit("Quiz attempts exceed the user's storage quota")
            if totals[0] >= MAX_TOTAL_ATTEMPTS or totals[1] + size > MAX_TOTAL_BYTES:
                raise QuizLimit("Quiz attempt storage is full")
            connection.execute(
                "INSERT OR REPLACE INTO quiz_attempts (session_id, owner, created_at, payload) VALUES (?, ?, ?, ?)",
                (session_id, owner, created_at, payload),
            )

    def get(self, session_id, owner):
        with self.transaction() as connection:
            row = connection.execute(
                "SELECT payload FROM quiz_attempts WHERE session_id=? AND (?=0 OR owner=?)",
                (session_id, owner, owner),
            ).fetchone()
            return json.loads(row["payload"]) if row else None

    def delete(self, session_id, owner):
        with self.transaction() as connection:
            return connection.execute(
                "DELETE FROM quiz_attempts WHERE session_id=? AND (?=0 OR owner=?)",
                (session_id, owner, owner),
            ).rowcount == 1

    def discard_unsaved(self):
        with self.transaction() as connection:
            connection.execute(
                "DELETE FROM quiz_attempts WHERE NOT EXISTS "
                "(SELECT 1 FROM saved_sessions WHERE saved_sessions.id=quiz_attempts.session_id)"
            )
