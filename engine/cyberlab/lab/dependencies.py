def validate_node_dependencies(nodes):
    node_ids = {node["id"] if isinstance(node, dict) else node.id for node in nodes}
    owners = {}
    for node in nodes:
        identifier = node["id"] if isinstance(node, dict) else node.id
        aliases = node.get("aliases", []) if isinstance(node, dict) else node.aliases
        for alias in aliases:
            if alias in node_ids or alias in owners:
                raise ValueError(f"Network alias is already used: {alias}")
            owners[alias] = identifier
        waits = node.get("wait_for", []) if isinstance(node, dict) else node.wait_for
        for dependency in waits:
            if dependency not in node_ids:
                raise ValueError(f"Undefined wait_for node: {dependency}")
            if dependency == identifier:
                raise ValueError(f"Node cannot wait for itself: {identifier}")
    states = {}
    stack = []
    by_id = {
        (node["id"] if isinstance(node, dict) else node.id): node for node in nodes
    }

    def visit(identifier):
        state = states.get(identifier, 0)
        if state == 1:
            cycle = " -> ".join(stack + [identifier])
            raise ValueError(f"wait_for dependency cycle: {cycle}")
        if state == 2:
            return
        states[identifier] = 1
        stack.append(identifier)
        node = by_id[identifier]
        waits = node.get("wait_for", []) if isinstance(node, dict) else node.wait_for
        for dependency in waits:
            visit(dependency)
        stack.pop()
        states[identifier] = 2

    for identifier in by_id:
        visit(identifier)


def startup_order(nodes):
    by_id = {node.id: node for node in nodes}
    ordered = []
    visited = set()

    def visit(identifier):
        if identifier in visited:
            return
        node = by_id[identifier]
        for dependency in node.wait_for:
            visit(dependency)
        visited.add(identifier)
        ordered.append(node)

    for node in nodes:
        visit(node.id)
    return tuple(ordered)
