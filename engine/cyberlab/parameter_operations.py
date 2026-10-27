from dataclasses import replace
from hashlib import md5, sha256
from pathlib import PurePosixPath
import re

from cyberlab.lab.assets import AssetError, MAX_BYTES, MAX_ENTRIES, valid_path, validate_seed
from cyberlab.lab.models import SeedEntry

OPERATIONS = {"rand_replace", "rand_replace_unique", "hash_replace", "hash_create", "clone_replace"}

def validate_operations(lab):
    if len(lab.parameter_operations) > 64:
        raise ValueError("Parameter operations exceed the 64 operation limit")
    node_ids = {node.id for node in lab.nodes}
    identities = set()
    unique_counts = {}
    for operation in lab.parameter_operations:
        if not isinstance(operation.id, str) or len(operation.id) > 64 or not re.fullmatch(r"[a-z][a-z0-9]*(?:-[a-z0-9]+)*", operation.id):
            raise ValueError("Invalid parameter operation identity")
        if operation.id in identities:
            raise ValueError("Duplicate parameter operation identity")
        identities.add(operation.id)
        if not isinstance(operation.operation, str) or operation.operation not in OPERATIONS:
            raise ValueError("Unsupported parameter operation")
        if not isinstance(operation.node, str) or operation.node not in node_ids:
            raise ValueError("Parameter operation references an undefined node")
        if not valid_path(operation.path):
            raise ValueError("Parameter operation requires a safe seeded path")
        targets = operation.targets or ((operation.node, operation.path),)
        if len(targets) > 8:
            raise ValueError("Parameter operation supports at most eight targets")
        for target_node, target_path in targets:
            if not isinstance(target_node, str) or target_node not in node_ids:
                raise ValueError("Parameter operation target references an undefined node")
            if not valid_path(target_path):
                raise ValueError("Parameter operation target requires a safe seeded path")
        for text, limit in ((operation.token, 128), (operation.value, 1024)):
            if not isinstance(text, str) or len(text.encode("utf-8")) > limit or "\x00" in text:
                raise ValueError("Parameter operation text exceeds its limit or contains NUL")
        if operation.operation != "hash_create" and not operation.token:
            raise ValueError("Parameter replacement requires a non-empty token")
        if operation.operation in {"rand_replace", "rand_replace_unique"}:
            if any(type(number) is not int or not 0 <= number <= 2147483647
                   for number in (operation.lower, operation.upper, operation.step)):
                raise ValueError("Random replacement requires bounded integer values")
            if operation.lower > operation.upper or not 1 <= operation.step <= operation.upper - operation.lower + 1:
                raise ValueError("Random replacement requires an ordered range and valid step")
            if operation.operation == "rand_replace_unique":
                span = ((operation.upper - operation.lower) // operation.step) + 1
                pool = (operation.lower, operation.upper, operation.step)
                unique_counts[pool] = unique_counts.get(pool, 0) + 1
                if unique_counts[pool] > span:
                    raise ValueError(f"Unique random operations exceed available values in range: {operation.id}")

def seed_usage(nodes):
    try:
        for node in nodes:
            validate_seed(node.seed)
    except AssetError as error:
        raise ValueError(str(error)) from None
    size = sum(len(entry.data or b"") for node in nodes for entry in node.seed)
    count = sum(len(node.seed) for node in nodes)
    if size > MAX_BYTES or count > MAX_ENTRIES:
        raise ValueError("Initial files exceed the shared seed limit")
    return size, count

def _operation_value(operation, seed, unique_pools=None):
    if operation.operation == "clone_replace":
        return operation.value or "1"
    if operation.operation in {"hash_replace", "hash_create"}:
        return md5((seed + ":" + operation.value).encode("utf-8"), usedforsecurity=False).hexdigest()
    digest = sha256(f"{seed}:{operation.id}:{operation.value}".encode("utf-8")).digest()
    span = ((operation.upper - operation.lower) // operation.step) + 1
    if operation.operation == "rand_replace":
        return str(operation.lower + (int.from_bytes(digest[:8], "big") % span) * operation.step)
    if operation.operation == "rand_replace_unique":
        pool_key = (operation.lower, operation.upper, operation.step)
        if unique_pools is None:
            unique_pools = {}
        used = unique_pools.setdefault(pool_key, set())
        if len(used) >= span:
            raise ValueError(f"Unique random allocation exhausted available values in range: {operation.id}")
        start_index = int.from_bytes(digest[:8], "big") % span
        for offset in range(span):
            candidate = str(operation.lower + ((start_index + offset) % span) * operation.step)
            if candidate not in used:
                used.add(candidate)
                return candidate
        raise ValueError(f"Unique random allocation exhausted available values in range: {operation.id}")
    raise ValueError(f"Unsupported operation: {operation.operation}")

def apply_operations(lab, seed, generated_values=None):
    validate_operations(lab)
    size, count = seed_usage(lab.nodes)
    nodes = list(lab.nodes)
    node_indices = {node.id: index for index, node in enumerate(nodes)}
    unique_pools = {}
    if generated_values is None:
        generated_values = {}
    for operation in lab.parameter_operations:
        generated = generated_values.get(operation.id)
        if generated is None:
            generated = _operation_value(operation, seed, unique_pools)
            generated_values[operation.id] = generated
        targets = operation.targets or ((operation.node, operation.path),)
        for target_node, target_path in targets:
            node_index = node_indices[target_node]
            node = nodes[node_index]
            entries = {entry.path: entry for entry in node.seed}
            existing = entries.get(target_path)
            previous_size = len(existing.data or b"") if existing else 0
            if operation.operation == "hash_create":
                if existing is not None and existing.data is None:
                    raise ValueError(f"Parameter operation cannot replace a seeded directory: {target_path}")
                parent = PurePosixPath(target_path).parent
                while str(parent) != ".":
                    directory = entries.get(str(parent))
                    if directory is None or directory.data is not None:
                        raise ValueError(f"Parameter operation requires a seeded directory: {target_path}")
                    parent = parent.parent
                data = generated.encode("ascii")
                size += len(data) - previous_size
                count += existing is None
                if size > MAX_BYTES or count > MAX_ENTRIES:
                    raise ValueError("Parameter operation exceeds the shared seed limit")
            else:
                if existing is None or existing.data is None:
                    raise ValueError(f"Parameter operation target is not a seeded file: {target_path}")
                try:
                    contents = existing.data.decode("utf-8")
                except UnicodeError:
                    raise ValueError(f"Parameter operation target must be UTF-8: {target_path}") from None
                if operation.operation == "clone_replace":
                    replacement = str(node.clone_index if node.clone_index is not None else (operation.value or "1"))
                else:
                    replacement = generated
                occurrences = contents.count(operation.token)
                if not occurrences:
                    raise ValueError(f"Parameter token was not found in {target_path}")
                size += occurrences * (len(replacement.encode("utf-8")) - len(operation.token.encode("utf-8")))
                if size > MAX_BYTES:
                    raise ValueError("Parameter operation exceeds the shared seed limit")
                data = contents.replace(operation.token, replacement).encode("utf-8")
            entries[target_path] = SeedEntry(target_path, data)
            nodes[node_index] = replace(node, seed=tuple(entries.values()))
    return replace(lab, nodes=tuple(nodes)), generated_values
