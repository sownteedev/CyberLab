from dataclasses import dataclass
from hashlib import sha256

from cyberlab.session import Session
from cyberlab.workspace import make_archive


def checkpoint_archives(session, workspaces):
    return {
        node.id: make_archive(workspaces[node.id], uid=node.user.uid if node.user else 65534,
                              gid=node.user.gid if node.user else 65534)
        for node in session.lab.nodes
    }


def workspace_hashes(archives):
    return {node: sha256(data).hexdigest() for node, data in archives.items()}


@dataclass(frozen=True)
class PreparedSubmission:
    report_id: str
    session: Session
    workspaces: dict[str, str]
    quiz: dict | None
    cleanup_started: bool = False
