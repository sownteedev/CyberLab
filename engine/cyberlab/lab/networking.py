from ipaddress import IPv4Address, IPv4Network
import re

PRIVATE_NETWORKS = tuple(IPv4Network(value) for value in ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16"))
MAX_TERMINALS = 8
HOSTNAME = re.compile(r"^[a-z][a-z0-9.-]{0,62}$")


def bridge_gateway(network):
    return network.gateway or str(IPv4Network(network.subnet).network_address + 1)


def validate_networking(lab):
    networks = {network.id: network for network in lab.networks}
    subnets = {}
    for network in lab.networks:
        if network.subnet is None:
            if network.gateway is not None:
                raise ValueError("A bridge gateway requires an explicit subnet")
            continue
        subnet = IPv4Network(network.subnet, strict=True)
        if not 16 <= subnet.prefixlen <= 30 or not any(subnet.subnet_of(private) for private in PRIVATE_NETWORKS):
            raise ValueError("Subnets must be canonical RFC1918 IPv4 networks with prefixes /16 through /30")
        gateway = IPv4Address(bridge_gateway(network))
        if gateway not in subnet or gateway in (subnet.network_address, subnet.broadcast_address):
            raise ValueError("Bridge gateway must be a usable address within its subnet")
        if any(subnet.overlaps(existing) for existing in subnets.values()):
            raise ValueError("Lab subnets must not overlap")
        subnets[network.id] = subnet

    assigned = set()
    for node in lab.nodes:
        if len(node.extra_hosts) > 8 or len(set(node.extra_hosts)) != len(node.extra_hosts):
            raise ValueError("At most eight distinct extra hosts are allowed")
        for hostname, address in node.extra_hosts:
            if not HOSTNAME.fullmatch(hostname) or hostname.endswith("."):
                raise ValueError("Extra host names must be safe DNS labels")
            if not any(IPv4Address(address) in private for private in PRIVATE_NETWORKS):
                raise ValueError("Extra host addresses must be RFC1918 IPv4 addresses")
        if not 64 <= node.resources.memory_mb <= 512:
            raise ValueError("Node memory must be between 64 and 512 MiB")
        if not 100 <= node.resources.cpu_millicores <= 1000:
            raise ValueError("Node CPU must be between 100 and 1000 millicores")
        if type(node.terminal_count) is not int or not 1 <= node.terminal_count <= 4:
            raise ValueError("Each node supports 1 through 4 terminal slots")
        addresses = dict(node.addresses)
        if len(addresses) != len(node.addresses) or not addresses.keys() <= set(node.networks):
            raise ValueError("Static addresses must uniquely reference attached networks")
        for network_id in node.networks:
            if network_id not in networks:
                raise ValueError("Node references an undefined network")
            if (network_id in subnets) != (network_id in addresses):
                raise ValueError("Every attachment to an explicit subnet requires a static address; automatic networks cannot have static addresses")
        for network_id, value in addresses.items():
            address = IPv4Address(value)
            subnet = subnets[network_id]
            if address not in subnet or address in (subnet.network_address, subnet.broadcast_address, IPv4Address(bridge_gateway(networks[network_id]))):
                raise ValueError("Node address must be usable in its subnet and cannot equal the bridge gateway")
            key = (network_id, str(address))
            if key in assigned:
                raise ValueError("Duplicate node address on a network")
            assigned.add(key)

    for node in lab.nodes:
        if len(node.dns) > 3 or len(set(node.dns)) != len(node.dns):
            raise ValueError("At most three distinct internal DNS servers are allowed")
        for value in node.dns:
            address = str(IPv4Address(value))
            if not any((network_id, address) in assigned for network_id in node.networks):
                raise ValueError("DNS servers must be statically addressed nodes on an attached Lab network")
    if sum(node.terminal_count for node in lab.nodes) > MAX_TERMINALS:
        raise ValueError("A Lab supports at most eight terminal slots in total")


def overlapping_subnets(first, second):
    return any(IPv4Network(left.subnet).overlaps(IPv4Network(right.subnet))
               for left in first.networks if left.subnet
               for right in second.networks if right.subnet)
