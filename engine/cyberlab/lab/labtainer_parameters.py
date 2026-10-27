from .labtainer_source import columns, fail, new_identity, records, workspace_target

SOURCE = "config/parameter.config"


def parse_parameter_config(text, source_nodes):
    operations, identities = [], {}
    for number, line in records(text, SOURCE):
        parts = columns(line)
        if len(parts) < 4:
            fail(SOURCE, number, "parameter requires identity, operation, targets and value")
        identifier = new_identity(parts[0], identities, SOURCE, number)
        kind = parts[1].upper()
        if kind not in {"RAND_REPLACE", "RAND_REPLACE_UNIQUE", "HASH_REPLACE", "HASH_CREATE", "CLONE_REPLACE"}:
            fail(SOURCE, number, "unsupported parameter operation " + kind)
        targets = [workspace_target(target.strip(), source_nodes, SOURCE, number) for target in parts[2].split(";")]
        if len({(target["node"], target["path"]) for target in targets}) != len(targets):
            fail(SOURCE, number, "duplicate parameter target")
        operation = {"id": identifier, "operation": kind.lower(), **targets[0]}
        if len(targets) > 1:
            operation["targets"] = targets
        if kind.startswith("RAND_"):
            if len(parts) not in {6, 7} or any(not value.isascii() or not value.isdecimal() for value in parts[4:]):
                fail(SOURCE, number, "random replacement requires decimal lower/upper bounds and optional step")
            step = int(parts[6]) if len(parts) == 7 else 1
            if step != 1:
                fail(SOURCE, number, "Labtainer random step semantics are not yet supported")
            operation.update(token=parts[3], lower=int(parts[4]), upper=int(parts[5]), step=step)
        elif kind == "CLONE_REPLACE":
            if len(parts) != 4:
                fail(SOURCE, number, "clone_replace operation requires identity, CLONE_REPLACE, targets and token")
            operation["token"] = parts[3]
        else:
            count = 4 if kind == "HASH_CREATE" else 5
            if len(parts) != count and not (len(parts) == count + 1 and parts[-1] == "32"):
                fail(SOURCE, number, "hash operation requires its exact arguments; truncated hashes are not supported")
            operation["value"] = parts[count - 1]
            if kind == "HASH_REPLACE":
                operation["token"] = parts[3]
        operations.append(operation)
    return operations
