"""Bounded JSON envelope for authenticated authoring calls, including bytes."""
import base64
import json

MAX_ENVELOPE = 48 * 1024 * 1024


def encode(value):
    return json.dumps(value, ensure_ascii=True, default=lambda item: {"$bytes": base64.b64encode(item).decode("ascii")} if isinstance(item, bytes) else _invalid())


def _invalid():
    raise ValueError("Unsupported authoring envelope value")


def decode(text):
    if not isinstance(text, str) or len(text.encode("utf-8")) > MAX_ENVELOPE:
        raise ValueError("Authoring envelope exceeds its limit")
    def restore(value):
        if "$bytes" in value:
            if set(value) != {"$bytes"} or not isinstance(value["$bytes"], str):
                raise ValueError("Invalid authoring bytes")
            return base64.b64decode(value["$bytes"], validate=True)
        return value
    try:
        return json.loads(text, object_hook=restore)
    except (RecursionError, UnicodeError) as error:
        raise ValueError("Invalid authoring envelope") from error
