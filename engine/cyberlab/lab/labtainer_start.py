from dataclasses import dataclass
from ipaddress import IPv4Address
import re

from .labtainer_source import fail, new_identity, records

SOURCE = "config/start.config"


@dataclass
class StartConfiguration:
    settings: dict
    networks: list
    nodes: dict
    terminals: list


def parse_start_config(text):
    settings, networks, nodes = {}, {}, {}
    network_ids, node_ids = {}, {}
    section, current = "global", settings
    declared = set()
    attachments, terminal_counts = [], {}

    for number, line in records(text, SOURCE):
        pieces = line.split(None, 1)
        tag, value = pieces[0].upper(), pieces[1].strip() if len(pieces) == 2 else ""
        if tag == "GLOBAL_SETTINGS":
            if value:
                fail(SOURCE, number, "GLOBAL_SETTINGS takes no argument")
            section, current = "global", settings
            continue
        if tag in {"NETWORK", "CONTAINER"}:
            if not value or len(value.split()) != 1:
                fail(SOURCE, number, f"{tag} requires one name")
            if tag == "CONTAINER" and (not re.fullmatch(r"[A-Za-z0-9_.-]+", value)
                                       or value in {"config", "instr_config", "dockerfiles", "docs"}):
                fail(SOURCE, number, "container name is invalid or conflicts with a reserved Lab directory")
            identities = network_ids if tag == "NETWORK" else node_ids
            identifier = new_identity(value, identities, SOURCE, number)
            section = "network" if tag == "NETWORK" else "container"
            current = {"id": identifier}
            if tag == "NETWORK":
                networks[value] = current
            else:
                current.update(networks=[], user={"name": "ubuntu", "uid": 1000, "gid": 1000,
                                                 "home": "/home/ubuntu", "shell": "/bin/bash"})
                nodes[value] = current
                terminal_counts[identifier] = 1
            continue
        if not value:
            fail(SOURCE, number, f"{tag} requires an argument")
        identity = (section, current.get("id", ""), tag)
        if identity in declared and tag != "ADD-HOST":
            fail(SOURCE, number, f"duplicate {tag} directive")
        declared.add(identity)
        if section == "global":
            fields = {"GRADE_CONTAINER": "grade_node", "HOST_HOME_XFER": "host_home_xfer",
                      "LAB_MASTER_SEED": "master_seed"}
            if tag in fields:
                settings[fields[tag]] = value.rstrip("/") if tag == "HOST_HOME_XFER" else value
            elif tag in {"CHECKWORK", "COLLECT_DOCS"} and value.lower() in {"yes", "no"}:
                settings["checkwork" if tag == "CHECKWORK" else "collect_documentation"] = value.lower() == "yes"
            else:
                fail(SOURCE, number, f"unsupported global directive {tag}")
        elif section == "network":
            if tag not in {"MASK", "GATEWAY"}:
                fail(SOURCE, number, f"unsupported network directive {tag}")
            current["subnet" if tag == "MASK" else "gateway"] = value
        elif tag == "USER":
            current["user"].update(name=value, home="/home/" + value)
        elif tag == "TERMINALS":
            if value not in {"0", "1", "2", "3", "4"}:
                fail(SOURCE, number, "TERMINALS supports 0..4; disabling terminal attachment is not implemented")
            terminal_counts[current["id"]] = int(value)
            if value != "0":
                current["terminal_count"] = int(value)
        elif tag == "TERMINAL_GROUP":
            current["terminal_group"] = value
        elif tag == "NAME_SERVER":
            current["dns"] = [value]
        elif tag == "CLONE":
            if value not in {"1", "2", "3", "4"}:
                fail(SOURCE, number, "CLONE supports 1..4")
            current["clone"] = int(value)
        elif tag == "ADD-HOST":
            if value.count(":") != 1:
                fail(SOURCE, number, "ADD-HOST network expansion is not implemented; host:IPv4 is required")
            hostname, address = value.split(":")
            hosts = current.setdefault("extra_hosts", {})
            if hostname in hosts:
                fail(SOURCE, number, "duplicate ADD-HOST name")
            hosts[hostname] = address
        elif tag in {"NO_PULL", "NO_PRIVILEGE"} and value.lower() == "yes":
            continue
        elif tag in {"X11", "MYSTUFF", "NO_GW"} and value.lower() == "no":
            continue
        else:
            attachments.append((current, pieces[0], value, number))

    for node, name, address, number in attachments:
        network = networks.get(name)
        if network is None:
            fail(SOURCE, number, "unsupported container directive or undefined network: " + name)
        if address.upper() == "AUTO" and network.get("subnet"):
            fail(SOURCE, number, "AUTO on an explicit subnet is not supported; no static address was invented")
        node["networks"].append(network["id"])
        if address.upper() != "AUTO":
            clean_address = address
            if address.upper().endswith("+CLONE"):
                clean_address = address[:address.upper().rfind("+CLONE")].strip()
            try:
                IPv4Address(clean_address)
            except ValueError:
                fail(SOURCE, number, "network attachment requires IPv4 or AUTO; clone/MAC suffixes are not supported")
            node.setdefault("addresses", {})[network["id"]] = address
    if "grade_node" in settings:
        grade = nodes.get(settings["grade_node"])
        if grade is None:
            fail(SOURCE, 1, "GRADE_CONTAINER references an undefined container")
        settings["grade_node"] = grade["id"]
    terminals = [node["id"] for node in nodes.values() if terminal_counts[node["id"]]]
    return StartConfiguration(settings, list(networks.values()), nodes, terminals)
