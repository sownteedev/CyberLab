import json
import subprocess
import sys

MAX_PATTERN_BYTES = 4096
MAX_TEXT_BYTES = 64 * 1024
MAX_REQUEST_BYTES = (MAX_PATTERN_BYTES + MAX_TEXT_BYTES) * 6 + 4096
MAX_RESULT_BYTES = MAX_TEXT_BYTES * 6 + 1024
MAX_REGEX_SECONDS = 1.0
MAX_REGEX_BUDGET_SECONDS = 5.0


class RegexCheckError(Exception):
    pass


def _validate_text(value, limit, label):
    if not isinstance(value, str):
        raise RegexCheckError(f"Regex {label} must be text")
    try:
        size = len(value.encode("utf-8"))
    except UnicodeError:
        raise RegexCheckError("Regex checks require valid UTF-8 text") from None
    if size > limit:
        raise RegexCheckError(f"Regex {label} exceeds its limit")


def _validate(pattern, contents):
    if not isinstance(pattern, str) or not isinstance(contents, str):
        raise RegexCheckError("Regex checks require text")
    try:
        pattern_size = len(pattern.encode("utf-8"))
        input_size = len(contents.encode("utf-8"))
    except UnicodeError:
        raise RegexCheckError("Regex checks require valid UTF-8 text") from None
    if pattern_size > MAX_PATTERN_BYTES:
        raise RegexCheckError("Regex patterns are limited to 4 KiB")
    if input_size > MAX_TEXT_BYTES:
        raise RegexCheckError("Regex input is limited to 64 KiB")


def _request(request, timeout=MAX_REGEX_SECONDS):
    if timeout <= 0:
        raise RegexCheckError("Regex checks exceeded their shared time budget")
    try:
        payload = json.dumps(request, ensure_ascii=True).encode("ascii")
    except (TypeError, ValueError):
        raise RegexCheckError("Regex worker request is invalid") from None
    if len(payload) > MAX_REQUEST_BYTES:
        raise RegexCheckError("Regex worker request exceeds its limit")
    try:
        completed = subprocess.run(
            [sys.executable, "-I", "-m", "cyberlab.regex_check"],
            input=payload, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            timeout=min(timeout, MAX_REGEX_SECONDS), check=False,
        )
    except subprocess.TimeoutExpired:
        raise RegexCheckError("Regex check exceeded its time limit") from None
    except OSError:
        raise RegexCheckError("Regex worker is unavailable") from None
    if completed.returncode != 0:
        raise RegexCheckError("Regex worker exceeded its limits or failed")
    if len(completed.stdout) > MAX_RESULT_BYTES:
        raise RegexCheckError("Regex worker returned an oversized response")
    try:
        response = json.loads(completed.stdout.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise RegexCheckError("Regex worker returned an invalid response") from None
    if not isinstance(response, dict) or response.get("status") == "limited":
        raise RegexCheckError("Regex check exceeded its resource limits")
    if response.get("status") == "invalid":
        raise RegexCheckError("Invalid regular expression")
    if response.get("status") != "ok":
        raise RegexCheckError("Regex worker returned an invalid response")
    return response


def search(pattern, contents, timeout=MAX_REGEX_SECONDS):
    _validate(pattern, contents)
    response = _request({"operation": "search", "pattern": pattern, "contents": contents}, timeout)
    if type(response.get("matched")) is not bool:
        raise RegexCheckError("Regex worker returned an invalid match")
    return response["matched"]


def _selected_value(response, flag, key):
    if type(response.get(flag)) is not bool:
        raise RegexCheckError("Regex worker returned an invalid selection")
    value = response.get(key)
    if value is not None:
        _validate_text(value, MAX_TEXT_BYTES, "result")
    return value if response[flag] else None

def group(pattern, contents, group_id, timeout=MAX_REGEX_SECONDS, *, by_line=False):
    _validate(pattern, contents)
    if type(group_id) is not int or not 0 <= group_id <= 32:
        raise RegexCheckError("Regex group must be an integer from 0 through 32")
    response = _request({"operation": "group", "pattern": pattern, "contents": contents,
                         "group": group_id, "by_line": by_line}, timeout)
    return _selected_value(response, "matched", "value")


def select_line(contents, line_type, line_id, timeout=MAX_REGEX_SECONDS):
    if line_type not in {"line", "starts_with", "contains", "regex", "previous_starts_with"}:
        raise RegexCheckError("Unsupported line selector")
    _validate_text(contents, MAX_TEXT_BYTES, "input")
    if line_type == "line" and (type(line_id) is not int or line_id < 1):
        raise RegexCheckError("Line number must be a positive integer")
    if line_type != "line":
        _validate_text(line_id, MAX_PATTERN_BYTES, "line selector")
    if line_type != "regex":
        lines = contents.splitlines()
        if line_type == "line":
            return lines[line_id - 1] if line_id <= len(lines) else None
        for index, line in enumerate(lines):
            matched = line_id in line if line_type == "contains" else line.startswith(line_id)
            if matched:
                if line_type == "previous_starts_with":
                    return lines[index - 1] if index else None
                return line
        return None
    response = _request({"operation": "select_line", "contents": contents,
                         "line_type": line_type, "line_id": line_id}, timeout)
    return _selected_value(response, "found", "line")


def _worker():
    import re
    import resource

    for limit, maximum in (
        (resource.RLIMIT_AS, 128 * 1024 * 1024),
        (resource.RLIMIT_CPU, 1),
        (resource.RLIMIT_CORE, 0),
        (resource.RLIMIT_FSIZE, 0),
    ):
        soft, hard = resource.getrlimit(limit)
        ceiling = maximum if hard == resource.RLIM_INFINITY else min(maximum, hard)
        ceiling = ceiling if soft == resource.RLIM_INFINITY else min(ceiling, soft)
        resource.setrlimit(limit, (ceiling, ceiling))
    response = {"status": "ok"}
    try:
        request = sys.stdin.buffer.read(MAX_REQUEST_BYTES + 1)
        if len(request) > MAX_REQUEST_BYTES:
            raise RegexCheckError("Request exceeds its limit")
        request = json.loads(request)
        operation = request.get("operation")
        contents = request.get("contents")
        _validate_text(contents, MAX_TEXT_BYTES, "input")
        if operation == "search":
            pattern = request.get("pattern")
            _validate(pattern, contents)
            response["matched"] = re.search(pattern, contents) is not None
        elif operation == "group":
            pattern = request.get("pattern")
            group_id = request.get("group")
            _validate(pattern, contents)
            if type(group_id) is not int or not 0 <= group_id <= 32:
                raise RegexCheckError("Regex group must be an integer from 0 through 32")
            compiled = re.compile(pattern)
            if request.get("by_line", False):
                match = next((match for line in contents.splitlines()
                              if (match := compiled.search(line)) is not None), None)
            else:
                match = compiled.search(contents)
            response["matched"] = match is not None
            if match is not None:
                try:
                    response["value"] = match.group(group_id)
                except IndexError:
                    response["status"] = "invalid"
        elif operation == "select_line":
            line_type = request.get("line_type")
            line_id = request.get("line_id")
            if line_type != "regex":
                raise RegexCheckError("Unsupported line selector")
            _validate(line_id, contents)
            compiled = re.compile(line_id)
            selected = next((line for line in contents.splitlines() if compiled.search(line)), None)
            response["found"] = selected is not None
            if selected is not None:
                response["line"] = selected
        else:
            raise RegexCheckError("Unsupported regex worker operation")
    except re.error:
        response = {"status": "invalid"}
    except (MemoryError, RecursionError):
        response = {"status": "limited"}
    except (ValueError, TypeError, RegexCheckError):
        response = {"status": "invalid"}
    output = json.dumps(response, ensure_ascii=True, separators=(",", ":")).encode("ascii")
    if len(output) > MAX_RESULT_BYTES:
        output = b'{"status":"limited"}'
    sys.stdout.buffer.write(output)
    sys.stdout.buffer.flush()


if __name__ == "__main__":
    _worker()
