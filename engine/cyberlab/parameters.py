from __future__ import annotations

from hashlib import sha256
import re
from dataclasses import replace
from cyberlab.assessment_goals import INTEGER_OPERATORS, integer_value
from cyberlab.lab.assets import MAX_BYTES
from cyberlab.parameter_operations import _operation_value, apply_operations, seed_usage


TOKEN = re.compile(r"(?:\{\{param:([a-z][a-z0-9]*(?:-[a-z0-9]+)*)\}\}|\$\{PARAM:([a-z][a-z0-9]*(?:-[a-z0-9]+)*)\})")
MAX_PARAMETER_BYTES = 1024


def _value(parameter, supplied: dict[str, str], seed: str):
    raw = supplied.get(parameter.id, parameter.default)
    if raw is None:
        digest = sha256(f"{seed}:{parameter.id}".encode("utf-8")).digest()
        if parameter.type == "text":
            raw = f"{parameter.id}-{digest.hex()[:8]}"
        elif parameter.type == "integer":
            raw = int.from_bytes(digest[:4], "big") % 1000
        elif parameter.type == "boolean":
            raw = bool(digest[0] & 1)
        else:
            raw = parameter.choices[int.from_bytes(digest[:4], "big") % len(parameter.choices)]
    if parameter.type == "integer":
        if isinstance(raw, bool) or re.fullmatch(r"-?[0-9]+", str(raw)) is None or len(str(raw)) > 11:
            raise ValueError(f"Parameter {parameter.id} requires an integer")
        try:
            raw = int(raw)
        except (TypeError, ValueError):
            raise ValueError(f"Parameter {parameter.id} requires an integer") from None
        if not -(2 ** 31) <= raw < 2 ** 31:
            raise ValueError(f"Parameter {parameter.id} exceeds the integer range")
    elif parameter.type == "boolean":
        if isinstance(raw, bool):
            pass
        elif str(raw).lower() in {"true", "1", "yes"}:
            raw = True
        elif str(raw).lower() in {"false", "0", "no"}:
            raw = False
        else:
            raise ValueError(f"Parameter {parameter.id} requires true or false")
    else:
        raw = str(raw)
    if parameter.type == "choice" and raw not in parameter.choices:
        raise ValueError(f"Parameter {parameter.id} must be one of its declared choices")
    if len(str(raw).encode("utf-8")) > MAX_PARAMETER_BYTES or "\x00" in str(raw):
        raise ValueError(f"Parameter {parameter.id} exceeds its text limit or contains NUL")
    return raw


def resolve_parameters(lab, supplied: dict[str, str] | None, seed: str):
    supplied = supplied or {}
    if not isinstance(supplied, dict) or len(supplied) > 32 or any(
            not isinstance(key, str) or not isinstance(value, str) or len(value.encode("utf-8")) > MAX_PARAMETER_BYTES
            for key, value in supplied.items()):
        raise ValueError("Parameters require at most 32 bounded text values")
    known = {parameter.id for parameter in lab.parameters}
    unknown = set(supplied) - known
    if unknown:
        raise ValueError(f"Unknown Lab parameter: {sorted(unknown)[0]}")
    seed = (lab.settings.master_seed or "") + ":" + seed
    values = {parameter.id: _value(parameter, supplied, seed) for parameter in lab.parameters}
    seed_usage(lab.nodes)
    remaining_seed_bytes = MAX_BYTES

    def replace_token(match):
        key = match.group(1) or match.group(2)
        if key not in values:
            raise ValueError(f"Unknown Lab parameter reference: {key}")
        return str(values[key]).lower() if isinstance(values[key], bool) else str(values[key])

    def substitute(value):
        if not isinstance(value, str):
            return value

        return TOKEN.sub(replace_token, value)

    unique_pools = {}
    operation_values = {}
    operations = []
    for operation in lab.parameter_operations:
        token = substitute(operation.token) if operation.token else operation.token
        value = substitute(operation.value) if operation.value else operation.value
        op = replace(operation, token=token, value=value)
        generated = _operation_value(op, seed, unique_pools)
        values[operation.id] = generated
        operation_values[operation.id] = generated
        operations.append(op)

    def substitute_seed(entry):
        nonlocal remaining_seed_bytes
        if entry.data is None:
            return entry
        try:
            text = entry.data.decode("utf-8")
        except UnicodeError:
            remaining_seed_bytes -= len(entry.data)
            if remaining_seed_bytes < 0:
                raise ValueError("Parameter substitution exceeds the shared seed limit")
            return entry
        size = len(entry.data) + sum(len(replace_token(match).encode("utf-8")) - len(match.group(0).encode("utf-8"))
                                    for match in TOKEN.finditer(text))
        remaining_seed_bytes -= size
        if remaining_seed_bytes < 0:
            raise ValueError("Parameter substitution exceeds the shared seed limit")
        return replace(entry, data=substitute(text).encode("utf-8"))

    nodes = tuple(
        replace(
            node,
            hostname=substitute(node.hostname) if node.hostname else node.hostname,
            terminal_group=substitute(node.terminal_group) if node.terminal_group else node.terminal_group,
            terminal_title=substitute(node.terminal_title) if node.terminal_title else node.terminal_title,
            aliases=tuple(substitute(item) for item in node.aliases),
            wait_for=tuple(substitute(item) for item in node.wait_for),
            command=tuple(substitute(item) for item in node.command),
            seed=tuple(substitute_seed(entry) for entry in node.seed),
            addresses=tuple((network, substitute(address)) for network, address in node.addresses),
            dns=tuple(substitute(item) for item in node.dns),
            extra_hosts=tuple((substitute(hostname), substitute(address)) for hostname, address in node.extra_hosts),
        )
        for node in lab.nodes
    )
    networks = tuple(replace(network, subnet=substitute(network.subnet) if network.subnet else network.subnet,
                              gateway=substitute(network.gateway) if network.gateway else network.gateway)
                     for network in lab.networks)
    settings = replace(
        lab.settings,
        master_seed=substitute(lab.settings.master_seed) if lab.settings.master_seed else lab.settings.master_seed,
        grade_node=substitute(lab.settings.grade_node) if lab.settings.grade_node else lab.settings.grade_node,
    )
    documentation = replace(lab.documentation, content=substitute(lab.documentation.content)) if lab.documentation else None
    assessment = replace(lab.assessment, results=tuple(
        replace(result, expected=substitute(result.expected), description=substitute(result.description), hint=substitute(result.hint),
                field_id=substitute(result.field_id), line_id=substitute(result.line_id))
        for result in lab.assessment.results), goals=tuple(
        replace(goal, expected=substitute(goal.expected)) for goal in lab.assessment.goals))
    for goal in assessment.goals:
        if goal.goal_type == "compare" and goal.operator in INTEGER_OPERATORS and not goal.other:
            integer_value(goal.expected)
    resolved = replace(lab, nodes=nodes, networks=networks, settings=settings,
                       documentation=documentation, assessment=assessment,
                       parameter_operations=tuple(operations))
    final_lab, _ = apply_operations(resolved, seed, generated_values=operation_values)
    typed_values = {parameter.id: values[parameter.id] for parameter in lab.parameters}
    return final_lab, typed_values
