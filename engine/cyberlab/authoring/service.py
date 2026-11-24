import ctypes
import errno
from hashlib import sha256
from importlib.resources import files
import json
import os
import pwd
from pathlib import Path
import shutil
import tempfile

from jsonschema import Draft202012Validator
import yaml

from cyberlab.lab import LabError, load_lab, list_labs
from cyberlab.lab.catalog import read_package
from cyberlab.lab.exchange import FORMAT, MAX_ARCHIVE, create_package, read_package as read_exchange_package
from cyberlab.lab.package import load_snapshot, materialize
from cyberlab.lab.loader import _LabYamlLoader
from cyberlab.lab.topics import catalog as topic_catalog, require_tags
from cyberlab.policy import PolicyDenied

from .store import DraftConflict, DraftLimit, DraftNotFound, DraftStore, MAX_ASSET, MAX_DEFINITION, MAX_PACKAGE, MAX_PATHS, check_package
from .updating import update_catalog
from .profiles import image_profiles
from .protection import EditProtection

MAX_CATALOG_LABS = 128

def schema():
    return json.loads(files("cyberlab.schemas").joinpath("v1/lab.schema.json").read_text())

def summary(snapshot):
    result = {**{key: snapshot[key] for key in ("id", "owner", "revision", "definition", "digest")},
            "origin": snapshot.get("origin"),
            "assets": [{"path": path, "size": len(data) if data is not None else 0,
                        "sha256": sha256(data).hexdigest() if data is not None else "",
                        "kind": "file" if data is not None else "directory"}
                       for path, data in sorted(snapshot["assets"].items())]}
    try:
        result["difficulty"] = json.loads(snapshot["definition"]).get("metadata", {}).get("difficulty")
    except (TypeError, ValueError):
        result["difficulty"] = None
    return result

def rename_new(source, destination):
    library = ctypes.CDLL(None, use_errno=True)
    rename = library.renameat2
    rename.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
    rename.restype = ctypes.c_int
    if rename(-100, os.fsencode(source), -100, os.fsencode(destination), 1):
        error = ctypes.get_errno()
        if error == errno.EEXIST:
            raise DraftConflict("A catalog destination already exists; it was not overwritten")
        raise OSError(error, "Cannot atomically publish Lab")

class Authoring:
    def __init__(self, database, catalog, policy, lifecycle_lock=None, runtime_checker=None, update_checker=None):
        self.store = DraftStore(database)
        self.protection = EditProtection(self.store)
        self.catalog = Path(catalog)
        self.policy = policy
        self.lifecycle_lock = lifecycle_lock or self.store.lock
        self.runtime_checker = runtime_checker
        self.update_checker = update_checker
        self.software = None

    def capabilities(self):
        from cyberlab.lab.software import catalog
        from cyberlab.lab.workstation import UBUNTU_IMAGE
        machine_setup = UBUNTU_IMAGE in self.policy.workstation_images and UBUNTU_IMAGE in self.policy.allowed_images
        return {"schema": schema(), "allowed_images": sorted(self.policy.allowed_images),
                "machine_setup": machine_setup, "machine_setup_version": 1 if machine_setup else 0,
                "topic_catalog": topic_catalog(), "edit_protection": True,
                "software_preparation": self.software is not None,
                "software_search": self.software is not None,
                "software_catalog": catalog(),
                "image_profiles": image_profiles(self.policy.allowed_images, self.policy.workstation_images),
                "max_nodes": self.policy.max_nodes, "max_networks": self.policy.max_networks,
                "max_definition_bytes": MAX_DEFINITION, "max_asset_bytes": MAX_ASSET,
                "max_package_bytes": MAX_PACKAGE, "max_paths": MAX_PATHS,
                "max_lab_archive_bytes": MAX_ARCHIVE,
                "max_catalog_labs": MAX_CATALOG_LABS,
                "home_directory_target": True,
                "file_workspace": True,
                "runtime_check": self.runtime_checker is not None,
                "workstation_runtime": True,
                "network_internet": True,
                "clone_lab": True, "installed_update": self.update_checker is not None, "resume_editing_draft": True,
                "max_terminal_slots_per_node": 4, "max_terminal_slots_per_lab": 8,
                "static_networking": {"private_ipv4_only": True, "min_prefix": 16, "max_prefix": 30,
                                      "gateway_role": "bridge", "dns_scope": "attached-static-nodes", "overlap_policy": "reject"},
                "publish_requires_admin": False, "publication_replaces_existing": False,
                "lab_package_format": FORMAT, "lab_package_images": "references-only"}

    def export_lab_package(self, lab_id, uid):
        with self.lifecycle_lock:
            definition, assets, _ = read_package(self.catalog, lab_id)
            lab = load_snapshot({"definition": definition, "assets": dict(assets)})
            if lab.metadata.id != lab_id:
                raise DraftConflict("Lab identity changed during export; review it again")
            return create_package(definition, dict(assets), lab, self.protection.verifier("lab", lab_id, uid))

    def export_draft_package(self, identifier, revision, uid):
        snapshot = self.store.get(identifier, uid, revision)
        lab = load_snapshot(snapshot)
        return create_package(snapshot["definition"], snapshot["assets"], lab, self.protection.verifier("draft", identifier, uid))

    def import_labtainer(self, archive, target_id, title, uid):
        from cyberlab.lab.labtainer_converter import REPORT_PATH, convert_labtainer_archive
        definition, assets, lab = convert_labtainer_archive(archive, target_id, title)
        imported_id = target_id or lab.metadata.id
        imported_title = title or lab.metadata.name
        document = yaml.safe_load(definition)
        document["metadata"]["id"] = imported_id
        document["metadata"]["name"] = imported_title
        serialized = json.dumps(document, indent=2, ensure_ascii=False)
        draft = summary(self.store.clone(imported_id, imported_title, serialized, tuple(assets.items()), uid))
        return {**draft, "import_report": json.loads(assets[REPORT_PATH])}

    def inspect_labtainer(self, archive, target_id, title, uid):
        from cyberlab.lab.labtainer_compatibility import inspect_archive
        return inspect_archive(archive, target_id or None, title or None)

    def import_lab_package(self, archive, target_id, title, uid):
        definition, assets, manifest = read_exchange_package(archive)
        lab = load_snapshot({"definition": definition, "assets": assets})
        if (manifest.get("lab") != {"id": lab.metadata.id, "name": lab.metadata.name,
                                    "version": lab.metadata.version}
                or manifest.get("images") != sorted({node.image for node in lab.nodes if node.image is not None})):
            raise ValueError("Lab package metadata does not match its definition")
        document = yaml.load(definition, Loader=_LabYamlLoader)
        imported_id = target_id or lab.metadata.id
        imported_title = title or lab.metadata.name
        document["metadata"]["id"] = imported_id
        document["metadata"]["name"] = imported_title
        definition = json.dumps(document, indent=2, ensure_ascii=False)
        if manifest.get("edit_protection"):
            with self.lifecycle_lock, self.store.lock:
                if (self.catalog / imported_id).exists():
                    raise DraftConflict("Lab ID already exists; catalog entries are not overwritten")
                snapshot = self.store.clone(imported_id, imported_title, definition, tuple(assets.items()), uid)
                try:
                    self.protection.install("draft", snapshot["id"], manifest["edit_protection"])
                    result = self.publish(snapshot["id"], snapshot["revision"], snapshot["digest"], uid)
                    if not result.get("published"):
                        raise ValueError("Protected Lab could not be validated for import")
                    return {"installed": True, "lab_id": imported_id, "edit_protected": True}
                finally:
                    self.store.delete(snapshot["id"], uid, snapshot["revision"])
                    self.protection.link("draft", snapshot["id"], None)
        return summary(self.store.clone(imported_id, imported_title, definition, tuple(assets.items()), uid))

    def create(self, lab_id, title, uid, tags=None, difficulty=None):
        tags = require_tags(tags)
        if difficulty is not None and difficulty not in {"easy", "medium", "hard"}:
            raise ValueError("Chọn độ khó: easy, medium hoặc hard")
        snapshot = self.store.create(lab_id, title, uid, tags)
        if difficulty is None:
            return summary(snapshot)
        document = json.loads(snapshot["definition"])
        document["metadata"]["difficulty"] = difficulty
        return summary(self.store.change(snapshot["id"], uid, snapshot["revision"], definition=json.dumps(document, ensure_ascii=False, indent=2)))

    def clone_lab(self, source_id, target_id, title, uid):
        if source_id == target_id:
            raise DraftConflict("A clone needs a new Lab ID; use edit to update the original")
        with self.lifecycle_lock:
            definition, assets, _ = read_package(self.catalog, source_id)
            document = yaml.load(definition, Loader=_LabYamlLoader)
            document["metadata"]["id"] = target_id
            document["metadata"]["name"] = title
            updated = json.dumps(document, indent=2, ensure_ascii=False)
            snapshot = self.store.clone(target_id, title, updated, assets, uid)
            verifier = self.protection.verifier("lab", source_id, uid)
            if verifier:
                self.protection.install("draft", snapshot["id"], verifier)
            return summary(snapshot)

    def edit_lab(self, lab_id, uid, draft_id="", fresh=False):
        if self.update_checker is None:
            raise ValueError("Installed-Lab updates are unavailable")
        if draft_id and fresh:
            raise ValueError("Choose an existing draft or create a new one, not both")
        with self.lifecycle_lock, self.store.lock:
            definition, assets, digest = read_package(self.catalog, lab_id)
            candidates = [entry for entry in self.list(uid)
                          if entry["owner"] == uid and entry["lab_id"] == lab_id
                          and entry.get("origin") and entry["origin"]["lab_id"] == lab_id]
            if draft_id:
                if not any(entry["id"] == draft_id for entry in candidates):
                    raise DraftConflict("Editing draft no longer belongs to this Lab; choose again")
                return self.get(draft_id, uid)
            if not fresh and len(candidates) == 1:
                return self.get(candidates[0]["id"], uid)
            if not fresh and candidates:
                return {"selection_required": True, "lab_id": lab_id,
                        "drafts": [{**entry, "based_on_current": entry["origin"]["digest"] == digest}
                                   for entry in candidates]}
            document = yaml.load(definition, Loader=_LabYamlLoader)
            updated = json.dumps(document, indent=2, ensure_ascii=False)
            snapshot = self.store.clone(lab_id, document["metadata"]["name"], updated, assets, uid,
                                        origin={"lab_id": lab_id, "digest": digest})
            self.protection.inherit("lab", lab_id, "draft", snapshot["id"], uid)
            return summary(snapshot)

    def get(self, identifier, uid):
        return summary(self.store.get(identifier, uid))

    def list(self, uid):
        entries = self.store.list(uid, include_definition=True)
        for entry in entries:
            definition = entry.pop("definition")
            try:
                document = yaml.load(definition, Loader=_LabYamlLoader)
            except (yaml.YAMLError, RecursionError, ValueError):
                document = None
            metadata = document.get("metadata") if isinstance(document, dict) else None
            for field, source, limit in (("lab_id", "id", 64), ("name", "name", 128)):
                value = metadata.get(source) if isinstance(metadata, dict) else None
                entry[field] = value if isinstance(value, str) and len(value) <= limit and value.isprintable() else ""
            entry["difficulty"] = metadata.get("difficulty") if isinstance(metadata, dict) and metadata.get("difficulty") in {"easy", "medium", "hard"} else None
        return entries

    def save(self, identifier, revision, definition, uid):
        return summary(self.store.change(identifier, uid, revision, definition=definition))

    def save_workspace(self, identifier, revision, payload, uid):
        from .workspace import save_workspace
        return summary(save_workspace(self.store, identifier, revision, payload, uid))

    def set_node_account_password(self, identifier, revision, node_id, payload, uid):
        from .passwords import set_password
        return summary(set_password(self.store, self.policy, identifier, revision, node_id, payload, uid))

    def put_assets(self, identifier, revision, assets, uid):
        return summary(self.store.change(identifier, uid, revision, additions=assets))

    def remove_asset(self, identifier, revision, path, uid):
        return summary(self.store.change(identifier, uid, revision, removals=(path,)))

    def asset(self, identifier, revision, path, uid):
        snapshot = self.store.get(identifier, uid, revision)
        if path not in snapshot["assets"] or snapshot["assets"][path] is None:
            raise DraftNotFound("Asset not found")
        return snapshot["assets"][path]

    def _validate(self, snapshot):
        report = {"id": snapshot["id"], "revision": snapshot["revision"], "digest": snapshot["digest"], "valid": False, "runtime_verified": False, "issues": [], "error": ""}
        try:
            document = yaml.load(snapshot["definition"], Loader=_LabYamlLoader)
        except (yaml.YAMLError, RecursionError, ValueError):
            report["issues"].append({"stage": "syntax", "path": "/", "message": "Invalid YAML/JSON; use one document, unique keys and no aliases"})
            report["error"] = report["issues"][0]["message"]
            return report
        for error in Draft202012Validator(schema()).iter_errors(document):
            report["issues"].append({"stage": "schema", "path": "/" + "/".join(str(part) for part in error.absolute_path), "message": f"{error.validator} constraint failed"})
            if len(report["issues"]) == 32:
                break
        if report["issues"]:
            report["error"] = report["issues"][0]["message"]
            return report
        try:
            require_tags(document["metadata"].get("tags"))
        except ValueError as error:
            report["issues"].append({"stage": "schema", "path": "/metadata/tags", "message": str(error)})
            report["error"] = str(error)
            return report
        with tempfile.TemporaryDirectory(prefix="cyberlab-draft-check-") as temporary:
            project = Path(temporary)
            materialize(snapshot, project)
            try:
                lab = load_lab(project / "lab.yaml")
            except LabError as error:
                report["issues"].append({"stage": "lab", "path": "/", "message": str(error)})
                report["error"] = report["issues"][0]["message"]
                return report
            try:
                self.policy.validate(lab)
            except PolicyDenied as error:
                report["issues"].append({"stage": "policy", "path": "/", "message": str(error)})
                report["error"] = report["issues"][0]["message"]
                return report
        report.update(valid=True, lab_id=lab.metadata.id, lab_version=lab.metadata.version)
        return report

    def validate(self, identifier, revision, uid):
        return self._validate(self.store.get(identifier, uid, revision))

    def check_runtime(self, identifier, revision, uid):
        snapshot = self.store.get(identifier, uid, revision)
        report = self._validate(snapshot)
        if not report["valid"]:
            return {**report, "ready": False, "cleanup_complete": True}
        if self.runtime_checker is None:
            raise ValueError("Runtime readiness checks are unavailable")
        with tempfile.TemporaryDirectory(prefix="cyberlab-runtime-check-") as temporary:
            project = Path(temporary)
            materialize(snapshot, project)
            result = self.runtime_checker(load_lab(project / "lab.yaml"), uid)
        return {**report, **result}

    def update_installed(self, target_id, identifier, revision, draft_digest, expected_catalog_digest, uid):
        if self.update_checker is None:
            raise ValueError("Installed-Lab updates are unavailable")
        with self.lifecycle_lock, self.store.lock:
            snapshot = self.store.get(identifier, uid, revision)
            if snapshot["digest"] != draft_digest:
                raise DraftConflict("Reviewed draft digest does not match its contents")
            origin = snapshot.get("origin")
            if origin and origin != {"lab_id": target_id, "digest": expected_catalog_digest}:
                raise DraftConflict("Target review does not match this editing draft")
            report = self._validate(snapshot)
            if not report["valid"]:
                return {**report, "updated": False}
            if report["lab_id"] != target_id:
                raise DraftConflict("Draft Lab ID must match the installed Lab being updated")
            self.update_checker(target_id, uid)
            self.require_software(snapshot)
            result = update_catalog(
                self.catalog, target_id, snapshot, expected_catalog_digest, self.policy,
                record_origin=lambda digest: self.store.set_origin(
                    identifier, revision, uid, {"lab_id": target_id, "digest": digest}))
            if self.protection.protected("lab", target_id, uid):
                self.protection.inherit("lab", target_id, "draft", identifier, uid)
            else:
                self.protection.inherit("draft", identifier, "lab", target_id, uid)
            return {**report, **result, "updated": True}

    def publish(self, identifier, revision, digest, uid):
        with self.lifecycle_lock, self.store.lock:
            snapshot = self.store.get(identifier, uid, revision)
            if digest != snapshot["digest"]:
                raise DraftConflict("Reviewed digest does not match the draft contents")
            report = self._validate(snapshot)
            if report["valid"]:
                self.require_software(snapshot)
            if not report["valid"]:
                return {**report, "published": False}
            catalog = list_labs(self.catalog)
            if any(lab.metadata.id == report["lab_id"] for lab in catalog):
                raise DraftConflict("Lab ID already exists; catalog entries are not overwritten")
            if len(catalog) >= MAX_CATALOG_LABS:
                raise DraftLimit("Local library limit reached; no Lab was written")
            group_id = pwd.getpwuid(uid).pw_gid if os.geteuid() == 0 and uid != 0 else os.getgid()
            destination = self.catalog / report["lab_id"]
            stage = Path(tempfile.mkdtemp(prefix=".cyberlab-publish-", dir=self.catalog))
            previous_family = self.protection.family_id("lab", report["lab_id"], uid)
            try:
                materialize(snapshot, stage)
                self.policy.validate(load_lab(stage / "lab.yaml"))
                for entry in stage.rglob("*"):
                    entry.chmod(0o755 if entry.is_dir() else 0o644)
                    if entry.is_file():
                        with entry.open("rb") as source:
                            os.fsync(source.fileno())
                stage.chmod(0o755)
                self.protection.inherit("draft", identifier, "lab", report["lab_id"], uid)
                rename_new(stage, destination)
                if uid != 0:
                    for entry in (*destination.rglob("*"), destination):
                        try:
                            os.chown(entry, uid, group_id)
                        except OSError:
                            pass
                descriptor = os.open(self.catalog, os.O_RDONLY | os.O_DIRECTORY)
                try:
                    os.fsync(descriptor)
                finally:
                    os.close(descriptor)
            except BaseException:
                self.protection.link("lab", report["lab_id"], previous_family)
                raise
            finally:
                if stage.exists():
                    shutil.rmtree(stage)
            return {**report, "published": True}

    def require_software(self, snapshot):
        from cyberlab.lab.software import enabled
        lab = load_snapshot(snapshot)
        if any(enabled(node.software) for node in lab.nodes):
            if self.software is None:
                raise ValueError("Software preparation is unavailable")
