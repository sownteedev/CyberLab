from ipaddress import IPv4Address, IPv4Network
from pathlib import Path
import sys

from . import RuntimeFailure


def read_host_subnets(path=Path("/proc/net/route")):
    try:
        with path.open("r", encoding="ascii") as source:
            content = source.read(1024 * 1024 + 1)
        lines = content.splitlines()
        if len(content) > 1024 * 1024 or not lines or lines[0].split()[:2] != ["Iface", "Destination"]:
            raise ValueError("Invalid route table")
        subnets = []
        for line in lines[1:]:
            if not line.strip():
                continue
            columns = line.split()
            if len(columns) < 8:
                raise ValueError("Invalid route entry")
            if not int(columns[3], 16) & 1:
                continue
            address = IPv4Address(int(columns[1], 16).to_bytes(4, sys.byteorder))
            mask = IPv4Address(int(columns[7], 16).to_bytes(4, sys.byteorder))
            subnet = IPv4Network(f"{address}/{mask}", strict=False)
            if subnet.prefixlen:
                subnets.append(subnet)
        return tuple(subnets)
    except (OSError, UnicodeError, ValueError, OverflowError):
        raise RuntimeFailure("Cannot inspect the VM's IPv4 routes before allocating a static subnet") from None
