"""Bounded binary Lab package framing and canonical JSON/base64 transport."""
import base64
from hashlib import sha256
import json
import struct
import zlib

from cyberlab.archives import json_object
from .package import MAX_ASSET, MAX_DEFINITION, MAX_PACKAGE, MAX_PATHS, asset_path

MAGIC = b"CYBLAB\r\n"
VERSION = 3
HEADER = struct.Struct(">8sBII32s")
MAX_ARCHIVE = 4 * 1024 * 1024
MAX_MANIFEST = 64 * 1024
MAX_ENVELOPE = 4 * ((MAX_PACKAGE + 2) // 3) + 6 * MAX_DEFINITION + MAX_MANIFEST + MAX_PATHS * 256 + 1024


def canonical(value):
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"),
                      allow_nan=False).encode("ascii")


def encode(definition, assets, manifest):
    raw = canonical({"definition": definition, "manifest": manifest,
                     "assets": {path: None if data is None else base64.b64encode(data).decode("ascii")
                                for path, data in assets.items()}})
    if len(raw) > MAX_ENVELOPE:
        raise ValueError("Lab package JSON envelope exceeds its limit")
    compressor = zlib.compressobj(wbits=-15)
    compressed = compressor.compress(raw) + compressor.flush()
    if HEADER.size + len(compressed) > MAX_ARCHIVE:
        raise ValueError("Lab package archive exceeds 4 MiB")
    return HEADER.pack(MAGIC, VERSION, len(compressed), len(raw), sha256(compressed).digest()) + compressed


def decode(data):
    if not isinstance(data, bytes) or not HEADER.size < len(data) <= MAX_ARCHIVE:
        raise ValueError("Lab package binary size is invalid")
    magic, version, compressed_size, raw_size, checksum = HEADER.unpack_from(data)
    if magic != MAGIC or version != VERSION:
        raise ValueError("Unsupported Lab package binary header")
    if compressed_size != len(data) - HEADER.size or not 0 < raw_size <= MAX_ENVELOPE:
        raise ValueError("Lab package binary lengths are invalid")
    compressed = data[HEADER.size:]
    if sha256(compressed).digest() != checksum:
        raise ValueError("Lab package checksum does not match")
    inflater = zlib.decompressobj(wbits=-15)
    try:
        raw = inflater.decompress(compressed, raw_size + 1)
    except zlib.error as error:
        raise ValueError("Invalid Lab package DEFLATE stream") from error
    if (len(raw) != raw_size or not inflater.eof or inflater.unused_data or inflater.unconsumed_tail):
        raise ValueError("Lab package DEFLATE stream is truncated, trailing or oversized")
    document = json_object(raw, MAX_ENVELOPE)
    if set(document) != {"definition", "assets", "manifest"} or canonical(document) != raw:
        raise ValueError("Lab package envelope must be canonical structured JSON")
    definition = document["definition"]
    manifest = document["manifest"]
    encoded_assets = document["assets"]
    if not isinstance(definition, str) or len(definition.encode("utf-8")) > MAX_DEFINITION:
        raise ValueError("Lab package definition is missing or too large")
    if not isinstance(manifest, dict) or len(canonical(manifest)) > MAX_MANIFEST:
        raise ValueError("Lab package manifest is missing or too large")
    if not isinstance(encoded_assets, dict) or len(encoded_assets) > MAX_PATHS:
        raise ValueError("Lab package assets must be a bounded object")
    assets = {}
    total = len(definition.encode("utf-8"))
    for path, encoded in encoded_assets.items():
        if path != "assets" or encoded is not None:
            asset_path(path)
        if encoded is None:
            assets[path] = None
            continue
        if not isinstance(encoded, str) or len(encoded) > 4 * ((MAX_ASSET + 2) // 3):
            raise ValueError("Lab package base64 asset exceeds its limit")
        content = base64.b64decode(encoded, validate=True)
        total += len(content)
        if len(content) > MAX_ASSET or total > MAX_PACKAGE:
            raise ValueError("Lab package content exceeds its byte limit")
        if base64.b64encode(content).decode("ascii") != encoded:
            raise ValueError("Lab package assets require canonical base64")
        assets[path] = content
    return definition, assets, manifest
