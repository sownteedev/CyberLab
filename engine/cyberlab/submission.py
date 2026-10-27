import base64
from hashlib import sha256
from html import escape
from io import BytesIO
import json
import zipfile

from cyberlab.workspace import relative_path

MAX_SUBMISSION_BYTES = 8 * 1024 * 1024


def public_report(report):
    result = json.loads(json.dumps(report))
    result.pop("documentation", None)
    for artifact in result.get("artifacts", []):
        for entry in artifact.get("entries", []):
            entry.pop("content_b64", None)
    return result


def html_report(report):
    rows = "".join(
        "<tr>" + "".join("<td>" + escape(str(value)) + "</td>" for value in (
            item.get("description") or item["id"], item["status"], item.get("message", ""))) + "</tr>"
        for item in report.get("goals", []) + report.get("results", []))
    quiz = report.get("quiz")
    quiz_html = ""
    if quiz is not None:
        quiz_rows = "".join(
            "<tr>" + "".join("<td>" + escape(str(item.get(key, ""))) + "</td>"
                               for key in ("id", "status", "selected", "explanation")) + "</tr>"
            for item in quiz.get("questions", []))
        quiz_html = ("<h2>Quiz</h2><p>" + escape(str(quiz["created_at"]))
                     + "</p><table><thead><tr><th>Question</th><th>Status</th><th>Selected (0-based)</th>"
                     "<th>Explanation</th></tr></thead><tbody>" + quiz_rows + "</tbody></table>")
    return ("<!doctype html><html lang=\"en\"><meta charset=\"utf-8\">"
            "<meta http-equiv=\"Content-Security-Policy\" content=\"default-src 'none'\">"
            "<title>CyberLab Checkwork</title><h1>" + escape(report["lab_name"]) + "</h1><p>"
            + escape(report["status"]) + " - " + escape(report["created_at"])
            + "</p><p>Local self-check; not a tamper-proof grade.</p>"
            "<table><thead><tr><th>Criterion</th><th>Status</th><th>Details</th></tr></thead><tbody>"
            + rows + "</tbody></table>" + quiz_html + "</html>")


def submission_archive(report):
    evidence = {}
    for artifact in report.get("artifacts", []):
        if artifact.get("status") != "COLLECTED":
            continue
        node = relative_path(artifact["node"])
        if "/" in node:
            raise ValueError("Invalid evidence node")
        for entry in artifact.get("entries", []):
            path = "artifacts/" + node + "/" + relative_path(entry["path"])
            if entry["kind"] == "directory":
                path += "/"
                data = b""
            elif entry["kind"] == "file":
                data = base64.b64decode(entry["content_b64"], validate=True)
                if len(data) != entry["size"] or sha256(data).hexdigest() != entry["sha256"]:
                    raise ValueError("Stored evidence integrity check failed")
            else:
                raise ValueError("Unsupported evidence entry")
            if path in evidence and evidence[path] != data:
                raise ValueError("Conflicting evidence paths")
            evidence[path] = data
    if len(evidence) > 256 or sum(map(len, evidence.values())) > 4 * 1024 * 1024:
        raise ValueError("Stored evidence exceeds its limit")
    manifest = {key: report[key] for key in (
        "id", "session_id", "lab_id", "lab_name", "lab_version", "lab_digest", "created_at", "status")}
    manifest.update(format="cyberlab-submission/v1", submission_ready=report.get("submission_ready", False),
                    evidence=[{"path": path, "size": len(data), "sha256": sha256(data).hexdigest()}
                              for path, data in sorted(evidence.items())])
    output = BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("manifest.json", json.dumps(manifest, ensure_ascii=True, indent=2))
        archive.writestr("checkwork.json", json.dumps(public_report(report), ensure_ascii=True, indent=2))
        archive.writestr("report.html", html_report(report))
        if "quiz" in report:
            archive.writestr("quiz.json", json.dumps(report["quiz"], ensure_ascii=True, indent=2))
        if "documentation" in report:
            archive.writestr("instructions.md", report["documentation"])
        for path, data in sorted(evidence.items()):
            archive.writestr(path, data)
    data = output.getvalue()
    if len(data) > MAX_SUBMISSION_BYTES:
        raise ValueError("Submission archive exceeds 8 MiB")
    return data
