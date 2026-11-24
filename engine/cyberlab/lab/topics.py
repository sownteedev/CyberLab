from functools import lru_cache
from importlib.resources import files
import json


@lru_cache(maxsize=1)
def choices():
    schema = json.loads(files("cyberlab.schemas").joinpath("v1/lab.schema.json").read_text())
    entries = schema["properties"]["metadata"]["properties"]["tags"]["items"]["oneOf"]
    return tuple((entry["const"], entry["title"]) for entry in entries)


def catalog():
    return [{"id": identifier, "label": label} for identifier, label in choices()]


def require_tags(tags):
    allowed = dict(choices())
    if not isinstance(tags, (list, tuple)) or not tags:
        raise ValueError("Chọn ít nhất một chủ đề cho bài lab.")
    if len(tags) > len(allowed) or any(not isinstance(tag, str) or tag not in allowed for tag in tags):
        raise ValueError("Chọn chủ đề trong danh sách được hỗ trợ.")
    if len(set(tags)) != len(tags):
        raise ValueError("Chủ đề của bài lab không được trùng nhau.")
    return list(tags)
