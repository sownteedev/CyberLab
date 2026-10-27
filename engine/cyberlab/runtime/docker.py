import docker
from ipaddress import ip_network
from docker.errors import DockerException, ImageNotFound
from docker.types import IPAMConfig, IPAMPool, LogConfig

from cyberlab.session import Session
from cyberlab.lab.environment import runtime_user, shell_environment, validate_environment, workspace
from cyberlab.lab.networking import bridge_gateway, validate_networking
from cyberlab.lab.dependencies import startup_order

from . import RuntimeFailure
from .docker_terminal import DockerTerminal, close_stream
from .seeding import bootstrap_command, seed_archive, seed_container
from .identity import identity_command
from .importing import transfer_file
from .networking import read_host_subnets


MANAGED_LABEL = "org.ptit.cyberlab.managed"
MANAGED_VALUE = "mvp-v1"
SESSION_LABEL = "org.ptit.cyberlab.session"


class DockerRuntime:
    name = "docker"

    def __init__(self, client=None):
        try:
            self.client = client or docker.DockerClient(
                base_url="unix:///var/run/docker.sock", timeout=30
            )
        except (DockerException, OSError):
            raise RuntimeFailure("Docker is unavailable; ask the administrator") from None

    def _resources(self, collection, session_id=None, include_stopped=False):
        labels = [f"{MANAGED_LABEL}={MANAGED_VALUE}"]
        if session_id is not None:
            labels.append(f"{SESSION_LABEL}={session_id}")
        options = {"filters": {"label": labels}}
        if include_stopped:
            options["all"] = True
        resources = collection.list(**options)
        owned = []
        for resource in resources:
            resource.reload()
            actual = resource.attrs.get("Config", {}).get("Labels")
            if actual is None:
                actual = resource.attrs.get("Labels", {})
            if actual.get(MANAGED_LABEL) != MANAGED_VALUE:
                continue
            if session_id is None or actual.get(SESSION_LABEL) == session_id:
                owned.append(resource)
        return owned

    def _check_static_networks(self, lab):
        requested = [ip_network(network.subnet) for network in lab.networks if network.subnet]
        if not requested:
            return
        if any(subnet.overlaps(existing) for subnet in requested for existing in read_host_subnets()):
            raise RuntimeFailure("Static subnet overlaps a VM IPv4 route; choose a different subnet")
        for network in self.client.networks.list():
            for pool in network.attrs.get("IPAM", {}).get("Config", []) or []:
                if pool.get("Subnet"):
                    try:
                        existing = ip_network(pool["Subnet"], strict=False)
                    except ValueError:
                        raise RuntimeFailure("Cannot verify existing Docker network subnets") from None
                    if existing.version == 4 and any(subnet.overlaps(existing) for subnet in requested):
                        raise RuntimeFailure("Static subnet overlaps an existing Docker network; choose a different subnet")

    def start(self, session: Session, workspaces: dict | None = None) -> None:
        try:
            validate_networking(session.lab)
        except ValueError as error:
            raise RuntimeFailure(str(error)) from None
        labels = {MANAGED_LABEL: MANAGED_VALUE, SESSION_LABEL: session.id}
        prefix = f"cyberlab-{session.id}"
        for node in session.lab.nodes:
            validate_environment(node.hostname, node.user)
        if workspaces:
            archives = {node.id: workspaces[node.id] for node in session.lab.nodes if node.id in workspaces}
        else:
            archives = {
                node.id: seed_archive(node.seed, node.user.uid, node.user.gid) if node.user else seed_archive(node.seed)
                for node in session.lab.nodes if node.seed or node.user
            }
        stage = "checking network availability"
        try:
            self._check_static_networks(session.lab)
            images = {}
            for node in session.lab.nodes:
                stage = f"inspecting local image for node {node.id}"
                try:
                    image = self.client.images.get(node.image)
                except ImageNotFound:
                    raise RuntimeFailure(
                        f"Node {node.id}: image {node.image} is not preloaded. "
                        "Ask the administrator to prepare the approved image; CyberLab does not pull images at start."
                    ) from None
                if image.attrs.get("Config", {}).get("Volumes"):
                    raise RuntimeFailure(f"Node {node.id}: image {node.image} declares volumes, which are not allowed in this MVP")
                images[node.id] = image.id
            networks = {}
            for network in session.lab.networks:
                stage = f"creating private network {network.id}"
                configuration = {}
                if network.subnet:
                    configuration["ipam"] = IPAMConfig(pool_configs=[IPAMPool(
                        subnet=network.subnet, gateway=bridge_gateway(network),
                    )])
                networks[network.id] = self.client.networks.create(
                    f"{prefix}-{network.id}", driver="bridge", internal=True, labels=labels, **configuration,
                )
            containers = {}
            for node in startup_order(session.lab.nodes):
                stage = f"configuring node {node.id}"
                for dependency in node.wait_for:
                    dependency_container = containers.get(dependency)
                    if dependency_container is None:
                        raise RuntimeFailure(f"Node {node.id} dependency {dependency} was not started")
                    dependency_container.reload()
                    if dependency_container.status != "running":
                        raise RuntimeFailure(f"Node {node.id} dependency {dependency} stopped during startup")
                options = {}
                addresses = dict(node.addresses)
                if node.dns:
                    options["dns"] = list(node.dns)
                if node.extra_hosts:
                    options["extra_hosts"] = {hostname: address for hostname, address in node.extra_hosts}
                tmpfs = {"/tmp": "rw,noexec,nosuid,nodev,size=16m"}
                command = list(node.command)
                if node.id in archives:
                    options["stdin_open"] = True
                    command = bootstrap_command(node.command, workspace(node))
                if node.user:
                    command = identity_command(node, command)
                    tmpfs[node.user.home] = f"rw,noexec,nosuid,nodev,size=16m,uid={node.user.uid},gid={node.user.gid},mode=0700"
                    options["environment"] = shell_environment(node)
                    options["working_dir"] = node.user.home
                aliases = [node.id, *node.aliases]
                if node.networks:
                    first_network = networks[node.networks[0]].id
                    options["network"] = first_network
                    options["networking_config"] = {
                        first_network: self.client.api.create_endpoint_config(
                            aliases=aliases, **({"ipv4_address": addresses[node.networks[0]]} if node.networks[0] in addresses else {}),
                        )
                    }
                else:
                    options["network_mode"] = "none"
                stage = f"creating container for node {node.id}"
                container = self.client.containers.create(
                    images[node.id], command=command, entrypoint=[""],
                    name=f"{prefix}-{node.id}", hostname=node.hostname or node.id, labels=labels,
                    user=runtime_user(node), privileged=False, cap_drop=["ALL"],
                    security_opt=["no-new-privileges:true"], read_only=True,
                    tmpfs=tmpfs,
                    mem_limit=f"{node.resources.memory_mb}m", memswap_limit=f"{node.resources.memory_mb}m",
                    nano_cpus=node.resources.cpu_millicores * 1_000_000,
                    pids_limit=64, restart_policy={"Name": "no"},
                    log_config=LogConfig(type="local", config={
                        "max-size": "1m", "max-file": "1", "compress": "false",
                    }),
                    healthcheck={"test": ["NONE"]}, **options,
                )
                containers[node.id] = container
                for network_id in node.networks[1:]:
                    stage = f"connecting node {node.id} to network {network_id}"
                    networks[network_id].connect(container, aliases=aliases, **({"ipv4_address": addresses[network_id]} if network_id in addresses else {}))
                stage = f"starting node {node.id}; check its image command, shell and configured account"
                container.start()
                if node.id in archives:
                    try:
                        if node.user:
                            seed_container(container, archives[node.id], user=runtime_user(node))
                        else:
                            seed_container(container, archives[node.id])
                    except RuntimeFailure as error:
                        raise RuntimeFailure(f"Node {node.id}, workspace {workspace(node)}: {error}") from None
            if not self.running(session):
                raise RuntimeFailure("A node exited during startup")
        except (DockerException, OSError):
            raise RuntimeFailure(
                f"Docker start failed while {stage}. Ask the administrator to inspect Docker availability and daemon logs."
            ) from None

    def open_terminal(self, session: Session, node_id: str):
        stream = None
        try:
            expected_name = f"cyberlab-{session.id}-{node_id}"
            matches = [
                container for container in self._resources(self.client.containers, session.id, include_stopped=True)
                if container.name == expected_name and container.status == "running"
            ]
            if len(matches) != 1 or node_id not in {node.id for node in session.lab.nodes}:
                raise RuntimeFailure("Running terminal node not found")
            node = next(node for node in session.lab.nodes if node.id == node_id)
            command = ["/bin/sh"]
            if node.user:
                command = [node.user.shell, "-i"] if node.user.shell == "/bin/sh" else [node.user.shell, "--noprofile", "--norc", "-i"]
                command = identity_command(node, command)
            execution = self.client.api.exec_create(
                matches[0].id, cmd=command, stdin=True, stdout=True,
                stderr=True, tty=True, privileged=False, user=runtime_user(node),
                environment=shell_environment(node), workdir=node.user.home if node.user else "/tmp",
            )
            stream = self.client.api.exec_start(execution["Id"], tty=True, socket=True)
            return DockerTerminal(self.client.api, execution["Id"], stream)
        except (DockerException, OSError):
            if stream is not None:
                close_stream(stream)
            raise RuntimeFailure("Cannot open terminal; reset the Session before retrying") from None

    def import_file(self, session, record, data):
        try:
            node = next((node for node in session.lab.nodes if node.id == record.node), None)
            matches = [
                container for container in self._resources(self.client.containers, session.id, include_stopped=True)
                if container.name == f"cyberlab-{session.id}-{record.node}" and container.status == "running"
            ]
            if node is None or len(matches) != 1:
                raise RuntimeFailure("Running import node not found")
            transfer_file(self.client.api, matches[0].id, node, record, data)
        except (DockerException, OSError):
            raise RuntimeFailure("Cannot access import node; inspect Session state") from None

    def _workspace_container(self, session, node):
        matches = [container for container in self._resources(self.client.containers, session.id, include_stopped=True)
                   if container.name == f"cyberlab-{session.id}-{node.id}" and container.status == "running"]
        if len(matches) != 1:
            raise RuntimeFailure("Running workspace node not found")
        return matches[0]

    def workspace(self, session, node):
        from .workspace import snapshot

        try:
            return snapshot(self.client.api, self._workspace_container(session, node).id, node)
        except (DockerException, OSError):
            raise RuntimeFailure("Cannot access workspace node") from None

    def import_workspace(self, session, node, name, entries):
        from .workspace import import_folder

        try:
            import_folder(self.client.api, self._workspace_container(session, node).id, node, name, entries)
        except (DockerException, OSError):
            raise RuntimeFailure("Cannot access workspace node") from None

    def remove(self, session_id: str) -> None:
        self._remove(session_id)

    def _remove(self, session_id=None):
        try:
            failed = False
            for container in self._resources(self.client.containers, session_id, include_stopped=True):
                try:
                    container.remove(force=True, v=True)
                except (DockerException, OSError):
                    failed = True
            for network in self._resources(self.client.networks, session_id):
                try:
                    network.remove()
                except (DockerException, OSError):
                    failed = True
            if failed:
                raise RuntimeFailure("Runtime cleanup incomplete; retry stop or contact administrator")
        except (DockerException, OSError):
            raise RuntimeFailure("Cannot discover resources for cleanup; contact administrator") from None

    def running(self, session: Session) -> bool:
        try:
            containers = self._resources(self.client.containers, session.id, include_stopped=True)
            return len(containers) == len(session.lab.nodes) and all(
                container.status == "running" for container in containers
            )
        except (DockerException, OSError):
            raise RuntimeFailure("Cannot inspect runtime state") from None

    def cleanup(self) -> None:
        self._remove()
