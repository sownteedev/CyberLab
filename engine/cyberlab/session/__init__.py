from dataclasses import dataclass, replace
from datetime import datetime, timezone
from enum import StrEnum

from cyberlab.lab import Lab


class SessionState(StrEnum):
    PREPARING = "PREPARING"
    RUNNING = "RUNNING"
    STOPPING = "STOPPING"
    STOPPED = "STOPPED"
    SUSPENDED = "SUSPENDED"
    RESETTING = "RESETTING"
    FAILED = "FAILED"


def timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class Session:
    id: str
    lab: Lab
    owner_uid: int
    state: SessionState
    created_at: str
    updated_at: str
    error: str = ""
    checkpoint_at: str = ""
    parameters: tuple[tuple[str, str], ...] = ()

    def transition(self, state: SessionState, error: str = "") -> "Session":
        allowed = {
            SessionState.PREPARING: {SessionState.RUNNING, SessionState.FAILED},
            SessionState.RUNNING: {SessionState.STOPPING, SessionState.RESETTING, SessionState.FAILED, SessionState.SUSPENDED},
            SessionState.STOPPING: {SessionState.STOPPED, SessionState.FAILED},
            SessionState.STOPPED: {SessionState.RESETTING, SessionState.PREPARING},
            SessionState.SUSPENDED: {SessionState.PREPARING, SessionState.RESETTING, SessionState.STOPPING, SessionState.STOPPED, SessionState.FAILED},
            SessionState.RESETTING: {SessionState.RUNNING, SessionState.FAILED},
            SessionState.FAILED: {SessionState.STOPPING, SessionState.RESETTING},
        }
        if state not in allowed[self.state]:
            raise ValueError(f"Invalid Session transition: {self.state} -> {state}")
        return replace(self, state=state, updated_at=timestamp(), error=error)
