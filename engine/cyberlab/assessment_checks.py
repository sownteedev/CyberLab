from hashlib import md5, sha256
import re
from time import monotonic

from cyberlab.regex_check import MAX_REGEX_SECONDS, RegexCheckError, group, search, select_line
from cyberlab.workspace import relative_path

MAX_TEXT_BYTES = 64 * 1024


def _remaining(regex_deadline):
    return MAX_REGEX_SECONDS if regex_deadline is None else regex_deadline - monotonic()


def _field_value(result, contents, regex_deadline):
    if result.field_type == "group":
        if result.line_type != "regex":
            raise RegexCheckError("Regex groups require a regex line selector")
        return group(result.line_id, contents, result.field_id,
                     timeout=_remaining(regex_deadline), by_line=True)
    if result.line_type is None:
        line = contents
    else:
        line = select_line(contents, result.line_type, result.line_id, timeout=_remaining(regex_deadline))
        if line is None:
            return None
    field_id = result.field_id
    if field_id == "ALL":
        return line
    if field_id == "LAST":
        occurrence = -1
    else:
        if type(field_id) is not int or field_id < 1:
            raise RegexCheckError("Field index must be a positive integer, ALL or LAST")
        occurrence = field_id - 1
    if result.field_type == "token":
        values = line.split()
    elif result.field_type == "parens":
        values = re.findall(r"\(([^()\n]*)\)", line)
    elif result.field_type == "quotes":
        values = [match.group(1) if match.group(1) is not None else match.group(2)
                  for match in re.finditer(r'"([^"\n]*)"|\'([^\'\n]*)\'', line)]
    elif result.field_type == "slash":
        values = re.findall(r"/([^/\n]*)/", line)
    else:
        raise RegexCheckError("Unsupported field type")
    return values[occurrence] if -len(values) <= occurrence < len(values) else None


def combined_status(statuses, mode="all"):
    if not statuses:
        return "NO_CRITERIA"
    decisive = "PASS" if mode == "any" else "FAIL"
    if decisive in statuses:
        return decisive
    if "ERROR" in statuses:
        return "ERROR"
    return "FAIL" if mode == "any" else "PASS"


def check_result(result, entries_by_node, errors, regex_deadline=None):
    base = {"id": result.id, "node": result.node, "path": result.path,
            "operator": result.operator, "description": result.description, "hint": result.hint}
    if result.node in errors:
        return {**base, "status": "ERROR", "message": errors[result.node]}
    entries = entries_by_node.get(result.node)
    if entries is None:
        return {**base, "status": "ERROR", "message": "Node workspace was not captured"}
    relative_path(result.path)
    entry = entries.get(result.path)
    if entry is None:
        return {**base, "status": "FAIL", "message": "Workspace path was not found"}
    if entry.kind not in {"file", "directory"}:
        return {**base, "status": "ERROR", "message": "Links and special files are not checked"}
    if result.operator == "exists":
        return {**base, "value": True, "status": "PASS", "message": "Workspace path exists"}
    if entry.kind != "file" or not isinstance(entry.data, bytes):
        return {**base, "status": "ERROR", "message": "This condition requires a regular file"}
    if result.operator == "size_less_than":
        passed = len(entry.data) < result.expected
        value = len(entry.data)
    elif result.operator == "size_equals":
        passed = len(entry.data) == result.expected
        value = len(entry.data)
    elif result.operator == "sha256_equals":
        value = sha256(entry.data).hexdigest()
        passed = value == result.expected.lower()
    elif result.operator == "md5_equals":
        value = md5(entry.data, usedforsecurity=False).hexdigest()
        passed = value == result.expected.lower()
    else:
        if len(entry.data) > MAX_TEXT_BYTES:
            return {**base, "status": "ERROR", "message": "Text checks are limited to 64 KiB"}
        try:
            contents = entry.data.decode("utf-8")
        except UnicodeError:
            return {**base, "status": "ERROR", "message": "Text checks require UTF-8 data"}
        if result.operator == "contains":
            value = result.expected in contents
            passed = value
        elif result.operator == "equals":
            value = contents
            passed = value == result.expected
        elif result.operator == "line_contains":
            value = any(result.expected in line for line in contents.splitlines())
            passed = value
        elif result.operator == "line_count_equals":
            value = len(contents.splitlines())
            passed = value == result.expected
        elif result.operator == "string_count_equals":
            if not isinstance(result.field_id, str) or not result.field_id:
                return {**base, "status": "ERROR", "message": "String count requires a non-empty search string"}
            value = contents.count(result.field_id)
            passed = value == result.expected
            return {**base, "value": value, "status": "PASS" if passed else "FAIL",
                    "message": "Condition satisfied" if passed else "Condition not yet satisfied"}
        elif result.operator == "field_equals":
            try:
                value = _field_value(result, contents, regex_deadline)
            except RegexCheckError as error:
                return {**base, "status": "ERROR", "message": str(error)}
            if value is None:
                return {**base, "status": "FAIL", "message": "Selected field was not found"}
            passed = value == result.expected
            return {**base, "value": value, "status": "PASS" if passed else "FAIL",
                    "message": "Condition satisfied" if passed else "Condition not yet satisfied"}
        elif result.operator == "regex":
            try:
                value = search(result.expected, contents, timeout=_remaining(regex_deadline))
                passed = value
            except RegexCheckError as error:
                return {**base, "status": "ERROR", "message": str(error)}
        else:
            return {**base, "status": "ERROR", "message": "Unsupported check operator"}
    return {**base, "value": value, "status": "PASS" if passed else "FAIL",
            "message": "Condition satisfied" if passed else "Condition not yet satisfied"}
