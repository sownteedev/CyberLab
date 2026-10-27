import re

from .labtainer_source import columns, fail, new_identity, records, workspace_target


def parse_results_config(text, source_nodes):
    source = "instr_config/results.config"
    results, identities = [], {}
    for number, line in records(text, source):
        if "=" not in line:
            fail(source, number, "result requires identity = definition")
        name, definition = line.split("=", 1)
        identifier = new_identity(name.strip(), identities, source, number)
        parts = columns(definition)
        if len(parts) != 3 or parts[1].upper() not in {"CONTAINS", "FILE_REGEX"}:
            fail(source, number, "only whole-workspace-file CONTAINS and FILE_REGEX results can be imported; extraction/event results need a separate evidence model")
        target = workspace_target(parts[0], source_nodes, source, number)
        if target["path"].endswith((".stdout", ".stdin")):
            fail(source, number, "program stdin/stdout archives are not workspace snapshot files")
        if re.search(r"\$[A-Za-z_]", parts[2]):
            fail(source, number, "parameterized result selectors are not yet converted")
        results.append({"id": identifier, **target,
                        "operator": "contains" if parts[1].upper() == "CONTAINS" else "regex",
                        "expected": parts[2]})
    return results, identities


def parse_goals_config(text, result_ids):
    source = "instr_config/goals.config"
    goals, identities = [], {}
    description = ""
    for number, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        if line.startswith("#DOC:"):
            description = line[5:].strip()
            continue
        if not line or line.startswith("#"):
            continue
        if len(line) > 4096 or "=" not in line:
            fail(source, number, "goal requires a bounded identity = definition")
        name, definition = line.split("=", 1)
        previous = {**result_ids, **identities}
        identifier = new_identity(name.strip(), identities, source, number)
        if identifier in result_ids.values():
            fail(source, number, "goal and result identities collide")
        parts = columns(definition)
        if len(parts) != 2 or parts[0].lower() != "boolean":
            fail(source, number, "only boolean snapshot goals can be imported; matchany/matchlast/matchacross, counts and temporal goals require event evidence")

        def reference(match):
            token = match.group(0)
            if token.lower() in {"and", "or", "not", "and_not", "or_not", "true", "false"}:
                return token.lower()
            if token not in previous:
                fail(source, number, "goal references an unknown or later result/goal")
            return previous[token]

        expression = re.sub(r"[A-Za-z0-9_.-]+", reference, parts[1])
        goals.append({"id": identifier, "type": "boolean", "expression": expression,
                      "description": description})
        description = ""
    return goals
