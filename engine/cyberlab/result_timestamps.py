from datetime import datetime, timezone
import json
import re

from cyberlab.result_collection import scalar_value

MAX_INSTANCES = 128
MAX_INSTANCE_BYTES = 16384
LOG_TIMESTAMP = re.compile(r"^(\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(?:Z|[+-]\d{2}:\d{2}))(?=\s|$)")

def bounded_instances(instances):
    if len(instances) > MAX_INSTANCES or len(json.dumps(instances).encode("utf-8")) > MAX_INSTANCE_BYTES:
        raise ValueError("Result instances exceed 128 entries or 16 KiB")
    return instances

def time_delimiters(path, entries):
    pattern = re.compile(re.escape(path) + r"\.stdout\.(\d{14})$")
    timestamps = set()
    for name, entry in entries.items():
        match = pattern.fullmatch(name)
        if not match:
            continue
        if entry.kind != "file":
            raise ValueError("Time delimiters require regular capture files")
        timestamps.add(datetime.strptime(match[1], "%Y%m%d%H%M%S"))
        if len(timestamps) > MAX_INSTANCES:
            raise ValueError("Result instances exceed 128 entries or 16 KiB")
    ordered = sorted(timestamps)
    return bounded_instances([{"start": value.isoformat(),
        "end": ordered[index + 1].isoformat() if index + 1 < len(ordered) else None,
        "clock": "capture-local", "value": True} for index, value in enumerate(ordered)])

def log_instances(result, contents, deadline):
    instances = []
    first = previous = last = None
    matched_boundary = False
    for line in contents.splitlines():
        if not line.strip():
            continue
        match = LOG_TIMESTAMP.match(line)
        if match is None:
            raise ValueError("Log records require ISO-8601 timestamps with timezone")
        timestamp = datetime.fromisoformat(match[1]).astimezone(timezone.utc)
        if last is not None and timestamp < last:
            raise ValueError("Log timestamps must be in chronological order")
        last = timestamp
        if first is None:
            first = previous = timestamp
        value = scalar_value(result, line, deadline)
        if value is None or value is False:
            continue
        if result.timestamp_type == "log_ts":
            instances.append({"timestamp": timestamp.isoformat(), "value": value})
        elif timestamp > previous:
            instances.append({"start": previous.isoformat(), "end": timestamp.isoformat(), "value": True})
            previous = timestamp
            matched_boundary = True
        bounded_instances(instances)
    if result.timestamp_type == "log_range" and matched_boundary and last > previous:
        instances.append({"start": previous.isoformat(), "end": last.isoformat(), "value": True})
    return bounded_instances(instances)
