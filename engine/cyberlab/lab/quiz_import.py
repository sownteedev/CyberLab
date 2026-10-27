import csv
from pathlib import PurePosixPath
import re

MAX_QUIZ_BYTES = 64 * 1024
MAX_ITEMS = 64
MAX_GROUPS = 8


def identifier(value):
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def records(text, source):
    if not isinstance(text, str) or len(text.encode("utf-8")) > MAX_QUIZ_BYTES or "\0" in text:
        raise ValueError(f"{source}: Quiz text exceeds 64 KiB or contains NUL")
    pending = ""
    first_line = 0
    for line_number, raw_line in enumerate(text.splitlines(), 1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if not pending:
            first_line = line_number
        pending += line[:-1] if line.endswith("\\") else line
        if line.endswith(("\\", ",")):
            continue
        try:
            row = next(csv.reader([pending], skipinitialspace=True, strict=True))
        except csv.Error:
            raise ValueError(f"{source}:{first_line}: Invalid quiz CSV record") from None
        yield first_line, [value.strip() for value in row]
        pending = ""
    if pending:
        raise ValueError(f"{source}:{first_line}: Unfinished quiz continuation")


def parse_quiz_file(text, *, prefix="q", source="quiz"):
    questions = []
    names = set()
    previous_questions = {}
    for line, row in records(text, source):
        location = f"{source}:{line}"
        if len(row) < 3 or not row[0] or not row[2]:
            raise ValueError(f"{location}: Quiz record needs an ID, type and text")
        original = row[0].lower()
        suffix = identifier(original)
        question_id = f"{prefix}-{suffix}"
        if not suffix or len(question_id) > 64 or question_id in names:
            raise ValueError(f"{location}: Duplicate or invalid normalized quiz ID")
        question_type = row[1].upper()
        if question_type == "PREFACE":
            if len(row) != 3 or len(row[2]) > 1024:
                raise ValueError(f"{location}: Preface needs one text field of at most 1024 characters")
            item = {"id": question_id, "type": "preface", "text": row[2]}
        else:
            if len(row[2]) > 512 or len(row) < 4:
                raise ValueError(f"{location}: Question requires text of at most 512 characters and an answer")
            item = {"id": question_id, "question": row[2],
                    "right_response": row[4] if len(row) > 4 else "",
                    "wrong_response": row[5] if len(row) > 5 else ""}
            if max(len(item["right_response"]), len(item["wrong_response"])) > 512:
                raise ValueError(f"{location}: Quiz feedback exceeds 512 characters")
            if question_type in {"TRUEFALSE", "TF"}:
                answer = row[3].upper()
                if len(row) > 7 or answer not in {"T", "F", "TRUE", "FALSE", "1", "0"}:
                    raise ValueError(f"{location}: TrueFalse requires a valid T/F answer and optional prerequisite")
                item.update(type="true_false", answer=answer in {"T", "TRUE", "1"})
                prerequisite = row[6].lower() if len(row) == 7 else ""
                if prerequisite:
                    if prerequisite not in previous_questions:
                        raise ValueError(f"{location}: Quiz prerequisite must name an earlier question in this file")
                    item["prerequisite"] = previous_questions[prerequisite]
            elif question_type in {"CHOICE", "MC"}:
                options = row[6:]
                if (not 2 <= len(options) <= 8 or len(set(options)) != len(options)
                        or any(not option or len(option) > 256 for option in options)
                        or not row[3].isascii() or not row[3].isdigit() or not 0 <= int(row[3]) < len(options)):
                    raise ValueError(f"{location}: Choice requires 2-8 options and a zero-based answer index")
                item.update(type="choice", options=options, answer=int(row[3]))
            else:
                raise ValueError(f"{location}: Unsupported quiz question type")
            previous_questions[original] = question_id
        names.add(question_id)
        questions.append(item)
        if len(questions) > MAX_ITEMS:
            raise ValueError(f"{source}: Quiz exceeds 64 items")
    if not questions:
        raise ValueError(f"{source}: Quiz contains no items")
    return questions


def convert_quizzes(file_map, directory):
    paths = sorted(path for path in file_map
                   if str(PurePosixPath(path).parent) == directory and path.endswith(".quiz"))
    if len(paths) > MAX_GROUPS:
        raise ValueError("Labtainer package exceeds eight quiz groups")
    groups = []
    names = set()
    total_bytes = 0
    total_items = 0
    for path in paths:
        data = file_map[path]
        total_bytes += len(data)
        if total_bytes > MAX_QUIZ_BYTES:
            raise ValueError("Labtainer quizzes exceed 64 KiB in total")
        name = PurePosixPath(path).stem
        group_id = "quiz-" + identifier(name)
        if not identifier(name) or len(group_id) > 40 or group_id in names:
            raise ValueError(f"{path}: Duplicate or invalid normalized quiz filename")
        names.add(group_id)
        try:
            text = data.decode("utf-8-sig")
        except UnicodeError:
            raise ValueError(f"{path}: Quiz must be UTF-8") from None
        items = parse_quiz_file(text, prefix=group_id, source=path)
        total_items += len(items)
        if total_items > MAX_ITEMS:
            raise ValueError("Labtainer quizzes exceed 64 items in total")
        groups.append({"id": group_id, "title": name, "items": items})
    return groups
