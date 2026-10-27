from datetime import datetime
from hashlib import sha256
import re

from cyberlab.archives import json_object, read_zip
from cyberlab.assessment_checks import combined_status
from cyberlab.submission import MAX_SUBMISSION_BYTES
from cyberlab.workspace import relative_path

MAX_BATCH_ITEMS = 32
MAX_BATCH_BYTES = 32 * 1024 * 1024
MAX_REPORT_BYTES = 8 * 1024 * 1024
MAX_MANIFEST_BYTES = 256 * 1024
MAX_QUIZ_BYTES = 256 * 1024


class SubmissionReviewError(ValueError):
    pass


def _text(value, limit=64):
    if not isinstance(value, str) or not 0 < len(value) <= limit or not value.isprintable():
        raise ValueError("Invalid submission identity or text")
    return value


def _timestamp(value):
    if datetime.fromisoformat(_text(value)).tzinfo is None:
        raise ValueError("Submission timestamps need a timezone")


def _criteria(report, key, limit):
    entries = report.get(key)
    if not isinstance(entries, list) or len(entries) > limit:
        raise ValueError("Invalid report criteria")
    identifiers = set()
    for item in entries:
        if not isinstance(item, dict) or item.get("status") not in ("PASS", "FAIL", "ERROR"):
            raise ValueError("Invalid criterion status")
        identifier = _text(item.get("id"))
        if identifier in identifiers:
            raise ValueError("Duplicate criterion ID")
        identifiers.add(identifier)
    return entries


def _evidence(report, manifest, entries):
    declared = manifest.get("evidence")
    artifacts = report.get("artifacts")
    if not isinstance(declared, list) or len(declared) > 256:
        raise ValueError("Invalid evidence manifest")
    if not isinstance(artifacts, list) or len(artifacts) > 64:
        raise ValueError("Invalid report artifacts")
    expected = {}
    count = 0
    identifiers = set()
    ready = True
    for artifact in artifacts:
        if not isinstance(artifact, dict):
            raise ValueError("Invalid artifact")
        identifier = _text(artifact.get("id"))
        if identifier in identifiers:
            raise ValueError("Duplicate artifact ID")
        identifiers.add(identifier)
        node = relative_path(_text(artifact.get("node")))
        if "/" in node or type(artifact.get("required")) is not bool:
            raise ValueError("Invalid artifact node or requirement")
        root = relative_path(artifact.get("path"), root=True)
        status = artifact.get("status")
        if status not in ("COLLECTED", "MISSING", "OPTIONAL_MISSING", "ERROR"):
            raise ValueError("Invalid artifact status")
        if status == "OPTIONAL_MISSING" and artifact["required"]:
            raise ValueError("Required artifact reported as optional")
        ready = ready and status in ("COLLECTED", "OPTIONAL_MISSING")
        files = artifact.get("entries", [])
        if not isinstance(files, list) or (status != "COLLECTED" and files):
            raise ValueError("Artifact entries do not match capture status")
        if status == "COLLECTED" and not files:
            raise ValueError("Collected artifact has no entries")
        count += len(files)
        if count > 256:
            raise ValueError("Too many evidence entries")
        for item in files:
            if not isinstance(item, dict) or item.get("kind") not in ("file", "directory"):
                raise ValueError("Invalid evidence entry")
            path = relative_path(item.get("path"))
            if root != "." and path != root and not path.startswith(root + "/"):
                raise ValueError("Evidence is outside its declared artifact")
            member = "artifacts/" + node + "/" + path
            if member not in entries or "content_b64" in item:
                raise ValueError("Missing or unexpected embedded evidence")
            data = entries[member]
            directory = item["kind"] == "directory"
            if directory != (data is None):
                raise ValueError("Evidence type does not match archive")
            size = 0 if directory else len(data)
            checksum = sha256(b"" if directory else data).hexdigest()
            if type(item.get("size")) is not int or item["size"] != size:
                raise ValueError("Evidence size does not match report")
            if not directory and item.get("sha256") != checksum:
                raise ValueError("Evidence hash does not match report")
            name = member + "/" if directory else member
            expected[name] = {"path": name, "size": size, "sha256": checksum}
    if sum(item["size"] for item in expected.values()) > 4 * 1024 * 1024:
        raise ValueError("Evidence exceeds 4 MiB")
    actual = {}
    for item in declared:
        if (not isinstance(item, dict) or not isinstance(item.get("path"), str)
                or type(item.get("size")) is not int or item["path"] in actual):
            raise ValueError("Invalid or duplicate evidence metadata")
        actual[item["path"]] = item
    if actual != expected:
        raise ValueError("Evidence manifest does not match captured report")
    if type(report.get("submission_ready")) is not bool or report["submission_ready"] != ready:
        raise ValueError("Report readiness does not match evidence")
    return {path.rstrip("/") for path in expected}


def _quiz(report, entries):
    if "quiz" not in report and "quiz.json" not in entries:
        return None
    quiz = json_object(entries.get("quiz.json"), MAX_QUIZ_BYTES)
    if (quiz != report.get("quiz") or quiz.get("format") != "cyberlab-quiz/v1"
            or any(quiz.get(key) != report[key] for key in ("session_id", "lab_id", "lab_version"))):
        raise ValueError("Quiz does not match captured report")
    _timestamp(quiz.get("created_at"))
    questions = quiz.get("questions")
    answers = quiz.get("answers")
    if not isinstance(questions, list) or not 1 <= len(questions) <= 64 or not isinstance(answers, dict):
        raise ValueError("Invalid quiz questions or answers")
    if len(answers) > 64 or any(type(answer) is not int or not 0 <= answer < 8 for answer in answers.values()):
        raise ValueError("Invalid quiz option index")
    identifiers = set()
    answerable = set()
    for item in questions:
        if not isinstance(item, dict) or item.get("status") not in (
                "CORRECT", "INCORRECT", "UNANSWERED", "UNASSESSED", "PREFACE", "SKIPPED"):
            raise ValueError("Invalid quiz question status")
        identifier = _text(item.get("id"))
        selected = item.get("selected")
        if (identifier in identifiers or selected != answers.get(identifier)
                or (selected is not None and (type(selected) is not int or not 0 <= selected < 8))):
            raise ValueError("Invalid quiz answer")
        if item.get("type", "choice") != "preface":
            answerable.add(identifier)
        if (item["status"] in ("UNANSWERED", "PREFACE") and selected is not None
                or item["status"] in ("CORRECT", "INCORRECT") and selected is None
                or item["status"] == "PREFACE" and item.get("type") != "preface"):
            raise ValueError("Quiz answer does not match status")
        identifiers.add(identifier)
    if set(answers) - answerable:
        raise ValueError("Unknown quiz answer")
    correct = sum(item["status"] == "CORRECT" for item in questions)
    graded = sum(item["status"] in ("CORRECT", "INCORRECT", "UNANSWERED") for item in questions)
    if (type(quiz.get("correct")) is not int or type(quiz.get("graded")) is not int
            or quiz["correct"] != correct or quiz["graded"] != graded
            or type(quiz.get("passed")) is not bool or quiz["passed"] != (graded > 0 and correct == graded)):
        raise ValueError("Quiz totals do not match questions")
    return {"passed": quiz["passed"], "correct": correct, "graded": graded}


def review_submission(data, filename="submission.zip"):
    try:
        _text(filename, 256)
        entries = read_zip(data, max_archive=MAX_SUBMISSION_BYTES, max_entries=261,
                           max_content=16 * 1024 * 1024)
        manifest = json_object(entries.get("manifest.json"), MAX_MANIFEST_BYTES)
        report = json_object(entries.get("checkwork.json"), MAX_REPORT_BYTES)
        if manifest.get("format") != "cyberlab-submission/v1" or report.get("format") != "cyberlab-checkwork/v1":
            raise ValueError("Unsupported submission format")
        for key in ("id", "session_id", "lab_id", "lab_name", "lab_version", "lab_digest", "created_at", "status"):
            _text(report.get(key), MAX_REPORT_BYTES if key == "lab_name" else 64)
            if manifest.get(key) != report[key]:
                raise ValueError("Submission identity does not match report")
        if not re.fullmatch(r"[a-f0-9]{64}", report["lab_digest"]):
            raise ValueError("Invalid Lab digest")
        _timestamp(report["created_at"])
        goals = _criteria(report, "goals", 32)
        results = _criteria(report, "results", 64)
        if report["status"] != combined_status([item["status"] for item in (goals or results)]):
            raise ValueError("Report status does not match its criteria")
        paths = _evidence(report, manifest, entries)
        if (type(manifest.get("submission_ready")) is not bool
                or manifest["submission_ready"] != report["submission_ready"]):
            raise ValueError("Manifest readiness does not match report")
        allowed = {"manifest.json", "checkwork.json", "report.html", "quiz.json", "instructions.md"}
        if set(entries) - allowed != paths or not isinstance(entries.get("report.html"), bytes):
            raise ValueError("Submission contains undeclared, missing or invalid files")
        if any(entries[key] is None for key in allowed & set(entries)):
            raise ValueError("Submission metadata must be regular files")
        quiz = _quiz(report, entries)
        return {
            "filename": filename, "valid": True, "authenticated": False,
            "report_id": report["id"],
            **{key: report[key] for key in ("session_id", "lab_id", "lab_version", "lab_digest", "created_at", "status", "submission_ready")},
            "lab_name": report["lab_name"][:512],
            "goals": {"passed": sum(item["status"] == "PASS" for item in goals), "total": len(goals)},
            "results": {"passed": sum(item["status"] == "PASS" for item in results), "total": len(results)},
            "quiz": quiz, "evidence_count": len(paths),
        }
    except (ValueError, TypeError, KeyError, RecursionError) as error:
        raise SubmissionReviewError(str(error)) from None


def review_submissions(packages):
    if not isinstance(packages, (list, tuple)) or not 1 <= len(packages) <= MAX_BATCH_ITEMS:
        raise SubmissionReviewError("Select between 1 and 32 submissions")
    total = 0
    for item in packages:
        if (not isinstance(item, (list, tuple)) or len(item) != 2
                or not isinstance(item[0], str) or not 1 <= len(item[0]) <= 256
                or not isinstance(item[1], bytes) or len(item[1]) > MAX_SUBMISSION_BYTES):
            raise SubmissionReviewError("Invalid submission input")
        total += len(item[1])
    if total > MAX_BATCH_BYTES:
        raise SubmissionReviewError("Review batch exceeds 32 MiB")
    items = []
    seen = set()
    for filename, data in packages:
        try:
            item = review_submission(data, filename)
            if item["report_id"] in seen:
                raise SubmissionReviewError("Duplicate report ID in review batch")
            seen.add(item["report_id"])
        except SubmissionReviewError as error:
            item = {"filename": filename, "valid": False, "error": str(error)}
        items.append(item)
    valid = [item for item in items if item["valid"]]
    return {"format": "cyberlab-review/v1", "items": items,
            "summary": {"submitted": len(items), "valid": len(valid), "invalid": len(items) - len(valid),
                        "passed": sum(item["status"] == "PASS" for item in valid)}}
