from dataclasses import asdict
from hashlib import sha256
import json
import re

from .models import NodeSoftware
from .workstation import UBUNTU_IMAGE

RECIPE_VERSION = "ubuntu-apps-v1"
STARTUP_TIMEOUT_SECONDS = 7200
APPLICATIONS = (
    {"id": "wireshark", "name": "Wireshark", "command": "wireshark", "packages": ["wireshark", "tshark", "libcap2-bin"],
     "permissions": ["NET_RAW", "NET_ADMIN"], "source": "Ubuntu"},
    {"id": "firefox", "name": "Firefox", "command": "firefox", "packages": ["firefox"],
     "permissions": [], "source": "Mozilla APT (signed)"},
)
PACKAGE_NAME = re.compile(r"[a-z0-9][a-z0-9+.-]{1,99}")

def enabled(software):
    return software.gui or bool(software.apps or software.packages)

def specification(software):
    return {"gui": software.gui, "apps": sorted(software.apps), "packages": sorted(software.packages)}

def fingerprint(software):
    return sha256(json.dumps({"recipe": RECIPE_VERSION, **specification(software)}, sort_keys=True).encode()).hexdigest()

def validate_software(software, image):
    if not isinstance(software, NodeSoftware) or type(software.gui) is not bool:
        raise ValueError("Invalid machine software declaration")
    if len(software.apps) > len(APPLICATIONS) or len(set(software.apps)) != len(software.apps) or set(software.apps) - {app['id'] for app in APPLICATIONS}:
        raise ValueError("Unknown or repeated application")
    if len(software.packages) > 32 or len(set(software.packages)) != len(software.packages) or any(not isinstance(name, str) or PACKAGE_NAME.fullmatch(name) is None for name in software.packages):
        raise ValueError("Use up to 32 distinct APT package names, not commands, options, versions or URLs")
    if set(software.packages) & {"firefox", "wireshark", "tshark", "wireshark-common", "snapd"}:
        raise ValueError("Use the reviewed Firefox/Wireshark choices; Snap is not supported")
    if (enabled(software) or software.environment) and image != UBUNTU_IMAGE:
        raise ValueError("Prepared software requires the approved Ubuntu workstation")
    if software.environment and re.fullmatch(r"sha256:[0-9a-f]{64}", software.environment) is None:
        raise ValueError("Prepared environment must be an immutable SHA-256 image ID")
    if software.environment and not enabled(software):
        raise ValueError("An unused software environment must be cleared")

def catalog():
    return {"applications": [dict(app) for app in APPLICATIONS],
            "packages": [], "max_packages": 32,
            "recipe": RECIPE_VERSION, "resources": {"memory_mb": 2048, "cpu_millicores": 2000},
            "sources": ["Ubuntu repositories", "Mozilla (Firefox only)"],
            "extra_packages_permissions": "No additional runtime capabilities"}
