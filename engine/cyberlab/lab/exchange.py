from hashlib import sha256
import struct

from cyberlab.archives import json_object, read_zip
from .package import MAX_DEFINITION, MAX_PACKAGE, MAX_PATHS, PackageLimit, check_package, digest
from . import exchange_v3
from .exchange_v3 import MAX_ARCHIVE, MAX_MANIFEST

FORMAT = "cyberlab-lab/v3"
LEGACY_FORMAT = "cyberlab-lab/v1"
PROTECTED_FORMAT = "cyberlab-lab/v2"
IMPORT_FORMATS = frozenset({LEGACY_FORMAT, PROTECTED_FORMAT, FORMAT})
MANIFEST = "manifest.json"
DEFINITION = "lab.yaml"


class LabPackageError(ValueError):
    pass


def _metadata(path, data):
    return {"path": path, "kind": "directory" if data is None else "file",
            "size": 0 if data is None else len(data),
            "sha256": "" if data is None else sha256(data).hexdigest()}


def create_package(definition, assets, lab, edit_protection=None):
    assets = dict(assets)
    check_package(definition, assets)
    definition_bytes = definition.encode("utf-8")
    manifest = {
        "format": FORMAT,
        "definition": {"path": DEFINITION, "size": len(definition_bytes),
                       "sha256": sha256(definition_bytes).hexdigest()},
        "lab": {"id": lab.metadata.id, "name": lab.metadata.name, "version": lab.metadata.version},
        "images": sorted({node.image for node in lab.nodes if node.image is not None}),
        "assets": [_metadata(path, data) for path, data in sorted(assets.items())],
        "content_digest": digest(definition, assets),
    }
    if edit_protection is not None:
        from cyberlab.authoring.protection import validate_verifier
        manifest["edit_protection"] = validate_verifier(edit_protection)
    manifest_bytes = exchange_v3.canonical(manifest)
    if len(manifest_bytes) > MAX_MANIFEST:
        raise LabPackageError("Lab package manifest exceeds its limit")
    try:
        return exchange_v3.encode(definition, assets, manifest)
    except ValueError as error:
        raise LabPackageError(str(error)) from None

def _legacy_entries(data):
    end = struct.Struct("<4s4H2IH")
    lower = max(0, len(data) - end.size - 65535)
    position = data.rfind(b"PK\x05\x06", lower)
    while position >= lower:
        if position + end.size <= len(data):
            _, disk, directory_disk, disk_count, count, size, offset, comment = end.unpack_from(data, position)
            if (position + end.size + comment == len(data) and disk == directory_disk == 0
                    and disk_count == count and offset + size == position):
                return read_zip(data, max_archive=MAX_ARCHIVE, max_entries=MAX_PATHS + 2,
                                max_content=MAX_PACKAGE + MAX_MANIFEST)
        position = data.rfind(b"PK\x05\x06", lower, position)
    raise ValueError("Legacy Lab ZIP has invalid lengths or trailing data")


def read_package(data):
    try:
        if not isinstance(data, bytes) or not data or len(data) > MAX_ARCHIVE:
            raise ValueError("Lab package exceeds 4 MiB or is empty")
        if data.startswith(exchange_v3.MAGIC):
            definition, entries, manifest = exchange_v3.decode(data)
            definition_bytes = definition.encode("utf-8")
            allowed_formats = {FORMAT}
        elif data.startswith(b"PK\x03\x04"):
            entries = _legacy_entries(data)
            manifest = json_object(entries.pop(MANIFEST, None), MAX_MANIFEST)
            definition_bytes = entries.pop(DEFINITION, None)
            allowed_formats = {LEGACY_FORMAT, PROTECTED_FORMAT}
        else:
            raise ValueError("Unsupported Lab package container")
        if not isinstance(manifest.get("format"), str) or manifest["format"] not in allowed_formats:
            raise ValueError("Unsupported Lab package format")
        if manifest["format"] == PROTECTED_FORMAT or "edit_protection" in manifest:
            if manifest["format"] == LEGACY_FORMAT:
                raise ValueError("Editing protection requires Lab package v2 or v3")
            from cyberlab.authoring.protection import validate_verifier
            validate_verifier(manifest.get("edit_protection"))
        if not isinstance(definition_bytes, bytes) or len(definition_bytes) > MAX_DEFINITION:
            raise ValueError("Lab package definition is missing or too large")
        definition_meta = manifest.get("definition")
        expected_definition = {"path": DEFINITION, "size": len(definition_bytes),
                               "sha256": sha256(definition_bytes).hexdigest()}
        if (not isinstance(definition_meta, dict) or type(definition_meta.get("size")) is not int
                or definition_meta != expected_definition):
            raise ValueError("Lab definition integrity check failed")
        definition = definition_bytes.decode("utf-8")
        check_package(definition, entries)
        declared = manifest.get("assets")
        if not isinstance(declared, list) or len(declared) != len(entries):
            raise ValueError("Lab package contains undeclared or missing assets")
        paths = set()
        for item in declared:
            if not isinstance(item, dict) or not isinstance(item.get("path"), str):
                raise ValueError("Lab package asset metadata is invalid")
            path = item["path"]
            if path in paths or path not in entries:
                raise ValueError("Lab package asset is missing or duplicated")
            paths.add(path)
            if type(item.get("size")) is not int or item != _metadata(path, entries[path]):
                raise ValueError("Lab asset integrity check failed")
        if manifest.get("content_digest") != digest(definition, entries):
            raise ValueError("Lab package content digest does not match")
        return definition, entries, manifest
    except (ValueError, UnicodeError, PackageLimit, RecursionError) as error:
        raise LabPackageError(str(error)) from None
