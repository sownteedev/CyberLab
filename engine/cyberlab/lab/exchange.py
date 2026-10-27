from hashlib import sha256
from io import BytesIO
import json
import stat
import zipfile

from cyberlab.archives import json_object, read_zip
from .package import MAX_DEFINITION, MAX_PACKAGE, MAX_PATHS, check_package, digest

FORMAT = "cyberlab-lab/v1"
MANIFEST = "manifest.json"
DEFINITION = "lab.yaml"
MAX_ARCHIVE = 4 * 1024 * 1024
MAX_MANIFEST = 64 * 1024


class LabPackageError(ValueError):
    pass


def _metadata(path, data):
    return {"path": path, "kind": "directory" if data is None else "file",
            "size": 0 if data is None else len(data),
            "sha256": "" if data is None else sha256(data).hexdigest()}


def create_package(definition, assets, lab):
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
    manifest_bytes = json.dumps(manifest, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode()
    if len(manifest_bytes) > MAX_MANIFEST:
        raise LabPackageError("Lab package manifest exceeds its limit")
    output = BytesIO()
    with zipfile.ZipFile(output, "w", allowZip64=False) as archive:
        for path, data in [(MANIFEST, manifest_bytes), (DEFINITION, definition_bytes), *sorted(assets.items())]:
            info = zipfile.ZipInfo(path + "/" if data is None else path, (1980, 1, 1, 0, 0, 0))
            info.create_system = 3
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = ((stat.S_IFDIR | 0o755) if data is None else (stat.S_IFREG | 0o644)) << 16
            archive.writestr(info, b"" if data is None else data)
    result = output.getvalue()
    if len(result) > MAX_ARCHIVE:
        raise LabPackageError("Lab package archive exceeds 4 MiB")
    return result


def read_package(data):
    try:
        entries = read_zip(data, max_archive=MAX_ARCHIVE, max_entries=MAX_PATHS + 2,
                           max_content=MAX_PACKAGE + MAX_MANIFEST)
        manifest = json_object(entries.pop(MANIFEST, None), MAX_MANIFEST)
        if manifest.get("format") != FORMAT:
            raise ValueError("Unsupported Lab package format")
        definition_bytes = entries.pop(DEFINITION, None)
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
    except (ValueError, UnicodeError) as error:
        raise LabPackageError(str(error)) from None
