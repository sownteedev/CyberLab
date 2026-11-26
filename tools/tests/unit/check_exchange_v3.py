#!/usr/bin/env python3
"""Isolated package codec checks; imported assets are never executed."""
import base64
import copy
from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path
import random
import struct
import sys
import tarfile
from types import SimpleNamespace
import unittest
import warnings
import zipfile
import zlib

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "engine"))

from cyberlab.lab import exchange
from cyberlab.lab.package import MAX_ASSET, MAX_DEFINITION, MAX_PACKAGE, MAX_PATHS, PackageLimit, digest

MAGIC = b"CYBLAB\r\n"
HEADER = struct.Struct(">8sBII32s")
VERIFIER = {"version": 1, "algorithm": "scrypt-131072-8-1",
            "salt": "12" * 16, "hash": "34" * 32}
LAB = SimpleNamespace(metadata=SimpleNamespace(id="sample", name="Sample", version="1"),
                      nodes=[SimpleNamespace(image="busybox:1.36")])
DEFINITION = 'metadata: {id: sample, name: "Th\u1eed nghi\u1ec7m"}\n'
ASSETS = {"assets": None, "assets/empty": None, "assets/zero": b"",
          "assets/start.sh": b"#!/bin/sh\nexit 97\n", "assets/bytes": bytes(range(256))}


def canonical(value):
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"),
                      allow_nan=False).encode("ascii")


def metadata(path, data):
    return {"path": path, "kind": "directory" if data is None else "file",
            "size": 0 if data is None else len(data),
            "sha256": "" if data is None else sha256(data).hexdigest()}


def envelope(definition=DEFINITION, assets=None, protection=None, version="cyberlab-lab/v3"):
    assets = ASSETS if assets is None else assets
    content = definition.encode("utf-8")
    manifest = {"format": version, "definition": {"path": "lab.yaml", "size": len(content),
                "sha256": sha256(content).hexdigest()},
                "lab": {"id": "sample", "name": "Sample", "version": "1"},
                "images": ["busybox:1.36"],
                "assets": [metadata(path, data) for path, data in sorted(assets.items())],
                "content_digest": digest(definition, assets)}
    if protection is not None:
        manifest["edit_protection"] = protection
    return {"definition": definition, "manifest": manifest,
            "assets": {path: None if data is None else base64.b64encode(data).decode("ascii")
                       for path, data in assets.items()}}


def frame(raw, *, compressed=None, size=None, checksum=None, version=3, magic=MAGIC):
    if compressed is None:
        compressor = zlib.compressobj(wbits=-15)
        compressed = compressor.compress(raw) + compressor.flush()
    return HEADER.pack(magic, version, len(compressed), len(raw) if size is None else size,
                       sha256(compressed).digest() if checksum is None else checksum) + compressed


def legacy(document, extra=()):
    output = BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("manifest.json", canonical(document["manifest"]))
        archive.writestr("lab.yaml", document["definition"].encode())
        for path, data in document["assets"].items():
            archive.writestr(path + "/" if data is None else path,
                             b"" if data is None else base64.b64decode(data))
        for path, data in extra:
            archive.writestr(path, data)
    return output.getvalue()


class ExchangeV3Checks(unittest.TestCase):
    def reject(self, data):
        with self.assertRaises(exchange.LabPackageError):
            exchange.read_package(data)

    def test_exports_binary_v3_and_independent_decoder(self):
        result = exchange.create_package(DEFINITION, ASSETS, LAB)
        self.assertEqual(exchange.FORMAT, "cyberlab-lab/v3")
        self.assertEqual(set(exchange.IMPORT_FORMATS),
                         {"cyberlab-lab/v1", "cyberlab-lab/v2", "cyberlab-lab/v3"})
        self.assertFalse(zipfile.is_zipfile(BytesIO(result)))
        with self.assertRaises(tarfile.ReadError):
            tarfile.open(fileobj=BytesIO(result))
        magic, version, compressed_size, raw_size, checksum = HEADER.unpack(result[:HEADER.size])
        self.assertEqual((magic, version, compressed_size), (MAGIC, 3, len(result) - HEADER.size))
        raw = zlib.decompress(result[HEADER.size:], -15)
        self.assertEqual((len(raw), sha256(result[HEADER.size:]).digest()), (raw_size, checksum))
        self.assertEqual(raw, canonical(envelope()))
        self.assertEqual(exchange.read_package(result), (DEFINITION, ASSETS, envelope()["manifest"]))
        self.assertEqual(result, exchange.create_package(DEFINITION, dict(reversed(list(ASSETS.items()))), LAB))

    def test_independent_encoder_and_protected_round_trips(self):
        for protection in (None, VERIFIER):
            with self.subTest(protection=protection is not None):
                document = envelope(protection=protection)
                self.assertEqual(exchange.read_package(frame(canonical(document))),
                                 (DEFINITION, ASSETS, document["manifest"]))
                encoded = exchange.create_package(DEFINITION, ASSETS, LAB, protection)
                self.assertEqual(exchange.read_package(encoded)[2], document["manifest"])

    def test_legacy_v1_v2_import_and_v3_reexport(self):
        for version, protection in (("cyberlab-lab/v1", None), ("cyberlab-lab/v2", VERIFIER)):
            document = envelope(version=version, protection=protection)
            definition, assets, manifest = exchange.read_package(legacy(document))
            self.assertEqual((definition, assets, manifest), (DEFINITION, ASSETS, document["manifest"]))
            exported = exchange.create_package(definition, assets, LAB, manifest.get("edit_protection"))
            self.assertEqual(exported[:8], MAGIC)

    def test_invalid_header_lengths_checksum_and_types(self):
        raw = canonical(envelope())
        encoded = frame(raw)
        variants = [None, "not bytes", b"", bytearray(encoded), encoded + b"x", encoded[:-1],
                    encoded[:20], frame(raw, version=2), frame(raw, magic=b"INVALID!"),
                    frame(raw, size=len(raw) - 1), frame(raw, size=len(raw) + 1),
                    frame(raw, size=0), frame(raw, checksum=b"\0" * 32),
                    b"\0" * (exchange.MAX_ARCHIVE + 1)]
        for variant in variants:
            with self.subTest(kind=type(variant).__name__, length=len(variant) if variant is not None else 0):
                self.reject(variant)

    def test_bad_deflate_streams_and_bombs(self):
        raw = canonical(envelope())
        encoded = frame(raw)
        compressed = encoded[HEADER.size:]
        for payload in (compressed + b"garbage", compressed + compressed, compressed[:-1],
                        b"not deflate", zlib.compress(raw)):
            self.reject(frame(raw, compressed=payload))
        self.reject(frame(b"A" * (5 * 1024 * 1024), size=64))
        self.reject(frame(b"A" * (5 * 1024 * 1024)))

    def test_duplicate_noncanonical_and_invalid_json(self):
        raw = canonical(envelope())
        variants = [b'{"assets":{},' + raw[1:], raw.replace(b'"format":', b'"format":"x","format":', 1),
                    b" " + raw, raw + b"\n", b"[]", b"null", b"\xff", b'{"x":NaN}',
                    b'{"x":' + b"[" * 2000 + b"0" + b"]" * 2000 + b"}"]
        for value in variants:
            self.reject(frame(value))

    def test_invalid_shapes_and_base64(self):
        for key, value in (("definition", None), ("definition", 123), ("assets", []),
                           ("manifest", []), ("unexpected", True)):
            document = envelope()
            document[key] = value
            self.reject(frame(canonical(document)))
        for value in (True, [], 42, "%%%", "YQ", "YQ==\n", "YR==", "\u00ff"):
            document = envelope()
            document["assets"]["assets/bytes"] = value
            self.reject(frame(canonical(document)))
        for value in ([], {}, None, True):
            for version in ("cyberlab-lab/v1", "cyberlab-lab/v3"):
                document = envelope(version=version)
                document["manifest"]["format"] = value
                self.reject(legacy(document) if version.endswith("v1") else frame(canonical(document)))

    def test_paths_conflicts_and_manifest_tampering(self):
        for path in ("../escape", "/assets/file", "assets/../file", "assets//file", "assets/file/",
                     "assets/\\file", "assets/\0file", "other/file", "assets/" + "a" * 65):
            self.reject(frame(canonical(envelope(assets={path: b"x"}))))
        self.reject(frame(canonical(envelope(assets={"assets/file": b"x", "assets/file/child": b"x"}))))
        for mutate in (
            lambda doc: doc["manifest"].update(format="cyberlab-lab/v1"),
            lambda doc: doc["manifest"].update(content_digest="0" * 64),
            lambda doc: doc["manifest"]["definition"].update(size=True),
            lambda doc: doc["manifest"]["assets"].append(doc["manifest"]["assets"][0]),
            lambda doc: doc["manifest"]["assets"][0].update(kind="symlink"),
            lambda doc: doc["manifest"]["assets"][0].update(size=False),
            lambda doc: doc["manifest"]["assets"][1].update(path="assets"),
            lambda doc: doc["manifest"]["definition"].update(sha256="0" * 64),
            lambda doc: doc["manifest"].update(edit_protection={"password": "plaintext"}),
            lambda doc: doc["manifest"].update(extra="x" * (64 * 1024)),
        ):
            document = envelope()
            mutate(document)
            self.reject(frame(canonical(document)))

    def test_content_limits_and_base64_headroom(self):
        definition = "\x01" * MAX_DEFINITION
        generator = random.Random(3)
        assets = {"assets/a": generator.randbytes(MAX_ASSET),
                  "assets/b": generator.randbytes(MAX_PACKAGE - MAX_ASSET - MAX_DEFINITION)}
        encoded = exchange.create_package(definition, assets, LAB)
        self.assertEqual(exchange.read_package(encoded)[:2], (definition, assets))
        for definition, assets in (("x" * (MAX_DEFINITION + 1), {}), ("\0", {}),
                                   ("", {"assets/a": b"x" * (MAX_ASSET + 1)}),
                                   ("x", {"assets/a": b"x" * MAX_ASSET, "assets/b": b"x" * MAX_ASSET}),
                                   ("", {f"assets/{index}": None for index in range(MAX_PATHS)})):
            self.reject(frame(canonical(envelope(definition, assets))))
            with self.assertRaises((ValueError, PackageLimit)):
                exchange.create_package(definition, assets, LAB)
        boundary = {f"assets/{index}": b"x" for index in range(MAX_PATHS - 1)}
        self.assertEqual(exchange.read_package(exchange.create_package("", boundary, LAB))[1], boundary)

    def test_legacy_validation_and_no_v3_zip_disguise(self):
        for version, protection in (("cyberlab-lab/v1", VERIFIER), ("cyberlab-lab/v2", None),
                                    ("cyberlab-lab/v3", None)):
            self.reject(legacy(envelope(version=version, protection=protection)))
        document = envelope(version="cyberlab-lab/v1")
        for extra in ((("assets/../escape", b"x"),), (("extra", b"x"),)):
            self.reject(legacy(document, extra))
        invalid = copy.deepcopy(document)
        invalid["manifest"]["content_digest"] = "0" * 64
        self.reject(legacy(invalid))
        self.reject(legacy(document) + b"trailing")
        self.reject(b"prefix" + legacy(document))
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            self.reject(legacy(document, (("assets/bytes", b"duplicate"),)))

    def test_native_and_labtainer_codecs_remain_separate(self):
        from cyberlab.lab.labtainer_archive import read_labtainer_archive

        native = exchange.create_package(DEFINITION, ASSETS, LAB)
        with self.assertRaises(ValueError):
            read_labtainer_archive(native)
        members = {"lesson/config/start.config": b"CONTAINER client\nX11 NO\n",
                   "lesson/client/start.sh": b"#!/bin/sh\nexit 97\n"}
        output = BytesIO()
        with zipfile.ZipFile(output, "w") as archive:
            for path, content in members.items():
                archive.writestr(path, content)
        archives = [output.getvalue()]
        for mode in ("w", "w:gz"):
            output = BytesIO()
            with tarfile.open(fileobj=output, mode=mode) as archive:
                for path, content in members.items():
                    info = tarfile.TarInfo(path)
                    info.size = len(content)
                    archive.addfile(info, BytesIO(content))
            archives.append(output.getvalue())
        for data in archives:
            self.assertEqual(read_labtainer_archive(data), members)
            self.reject(data)

    def test_random_round_trips_and_payload_corruption(self):
        generator = random.Random(20261125)
        for index in range(24):
            assets = {"assets/random": generator.randbytes(index * 97)}
            result = exchange.create_package(DEFINITION, assets, LAB)
            self.assertEqual(exchange.read_package(result)[:2], (DEFINITION, assets))
            position = generator.randrange(HEADER.size, len(result))
            damaged = bytearray(result)
            damaged[position] ^= 0x80
            self.reject(bytes(damaged))


if __name__ == "__main__":
    unittest.main(verbosity=2)
