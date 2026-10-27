from hashlib import sha256
import json
from pathlib import PurePosixPath

import yaml

from .assets import valid_path
from .labtainer_archive import read_labtainer_archive
from .labtainer_assessment import parse_goals_config, parse_results_config
from .labtainer_parameters import parse_parameter_config
from .labtainer_source import fail, normalize_id, text_file
from .labtainer_start import parse_start_config
from .loader import validate_lab
from .package import check_package, load_snapshot
from .quiz_import import convert_quizzes
from cyberlab.parameters import resolve_parameters

REPORT_PATH = "assets/docs/labtainer-import.json"


def convert_labtainer_files(file_map, target_id=None, target_title=None):
    starts = [path for path, data in file_map.items() if data is not None
              and (path == "config/start.config" or path.endswith("/config/start.config"))]
    if len(starts) != 1:
        raise ValueError("Labtainer package requires exactly one config/start.config")
    root = starts[0].removesuffix("config/start.config")
    ancestors = {str(parent) for parent in PurePosixPath(root).parents} | {root.rstrip("/")}
    if any(not path.startswith(root) and not (data is None and path in ancestors)
           for path, data in file_map.items()):
        raise ValueError("Labtainer archive contains entries outside the selected Lab root")
    files = {path[len(root):]: data for path, data in file_map.items() if path.startswith(root)}
    start = parse_start_config(text_file(files, "config/start.config"))
    operations = parse_parameter_config(text_file(files, "config/parameter.config"), start.nodes)
    results, result_ids = parse_results_config(text_file(files, "instr_config/results.config"), start.nodes)
    goals = parse_goals_config(text_file(files, "instr_config/goals.config"), result_ids)
    quizzes = convert_quizzes({path: data for path, data in files.items() if data is not None}, "config")
    about = text_file(files, "config/about.txt").strip()
    lab_id = target_id or normalize_id(PurePosixPath(root.rstrip("/")).name or "labtainer-lab")
    title = target_title or (about.splitlines()[0] if about else lab_id.replace("-", " ").title())
    assets, image_sources = {}, []
    known_configs = {"config/start.config", "config/parameter.config", "config/about.txt",
                     "instr_config/results.config", "instr_config/goals.config"}
    for path, data in sorted(files.items()):
        if path in known_configs or (PurePosixPath(path).parent == PurePosixPath("config") and path.endswith(".quiz")):
            if data is None:
                fail(path, 1, "configuration must be a regular file, not a directory")
            continue
        if data is None and path in {"", "config", "instr_config", "dockerfiles", "docs", *start.nodes}:
            continue
        if path.startswith("dockerfiles/"):
            if data is not None:
                image_sources.append({"path": path, "sha256": sha256(data).hexdigest()})
            continue
        first, separator, relative = path.partition("/")
        node = start.nodes.get(first)
        if node is not None and separator:
            if relative.split("/", 1)[0] in {"_system", "_bin", "_startup", "_instructor"}:
                fail(path, 1, "system provisioning and lifecycle hooks are not converted to home files")
            if not valid_path(relative):
                fail(path, 1, "home-file path cannot be imported without renaming or moving it")
            prefix = f"assets/nodes/{node['id']}"
            assets[prefix + "/" + relative] = data
            node["files"] = [{"source": prefix, "target": "."}]
        elif first == "docs" and separator and valid_path(relative):
            assets["assets/docs/source/" + relative] = data
        else:
            fail(path, 1, "unrecognized Labtainer file; nothing was imported")

    if about:
        assets["assets/docs/manual.md"] = ("# " + title + "\n\n" + about).encode("utf-8")
    if results or goals:
        start.settings.setdefault("checkwork", True)
    report = {
        "format": "cyberlab-labtainer-import/v1", "status": "requires-runtime-review",
        "source_digest": sha256(json.dumps([
            [path, sha256(data).hexdigest() if data is not None else None]
            for path, data in sorted(files.items())], ensure_ascii=True).encode("utf-8")).hexdigest(),
        "nodes": [{"source": name, "id": node["id"], "user": node["user"]["name"],
                   "review": ["image", "command", "uid", "gid", "shell"]} for name, node in start.nodes.items()],
        "unbuilt_image_sources": image_sources,
        "notes": ["No Docker image was substituted, built or pulled. Select an approved image and startup argv for every node.",
                  "UID/GID 1000 and /bin/bash are editable suggestions, not accounts discovered in an image. Verify runtime readiness.",
                  "CyberLab generates a new instance seed; imported parameter values do not reproduce a previous Labtainer run.",
                  "Source docs are preserved as assets/docs/source; select or adapt the learner manual in the editor."]}
    assets[REPORT_PATH] = json.dumps(report, indent=2, ensure_ascii=True).encode("utf-8")
    document = {"apiVersion": "cyberlab.ptit/v1", "kind": "Lab",
                "metadata": {"id": lab_id, "name": title, "version": "1.0.0"},
                "settings": start.settings, "networks": start.networks,
                "nodes": list(start.nodes.values()), "terminals": start.terminals}
    if about:
        document["documentation"] = "assets/docs/manual.md"
    if operations:
        document["parameterizations"] = operations
    if results or goals:
        document["assessment"] = {"artifacts": [], "results": results, "goals": goals}
    if quizzes:
        document["quizzes"] = quizzes
    validate_lab(document)
    definition = yaml.safe_dump(document, sort_keys=False, allow_unicode=True)
    check_package(definition, assets)
    lab = load_snapshot({"definition": definition, "assets": assets})
    resolve_parameters(lab, {}, "labtainer-import-validation")
    return definition, assets, lab


def convert_labtainer_archive(archive, target_id=None, target_title=None):
    return convert_labtainer_files(read_labtainer_archive(archive), target_id, target_title)
