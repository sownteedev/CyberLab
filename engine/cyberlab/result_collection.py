from hashlib import md5
import re
from string import Formatter
from time import monotonic

from cyberlab.regex_check import MAX_REGEX_SECONDS, MAX_REGEX_BUDGET_SECONDS, MAX_TEXT_BYTES, RegexCheckError, group, search, select_line

FIELD_SELECTORS = frozenset({"token", "parens", "quotes", "slash", "group", "search"})
TEXT_FIELDS = frozenset({"contains", "file_regex", "string_count", "command_count", "search"})
SIMPLE_FIELDS = frozenset({"line_count", "checksum", "size", "time_delim"})
TIMED_FIELDS = frozenset({"contains", "file_regex", "search"})
SEARCH_FORMATS = {"": r".+?", "d": r"[-+]?\d+", "f": r"[-+]?(?:\d+\.\d*|\.\d+)",
                  "w": r"\w+", "S": r"\S+", "s": r"\s+", "x": r"(?:0[xX])?[0-9a-fA-F]+"}

def search_pattern(template):
    pieces = []
    formats = []
    for literal, name, spec, conversion in Formatter().parse(template):
        pieces.append(re.escape(literal))
        if name is not None:
            if name != "" or conversion is not None or spec not in SEARCH_FORMATS:
                raise ValueError("Unsupported SEARCH format; use {}, {:d}, {:f}, {:w}, {:S}, {:s} or {:x}")
            formats.append(spec)
            pieces.append("(" + SEARCH_FORMATS[spec] + ")")
    if not formats or len(formats) > 16:
        raise ValueError("SEARCH requires 1 through 16 positional fields")
    return "".join(pieces), formats[0]

def validate_collection(result):
    kind = result.get("field_type")
    field = result.get("field_id")
    line = result.get("line_type")
    line_id = result.get("line_id")
    timestamp = result.get("timestamp_type", "file")
    if "expected" in result:
        raise ValueError("Collected results cannot define expected")
    if kind not in FIELD_SELECTORS | TEXT_FIELDS | SIMPLE_FIELDS | {"param"}:
        raise ValueError("Unknown collection field type")
    if timestamp != "file" and kind not in TIMED_FIELDS:
        raise ValueError("Log timestamps require CONTAINS, FILE_REGEX or SEARCH")
    if kind in SIMPLE_FIELDS and field is not None:
        raise ValueError("This field type does not accept Field ID")
    if kind in TEXT_FIELDS and (not isinstance(field, str) or not field.strip()):
        raise ValueError("This field type requires a non-empty Field ID")
    if kind == "search":
        search_pattern(field)
    if kind in {"param", "group"}:
        maximum = 32 if kind == "group" else 4096
        if type(field) is not int or not 0 <= field <= maximum:
            raise ValueError("Field ID must be an integer in the supported range")
    if kind in {"token", "parens", "quotes", "slash"}:
        if field not in {"ALL", "LAST"} and (type(field) is not int or not 1 <= field <= 4096):
            raise ValueError("Field ID must be positive, ALL or LAST")
    if kind in FIELD_SELECTORS:
        if line not in {"none", "line", "starts_with", "contains", "regex", "previous_starts_with"}:
            raise ValueError("Collection requires a line selector")
        if line == "none" and line_id is not None:
            raise ValueError("NONE does not accept Line ID")
        if line == "line" and (type(line_id) is not int or line_id < 1):
            raise ValueError("LINE requires a positive Line ID")
        if line not in {"none", "line"} and (not isinstance(line_id, str) or not line_id):
            raise ValueError("Line selector requires a non-empty Line ID")
        if kind == "group" and line != "regex":
            raise ValueError("GROUP requires a REGEX line selector")
        if timestamp != "file" and line not in {"none", "starts_with", "contains", "regex"}:
            raise ValueError("Log SEARCH requires NONE, STARTSWITH, HAVESTRING or REGEX")
    elif line is not None or line_id is not None:
        raise ValueError("This field type does not accept a line selector")

def remaining(deadline):
    return MAX_REGEX_SECONDS if deadline is None else deadline - monotonic()

def text_data(entry):
    if entry.kind != "file" or not isinstance(entry.data, bytes):
        raise ValueError("This condition requires a regular file")
    if len(entry.data) > MAX_TEXT_BYTES:
        raise ValueError("Text checks are limited to 64 KiB")
    try:
        return entry.data.decode("utf-8")
    except UnicodeError:
        raise ValueError("Text checks require UTF-8 data") from None

def scalar_value(result, contents, deadline):
    kind, field = result.field_type, result.field_id
    if kind == "contains":
        return field in contents
    if kind == "file_regex":
        return search(field, contents, timeout=remaining(deadline))
    if kind == "line_count":
        return len(contents.splitlines())
    if kind == "string_count":
        return contents.count(field)
    if kind == "command_count":
        count = 0
        for line in contents.splitlines():
            for prefix in ("time ", "sudo "):
                if line.startswith(prefix) and not field.startswith(prefix):
                    line = line[len(prefix):].strip()
            count += sum(part.strip().removeprefix("(").startswith(field)
                         for command in line.split(";") for part in command.split("|"))
        return count
    if kind == "param":
        lines = contents.splitlines()
        match = re.fullmatch(r"PROGRAM_ARGUMENTS\s*\((.*)\)\s*", lines[0]) if lines else None
        if match is None:
            raise ValueError("PARAM requires a PROGRAM_ARGUMENTS (...) capture header")
        if field == 0:
            program, marker, suffix = result.path.rpartition(".stdin")
            if not marker or (suffix and not re.fullmatch(r"\.\d{14}", suffix)):
                raise ValueError("PARAM 0 requires a program.stdin capture filename")
            return program
        arguments = match[1].split()
        return arguments[field - 1] if field <= len(arguments) else None
    if kind == "group":
        return group(result.line_id, contents, field, timeout=remaining(deadline), by_line=True)
    selected = contents if result.line_type == "none" else select_line(
        contents, result.line_type, result.line_id, timeout=remaining(deadline))
    if selected is None:
        return None
    if kind == "search":
        pattern, spec = search_pattern(field)
        value = group(pattern, selected, 1, timeout=remaining(deadline))
        if value is not None:
            if spec == "d":
                value = str(int(value))
            elif spec == "x":
                value = str(int(value, 16))
            elif spec == "f":
                value = str(float(value))
        return value
    if field == "ALL":
        return selected
    if kind == "token":
        values = selected.split()
    elif kind == "parens":
        values = re.findall(r"\(([^()\n]+)\)", selected)
    elif kind == "quotes":
        values = re.findall(r'"([^"\n]+)"', selected)
    else:
        values = selected.split("/")
    index = -1 if field == "LAST" else field - 1
    return values[index] if -len(values) <= index < len(values) else None

def collect_result(result, entries, base, deadline):
    from cyberlab.result_timestamps import log_instances, time_delimiters

    base = {**base, "field_type": result.field_type, "timestamp_type": result.timestamp_type or "file"}
    if deadline is None:
        deadline = monotonic() + MAX_REGEX_BUDGET_SECONDS
    try:
        if result.field_type == "time_delim":
            instances = time_delimiters(result.path, entries)
            return {**base, "status": "COLLECTED" if instances else "FAIL", "instances": instances,
                    "message": "Result instances collected" if instances else "No result instances found"}
        entry = entries.get(result.path)
        if entry is None:
            return {**base, "status": "FAIL", "message": "Workspace path was not found"}
        if entry.kind != "file" or not isinstance(entry.data, bytes):
            raise ValueError("This condition requires a regular file")
        if result.field_type == "size":
            value = len(entry.data)
        elif result.field_type == "checksum":
            value = md5(entry.data, usedforsecurity=False).hexdigest()
        else:
            contents = text_data(entry)
            if result.timestamp_type in {"log_ts", "log_range"}:
                instances = log_instances(result, contents, deadline)
                return {**base, "status": "COLLECTED" if instances else "FAIL", "instances": instances,
                        "message": "Result instances collected" if instances else "No result instances found"}
            value = scalar_value(result, contents, deadline)
        if value is None:
            return {**base, "status": "FAIL", "message": "Selected field was not found"}
        status = ("PASS" if value else "FAIL") if type(value) is bool else "COLLECTED"
        return {**base, "status": status, "value": value, "message": "Result collected"}
    except (ValueError, RegexCheckError, OverflowError) as error:
        return {**base, "status": "ERROR", "message": str(error)}
