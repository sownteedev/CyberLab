# Network and Per-Node Terminal Configuration (Development Source)

This implements the first restricted slice inspired by the supplied network
and container configuration screenshots. The schema, draft editor, engine,
Docker adapter, shared D-Bus contract and CLI use the same configuration.
No Quickshell, new public transport, image build or host installation is added.
No release version or existing bundle is changed by this development step.

## Example Definition

Use this definition in your own draft; it is not installed as another sample
Lab. The selected image must already be approved and preloaded. These default
BusyBox nodes use `nobody`, not the Ubuntu VM's student account.

```yaml
apiVersion: cyberlab.ptit/v1
kind: Lab
metadata:
  id: my-network-lab
  name: My network lab
  version: "1.0.0"
networks:
  - id: lan
    subnet: 10.231.20.0/24
    gateway: 10.231.20.1
nodes:
  - id: client
    hostname: workstation
    image: busybox:1.37.0
    command: [sleep, "3600"]
    networks: [lan]
    addresses:
      lan: 10.231.20.2
    terminal_count: 2
  - id: server
    hostname: server
    image: busybox:1.37.0
    command: [sleep, "3600"]
    networks: [lan]
    addresses:
      lan: 10.231.20.3
    terminal_count: 1
terminals: [client, server]
```

Starting this Lab creates two containers and one internal bridge, then asks
Konsole to open three windows: two independent shells in `client`, one in
`server`. It does not create a container per terminal. The existing `user`,
`files`, and `documentation` properties can be added as before.

For a node on multiple networks, keep `networks: [lan, backend]` and provide an
`addresses` entry for each attached explicit subnet. Interface names/order and
default-route selection across multiple networks are not a public guarantee.

## Network Validation and Safety

- Old `{id: lan}` networks stay automatic. Old `networks: [lan]` attachments
  and all shipped Labs continue to work unchanged.
- Explicit subnets must be canonical IPv4 CIDRs inside RFC1918 ranges, with
  prefix /16 through /30. Public, loopback, link-local, multicast, IPv6,
  host-bit CIDRs, duplicate addresses and overlapping Lab subnets are rejected.
- `gateway` is optional and requires a subnet. It defaults to the first usable
  address. It reserves the Docker bridge's address, **not** a Lab router and
  **not** an Internet egress setting. It cannot be assigned to a node.
- Every attachment to an explicit subnet needs an explicit usable node IP.
  Mixing automatic and static allocation on the same explicit subnet is not
  supported. Automatic networks cannot have `addresses` entries.
- Networks remain `internal=True`, without published host ports, host network
  mode, devices, new capabilities or privileged containers.
- Before allocating explicit networks, the Docker adapter checks existing
  Docker IPAM subnets and active non-default routes in `/proc/net/route`.
  Missing/malformed route data fails closed. This is a read-only check of the
  Linux main IPv4 route table and needs no netlink permission or subprocess.
- This does not inspect all policy-routing tables, VPN namespaces or VMware's
  outer network. Administrator changes can race preflight; Docker errors still
  fail the start and the engine attempts Session-scoped cleanup. It is not a
  general guarantee against all host/container communication.

## Concurrent Sessions with Static Subnets

The current single Docker bridge runtime does not provide separate overlapping
address spaces. It rejects a second Session requesting an overlapping static
subnet, **without** renumbering addresses or sharing the first Session's network.
Use distinct subnets, or stop the existing Session before starting another.
Automatic-network Labs retain their existing multi-Session behavior.

The engine reserves subnets before runtime start under its lifecycle lock.
Successful cleanup releases them; uncertain cleanup retains them until a
successful stop. A rejected overlapping start does not poison reset of the
original Session. Errors are returned in a `FAILED` Session with an ID for
inspection/cleanup. Reset retains the original Lab snapshot and addresses.
Per-user Session quotas still count failed Sessions until stopped.

## Internal DNS

Optional per-node `dns: [10.231.20.3]` selects up to three distinct statically
addressed nodes sharing one of that node's declared networks. The target must
actually run a compatible DNS server; the example above does not start one.
This setting does not install a DNS service or grant low-port binding rights.
Public DNS, the bridge/host address and undeclared endpoints are rejected.
With no `dns` field, the runtime's existing Docker embedded name resolution
and node aliases are unchanged. This is not `No resolv.conf server`, custom
hosts-file editing, DNS search domains or unrestricted host DNS configuration.

## Terminal Slots

- `terminal_count` defaults to 1, with 1–4 slots per node, at most 8 across the
  whole Lab. Even nodes omitted from auto-launch `terminals` count toward the
  budget because they may be attached manually. An omitted node is headless
  at start, not forbidden to have a terminal.
- Slot numbers are zero-based and refer to independent runtime shells within
  the same container. Slots share the container's filesystem and networking.
- One D-Bus attachment per slot, bound to caller UID and connection. An occupied
  slot returns `Busy`; an out-of-range slot returns `InvalidArgs`.
- Detach/reconnect keeps that slot's shell; exit ends it. Reset/stop closes all
  slots and invalidates old handles. No terminal-group/tab feature yet.

```sh
cyberlab terminal SESSION_ID client
cyberlab terminal SESSION_ID client --slot 1
cyberlab terminal SESSION_ID server
```

The first command uses slot 0. Start in an interactive graphical desktop opens
the configured windows automatically; `--no-terminals` suppresses that launch.
The CLI reads the new plan and validates its shape/budget before executing the
fixed Konsole command. It never invokes Docker or a host shell.

## Shared D-Bus Additions

Existing `OpenTerminal(ssqq) -> s` remains slot 0. New method
`OpenTerminalSlot(ssuqq) -> s` accepts Session ID, node ID, slot, rows, columns.
Read/write/resize/close methods retain their existing attachment-handle API.
Capabilities `terminal-slots` and `static-networking` identify this source
feature; do not infer availability from version `0.9.0` alone.

Both Lab and captured Session dictionaries additionally expose:

| Key | Type | Contents |
| --- | --- | --- |
| `network_config` | `a(sss)` | Network ID, subnet, bridge gateway; empty strings for automatic networks |
| `addresses` | `a(sss)` | Node ID, network ID, configured static IP |
| `dns` | `a(sas)` | Node ID, declared DNS servers |
| `terminal_counts` | `a(su)` | Node ID, total permitted slots |
| `terminal_slots` | `a(su)` | Ordered node/slot auto-launch plan |

These are declared/snapshot values, not live interface discovery, assigned
dynamic IPs or per-node health. `GetAuthoringInfo` exposes the extended schema,
slot limits and restricted static-networking policy for future UI forms.

## Testing and Remaining Scope

```sh
.venv/bin/python -m pytest -q
.venv/bin/python tools/smoke_mvp.py
```

Tests cover parser/policy errors, host/Docker subnet preflight, actual SDK
serialization of IPAM/endpoints/DNS, multiple network attachments, concurrent
Session reservations and reset/cleanup, terminal isolation/reconnect/bounds,
window argv and invalid plans. Real CLI/private-D-Bus smoke creates a temporary
draft with static addressing and two slots, then saves/starts it and exercises
slot 1 through a real PTY. It uses MemoryRuntime, not Docker or Konsole.

No production service, Docker network, image, catalog or draft is changed by
these tests. Actual static IP assignment, DNS traffic and multiple real Docker
exec shells remain VM acceptance work after a separately approved source
deployment. The previous 0.9.0 bundle lacks these development changes.

Still deferred: gateway via a router container, static routes/NAT/forwarding,
Internet/MACVLAN/TAP, password provisioning, account creation inside arbitrary
images, X11, terminal groups, arbitrary DNS/resolver/hosts settings, GNS3,
assessment and Quickshell. Do not expose those screenshot controls as working.
