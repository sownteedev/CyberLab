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
from cyberlab.policy import PolicyDenied

from .store import DraftConflict, DraftLimit, DraftNotFound, DraftStore, MAX_ASSET, MAX_DEFINITION, MAX_PACKAGE, MAX_PATHS, check_package
from .updating import update_catalog
from .profiles import image_profiles

MAX_CATALOG_LABS = 128

def schema():
    return json.loads(files("cyberlab.schemas").joinpath("v1/lab.schema.json").read_text())

def summary(snapshot):
    return {**{key: snapshot[key] for key in ("id", "owner", "revision", "definition", "digest")},
            "origin": snapshot.get("origin"),
            "assets": [{"path": path, "size": len(data) if data is not None else 0,
                        "sha256": sha256(data).hexdigest() if data is not None else "",
                        "kind": "file" if data is not None else "directory"}
                       for path, data in sorted(snapshot["assets"].items())]}

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
        self.catalog = Path(catalog)
        self.policy = policy
        self.lifecycle_lock = lifecycle_lock or self.store.lock
        self.runtime_checker = runtime_checker
        self.update_checker = update_checker

    def capabilities(self):
        return {"schema": schema(), "allowed_images": sorted(self.policy.allowed_images),
                "image_profiles": image_profiles(self.policy.allowed_images),
                "max_nodes": self.policy.max_nodes, "max_networks": self.policy.max_networks,
                "max_definition_bytes": MAX_DEFINITION, "max_asset_bytes": MAX_ASSET,
                "max_package_bytes": MAX_PACKAGE, "max_paths": MAX_PATHS,
                "max_lab_archive_bytes": MAX_ARCHIVE,
                "max_catalog_labs": MAX_CATALOG_LABS,
                "home_directory_target": True,
                "runtime_check": self.runtime_checker is not None,
                "clone_lab": True, "installed_update": self.update_checker is not None,
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
            return create_package(definition, dict(assets), lab)

    def export_draft_package(self, identifier, revision, uid):
        snapshot = self.store.get(identifier, uid, revision)
        lab = load_snapshot(snapshot)
        return create_package(snapshot["definition"], snapshot["assets"], lab)

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
        return summary(self.store.clone(imported_id, imported_title, definition, tuple(assets.items()), uid))

    def create(self, lab_id, title, uid):
        return summary(self.store.create(lab_id, title, uid))

    def clone_lab(self, source_id, target_id, title, uid):
        if source_id == target_id:
            raise DraftConflict("A clone needs a new Lab ID; use edit to update the original")
        with self.lifecycle_lock:
            definition, assets, _ = read_package(self.catalog, source_id)
            document = yaml.load(definition, Loader=_LabYamlLoader)
            document["metadata"]["id"] = target_id
            document["metadata"]["name"] = title
            updated = json.dumps(document, indent=2, ensure_ascii=False)
            return summary(self.store.clone(target_id, title, updated, assets, uid))

    def edit_lab(self, lab_id, uid):
        if self.update_checker is None:
            raise ValueError("Installed-Lab updates are unavailable")
        with self.lifecycle_lock:
            definition, assets, digest = read_package(self.catalog, lab_id)
            document = yaml.load(definition, Loader=_LabYamlLoader)
            updated = json.dumps(document, indent=2, ensure_ascii=False)
            return summary(self.store.clone(lab_id, document["metadata"]["name"], updated, assets, uid,
                                            origin={"lab_id": lab_id, "digest": digest}))

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
        return entries

    def save(self, identifier, revision, definition, uid):
        return summary(self.store.change(identifier, uid, revision, definition=definition))

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
            result = update_catalog(self.catalog, target_id, snapshot, expected_catalog_digest, self.policy)
            self.store.set_origin(identifier, revision, uid, {"lab_id": target_id, "digest": result["catalog_digest"]})
            return {**report, **result, "updated": True}

    def publish(self, identifier, revision, digest, uid):
        with self.lifecycle_lock, self.store.lock:
            snapshot = self.store.get(identifier, uid, revision)
            if digest != snapshot["digest"]:
                raise DraftConflict("Reviewed digest does not match the draft contents")
            report = self._validate(snapshot)
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
            try:
                materialize(snapshot, stage)
                self.policy.validate(load_lab(stage / "lab.yaml"))
                for entry in stage.rglob("*"):
                    entry.chmod(0o755 if entry.is_dir() else 0o644)
                    if entry.is_file():
                        with entry.open("rb") as source:
                            os.fsync(source.fileno())
                stage.chmod(0o755)
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
            finally:
                if stage.exists():
                    shutil.rmtree(stage)
            return {**report, "published": True}
