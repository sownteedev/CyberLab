import base64
from dataclasses import asdict
from hashlib import sha256
import json
from time import monotonic

from cyberlab.assessment_checks import check_result, combined_status
from cyberlab.assessment_goals import check_goal
from cyberlab.submission import public_report, submission_archive
from cyberlab.regex_check import MAX_REGEX_BUDGET_SECONDS
from cyberlab.workspace import WorkspaceNotFound, select, validate_entries

MAX_ARTIFACT_BYTES = 4 * 1024 * 1024
MAX_ARTIFACT_ENTRIES = 256


def lab_digest(lab):
    def encode(value):
        if isinstance(value, bytes):
            return {"sha256": sha256(value).hexdigest(), "size": len(value)}
        raise TypeError("Unsupported Lab value")

    payload = json.dumps(asdict(lab), default=encode, ensure_ascii=True,
                         sort_keys=True, separators=(",", ":"))
    return sha256(payload.encode("utf-8")).hexdigest()


def collect_artifact(artifact, entries_by_node, errors, used_bytes, used_entries):
    base = {"id": artifact.id, "node": artifact.node, "path": artifact.path,
            "label": artifact.label, "required": artifact.required}
    if artifact.node in errors:
        return {**base, "status": "ERROR", "message": errors[artifact.node]}, used_bytes, used_entries
    entries = entries_by_node.get(artifact.node)
    if entries is None:
        return {**base, "status": "ERROR", "message": "Node workspace was not captured"}, used_bytes, used_entries
    try:
        selected = select(tuple(entries.values()), artifact.path)
    except WorkspaceNotFound:
        status = "MISSING" if artifact.required else "OPTIONAL_MISSING"
        return {**base, "status": status, "message": "Declared evidence was not found"}, used_bytes, used_entries
    except ValueError as error:
        return {**base, "status": "ERROR", "message": str(error)}, used_bytes, used_entries
    total_bytes = used_bytes + sum(entry.size for entry in selected)
    total_entries = used_entries + len(selected)
    if total_bytes > MAX_ARTIFACT_BYTES or total_entries > MAX_ARTIFACT_ENTRIES:
        return {**base, "status": "ERROR", "message": "Evidence exceeds 4 MiB or 256 entries"}, used_bytes, used_entries
    contents = []
    for entry in sorted(selected, key=lambda item: item.path):
        item = entry.metadata()
        if entry.kind == "file":
            item.update(sha256=sha256(entry.data).hexdigest(),
                        content_b64=base64.b64encode(entry.data).decode("ascii"))
        contents.append(item)
    return {**base, "status": "COLLECTED", "entries": contents}, total_bytes, total_entries


def evaluate(session, workspace_by_node, errors=None, package_digest=None, *, assess=True):
    lab = session.lab
    errors = dict(errors or {})
    entries_by_node = {}
    for node_id, entries in workspace_by_node.items():
        try:
            checked = validate_entries(entries, unsafe=True)
            entries_by_node[node_id] = {entry.path: entry for entry in checked}
        except ValueError as error:
            errors[node_id] = str(error)
    regex_deadline = monotonic() + MAX_REGEX_BUDGET_SECONDS
    results = [check_result(result, entries_by_node, errors, regex_deadline=regex_deadline)
               for result in lab.assessment.results] if assess else []
    results_by_id = {result["id"]: result for result in results}

    goals = []
    goals_by_id = {}
    if assess:
        for goal in lab.assessment.goals:
            res = check_goal(goal, results_by_id, goals_by_id)
            goals.append(res)
            goals_by_id[goal.id] = res
    artifacts = []
    used_bytes = 0
    used_entries = 0
    for artifact in lab.assessment.artifacts:
        collected, used_bytes, used_entries = collect_artifact(
            artifact, entries_by_node, errors, used_bytes, used_entries)
        artifacts.append(collected)
    report = {
        "format": "cyberlab-checkwork/v1",
        "session_id": session.id, "lab_id": lab.metadata.id,
        "lab_name": lab.metadata.name, "lab_version": lab.metadata.version,
        "lab_digest": package_digest or lab_digest(lab),
        "resolved_digest": lab_digest(lab),
        "status": combined_status([item["status"] for item in (goals or results)]),
        "submission_ready": all(item["status"] in {"COLLECTED", "OPTIONAL_MISSING"} for item in artifacts),
        "results": results, "goals": goals, "artifacts": artifacts,
    }
    if lab.settings.collect_documentation and lab.documentation is not None:
        report["documentation"] = lab.documentation.content or ""
    return report
