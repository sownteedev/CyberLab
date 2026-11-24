from dataclasses import dataclass

from cyberlab.lab import Lab
from cyberlab.lab.environment import validate_environment
from cyberlab.lab.workstation import UBUNTU_IMAGE, validate_workstation
from cyberlab.lab.software import validate_software, enabled
from cyberlab.lab.setup import validate_setup_seed
from cyberlab.lab.networking import validate_networking
from cyberlab.lab.documentation import validate_documentation
from cyberlab.lab.dependencies import validate_node_dependencies
from cyberlab.lab.assets import AssetError, MAX_BYTES, MAX_ENTRIES, validate_mappings, validate_seed


class PolicyDenied(Exception):
    """The requested runtime behavior is not allowed."""


@dataclass(frozen=True)
class RuntimePolicy:
    allowed_images: frozenset[str]
    max_nodes: int = 4
    max_networks: int = 4
    max_active_sessions: int = 4
    max_sessions_per_user: int = 2
    max_session_history: int = 100
    workstation_images: frozenset[str] = frozenset()

    def validate(self, lab: Lab) -> None:
        if not self.workstation_images <= self.allowed_images or self.workstation_images - {UBUNTU_IMAGE}:
            raise PolicyDenied("Invalid administrator workstation image allowlist")
        try:
            validate_networking(lab)
            validate_node_dependencies(lab.nodes)
            validate_documentation(lab.documentation, loaded=True)
        except (AssetError, ValueError) as error:
            raise PolicyDenied(str(error)) from None
        if not 1 <= len(lab.nodes) <= self.max_nodes:
            raise PolicyDenied("Lab node count exceeds runtime policy")
        if len(lab.networks) > self.max_networks:
            raise PolicyDenied("Lab network count exceeds runtime policy")
        for node in lab.nodes:
            try:
                validate_environment(node.hostname, node.user)
                validate_software(node.software, node.image)
                validate_setup_seed(node)
                if node.image not in self.workstation_images and (node.resources.memory_mb > 512 or node.resources.cpu_millicores > 1000):
                    raise ValueError("Extended resource limits require an approved Ubuntu workstation")
                if enabled(node.software) and node.software.gui and node.resources.memory_mb < 1024:
                    raise ValueError("Graphical software requires at least 1024 MiB; recommended 2048 MiB")
                if node.image in self.workstation_images:
                    validate_workstation(node)
                elif node.image == UBUNTU_IMAGE:
                    raise ValueError("Ubuntu workstation mode has not been enabled by the administrator")
                validate_mappings(node.files)
                validate_seed(node.seed)
                validate_seed(node.system_seed)
                if bool(node.setup and node.setup.files) != bool(node.system_seed):
                    raise AssetError('System files must be loaded from the Lab package before start')
                if bool(node.files) != bool(node.seed):
                    raise AssetError("Initial files must be loaded from the Lab package before start")
            except (AssetError, ValueError) as error:
                raise PolicyDenied(str(error)) from None
            if node.image not in self.allowed_images:
                raise PolicyDenied("A node image is missing or not allowed by runtime policy")
            if not node.command:
                raise PolicyDenied("Each runtime node requires an explicit command")
        if sum(len(node.seed) + len(node.system_seed) for node in lab.nodes) > MAX_ENTRIES or sum(len(entry.data or b"") for node in lab.nodes for entry in (*node.seed, *node.system_seed)) > MAX_BYTES:
            raise PolicyDenied("Lab initial files exceed the 128 entry or 1 MiB limit")
