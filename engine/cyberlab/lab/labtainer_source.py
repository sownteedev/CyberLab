import re

from .assets import valid_path

MAX_CONFIG_BYTES = 64 * 1024


def fail(source, line, message):
    raise ValueError(f"{source}:{line}: {message}")


def text_file(files, path):
    data = files.get(path, b"")
    if not isinstance(data, bytes) or len(data) > MAX_CONFIG_BYTES:
        fail(path, 1, "configuration text exceeds 64 KiB")
    try:
        text = data.decode("utf-8")
    except UnicodeError:
        fail(path, 1, "configuration text must be UTF-8")
    if "\x00" in text:
        fail(path, 1, "configuration text contains NUL")
    return text


def records(text, source):
    for number, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        if len(line) > 4096:
            fail(source, number, "configuration line exceeds 4096 characters")
        if line and not line.startswith("#"):
            yield number, line


def normalize_id(text, default="item"):
    cleaned = re.sub(r"[^a-zA-Z0-9]+", "-", text).strip("-").lower()
    if not cleaned or not cleaned[0].isalpha():
        cleaned = "item-" + cleaned if cleaned else default
    return cleaned


def new_identity(raw, identities, source, line):
    if not raw or not re.fullmatch(r"[A-Za-z0-9_./-]+", raw):
        fail(source, line, "identity requires a non-empty name without whitespace or control characters")
    identifier = normalize_id(raw)
    if len(identifier) > 64 or identifier in identities.values() or raw in identities:
        fail(source, line, "duplicate, colliding or oversized identity")
    identities[raw] = identifier
    return identifier


def columns(value):
    return [part.strip() for part in re.split(r"\s+:\s+", value)]


def workspace_target(value, source_nodes, source, line):
    if ":" in value:
        name, path = value.split(":", 1)
        node = source_nodes.get(name)
    elif len(source_nodes) == 1:
        node = next(iter(source_nodes.values()))
        path = value
    else:
        fail(source, line, "a target in a multi-container Lab requires container:path")
    if node is None:
        fail(source, line, "target references an undefined container")
    if path == "start.config":
        fail(source, line, "start.config parameterization requires network-parameter support")
    if path.startswith("/"):
        home = node["user"]["home"] + "/"
        if not path.startswith(home):
            fail(source, line, "only paths within the configured user's home can be imported")
        path = path[len(home):]
    if not valid_path(path):
        fail(source, line, "workspace path cannot be represented without changing its name")
    return {"node": node["id"], "path": path}
