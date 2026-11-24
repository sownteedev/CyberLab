# Network and Per-Node Terminal Configuration

The schema, draft editor, engine, Docker adapter, shared D-Bus contract and CLI
use the same network configuration. No new transport or host service is added.

## Single-interface Internet access (2026-11-11)

The approved runtime now uses each declared network for both Lab traffic and,
when enabled, outbound Internet access. A two-machine Ubuntu Lab on `lan` gets
one private bridge and only `eth0` on each machine. There is no extra `packages`
network/interface. `sudo apt update` and `sudo apt install` work during practice
through the same interface as DNS, ping and SSH between machines.

`networks[].internet` is an optional boolean. Studio exposes one **Internet**
switch per network; new networks default to on. Explicit `false` creates an
internal bridge with no hidden egress attachment. This applies to the entire
network, not just one machine. Software can still be prepared in the separate
existing image-preparation workflow before an offline Lab starts.

For existing definitions that omit the field, a network defaults to Internet
enabled only if it is the first attachment of an Ubuntu workstation. Legacy
restricted-only networks and other secondary networks remain internal.
No catalog file or draft is rewritten to apply these defaults. A standalone
Ubuntu workstation with no declared networks retains one Session-owned egress
bridge for compatibility; define and attach an offline network to disable it.
CLI `show`/`status` expose the resolved values in `network_internet` alongside
the unchanged `network_config` tuples.

Every bridge remains private to its Session; nothing is attached to Docker's
shared default bridge. Enabling Internet means outbound access allowed by the
host routing/firewall, including reachable LAN/host services, not a package-only
or Internet-only destination filter. No host ports are published. A machine
attached to multiple declared networks has multiple interfaces; an offline
attachment does not prevent that machine using another Internet-enabled one.

Existing running Sessions retain their old topology. A newly started/resumed
Session gets the new topology; no live network disconnect or forced restart is
performed by an upgrade. Static-subnet collision checks remain unchanged.

### Verification and deployment

On 2026-11-11, the isolated real-Docker network fixture passed single-interface
DNS/TCP between two machines, `apt update` and installation of `hello` through
`eth0`, distinct bridges for simultaneous Sessions with cross-bridge TCP blocked,
offline LAN connectivity with no default route, and a second interface only for
an explicitly attached second network. The workstation acceptance fixture also
passed package installation, suspend/reload/resume and reset, verifying exactly
one network attachment after each lifecycle operation. All fixture containers,
networks and checkpoint images were removed; the production catalog/database
were not used. Ubuntu workstation containers now receive only `CAP_NET_RAW` in
addition to their existing reviewed capabilities, so the standard
`iputils-ping` command can create ICMP sockets. Restricted non-Ubuntu nodes do
not receive this capability, and no container is run as `privileged`.

Regression checks passed: 30 workstation tests, 18 Session-state tests,
69 desktop/private-D-Bus tests, 31 native-display tests, 19 software tests,
14 Labtainer-compatibility tests and 12 draft-editing tests. Studio passed
103 editor tests and native offscreen loading, both from source and the extracted
wheel. Desktop/compact network-page screenshots were inspected. Targeted Qt 6
lint exited successfully with existing naming/unqualified-access warnings;
`git diff --check` passed.

Guarded installation used
`/tmp/cyberlab-network-release-20261111-EvK0wL/cyberlab_engine-0.9.0-py3-none-any.whl`,
SHA-256 `7954e87d8cb1abe2771c48e091ca6f356631346fc8ab817e2d8ed4ce67430915`,
with rollback backup `/var/tmp/cyberlab-runtime-backup-5rrhym78`. The user's
Session was already STOPPED and Studio closed; no user process or Lab was
force-stopped. All allowed users passed the updater's stopped-Session gate.
All 292 installed package files match the wheel. Installed `draft info` reports
`network_internet=true`, and read-only `show users` resolves `lan` to Internet
enabled without rewriting the existing template. The daemon is active with
`RestrictAddressFamilies=AF_UNIX`; XWayland host readiness remains available.
Normal installed Studio opened on Wayland and its exact test window closed
cleanly. Its existing `NodeSoftwareEditor.qml:122` initialization warning remains
outside this change. User-Lab manual acceptance is still separate from these
disposable runtime checks.

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
    internet: false
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
the selected desktop terminal to open three attachments: two independent shells in `client`, one in
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
- Offline networks use `internal=True`; Internet-enabled networks use the same
  Session-owned bridge with `internal=False`. Neither publishes host ports,
  adds host network mode or devices, nor makes a container `privileged`.
  Reviewed Ubuntu workstation capabilities are configured separately; restricted
  nodes receive none.
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
selected terminal adapter's explicit argv. It never invokes Docker or accepts
host shell commands from a Lab. Black Box's internal shell requires quoted
arguments; see `terminal-windows.md`. Konsole retains grouped tabs; other adapters open separate windows/slots.
The terminal preference is local user configuration, not part of this Lab schema.

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
