from pathlib import PurePosixPath
import re

from .labtainer_archive import read_labtainer_archive
from .labtainer_source import LabtainerSourceError, text_file
from .package import PackageLimit

MESSAGES = {
    "x11": "X11 forwarding is requested. CyberLab does not expose the host display; graphical applications need an isolated display implementation.",
    "system_files": "System files need a reviewed container image; they cannot be copied into the learner home instead.",
    "startup_hooks": "Lifecycle scripts need review and a supported container setup mechanism. They are not executed during import.",
    "grading_hooks": "Instructor scripts need conversion to supported Checkwork rules; importing them as ordinary files would not preserve grading.",
    "privileged": "Privileged containers are not permitted by the CyberLab runtime policy.",
    "image_build": "Dockerfiles are not built or executed. Select an approved image and verify its accounts, tools and services.",
    "conversion": "Other declarations or assets cannot be converted safely. The source has not been changed and no draft was created.",
    "archive": "The archive is invalid, exceeds limits, or does not contain exactly one Lab root with config/start.config.",
}


class LabtainerCompatibilityError(ValueError):
    def __init__(self, issues):
        self.issues = issues
        messages = [issue["message"] for issue in issues if issue["severity"] == "blocker"]
        super().__init__("Labtainer import blocked. " + " ".join(messages) + " No draft was created.")


def source_files(file_map):
    starts = [path for path, data in file_map.items() if data is not None
              and (path == "config/start.config" or path.endswith("/config/start.config"))]
    if len(starts) != 1:
        raise ValueError("Labtainer package requires exactly one config/start.config")
    root = starts[0].removesuffix("config/start.config")
    ancestors = {str(parent) for parent in PurePosixPath(root).parents} | {root.rstrip("/")}
    if any(not path.startswith(root) and not (data is None and path in ancestors)
           for path, data in file_map.items()):
        raise ValueError("Labtainer archive contains entries outside the selected Lab root")
    return root, {path[len(root):]: data for path, data in file_map.items() if path.startswith(root)}


def location(path, line=None):
    safe = re.sub(r"[^A-Za-z0-9_./-]", "_", path)[:200]
    return f"{safe}:{line}" if line is not None else safe


def requirement_issues(files):
    issues = {}

    def add(code, path, line=None):
        issue = issues.setdefault(code, {"code": code, "severity": "review" if code == "image_build" else "blocker",
                                         "message": MESSAGES[code], "locations": [], "count": 0})
        issue["count"] += 1
        if len(issue["locations"]) < 8:
            issue["locations"].append(location(path, line))

    section = "global"
    for number, raw in enumerate(text_file(files, "config/start.config").splitlines(), 1):
        parts = raw.strip().split()
        if not parts or parts[0].startswith("#"):
            continue
        tag = parts[0].upper()
        if tag in {"GLOBAL_SETTINGS", "NETWORK", "CONTAINER"}:
            section = tag
        if section == "CONTAINER" and len(parts) == 2:
            if tag == "X11" and parts[1].lower() == "yes":
                add("x11", "config/start.config", number)
            if tag == "NO_PRIVILEGE" and parts[1].lower() == "no":
                add("privileged", "config/start.config", number)
    for path, data in sorted(files.items()):
        parts = path.split("/")
        if len(parts) < 2:
            continue
        if parts[0] == "dockerfiles" and data is not None:
            add("image_build", path)
        elif parts[0] == "instr_config" and path not in {"instr_config/results.config", "instr_config/goals.config"}:
            if data is not None:
                add("grading_hooks", path)
        elif parts[0] not in {"config", "docs", "dockerfiles", "instr_config"}:
            if parts[1] == "_system":
                add("system_files", path)
            elif parts[1] in {"_bin", "_startup", "_instructor"}:
                add("startup_hooks", path)
    return list(issues.values())


def inspect_archive(archive, target_id=None, target_title=None):
    from . import LabError
    from .labtainer_converter import convert_labtainer_files

    try:
        file_map = read_labtainer_archive(archive)
        _, files = source_files(file_map)
    except ValueError:
        return report([generic_issue("archive")], False)
    issues = []
    try:
        issues = requirement_issues(files)
        if any(issue["severity"] == "blocker" for issue in issues):
            return report(issues, False)
        convert_labtainer_files(file_map, target_id, target_title)
    except (ValueError, LabError, PackageLimit) as error:
        issue = generic_issue("conversion")
        if isinstance(error, LabtainerSourceError):
            issue["locations"] = [location(error.source, error.line)]
        issues.append(issue)
        return report(issues, False)
    return report(issues, True)


def generic_issue(code):
    return {"code": code, "severity": "blocker", "message": MESSAGES[code], "locations": [], "count": 1}


def report(issues, can_import):
    return {"format": "cyberlab-labtainer-compatibility/v1", "can_import": can_import,
            "runtime_ready": False, "status": "requires-runtime-review" if can_import else "blocked",
            "issues": issues, "note": "Analysis only: no draft, image, Lab or Session was created. A convertible draft is not a runnable Lab."}
