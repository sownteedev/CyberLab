import argparse
import asyncio
import logging
import os
from pathlib import Path
import signal
import tempfile
import stat

from dbus_next import BusType, NameFlag, RequestNameReply
from dbus_next.aio import MessageBus

from cyberlab.policy import RuntimePolicy
from cyberlab.service import Engine
from cyberlab_ipc import BUS_NAME

from .config import load_config, trusted_path
from .server import Server


async def serve(arguments):
    temporary_authoring = None
    authoring_path = None
    practice_path = None
    if arguments.test_session_bus:
        if os.geteuid() == 0:
            raise ValueError("Test mode must run unprivileged, not as root")
        from .testing import MemoryRuntime

        runtime = MemoryRuntime()
        allowed_uids = frozenset({os.getuid()})
        catalog = arguments.catalog or Path.cwd() / "labs"
        images = frozenset({"busybox:1.37.0", "cyberlab/demo-users:0.6.0"})
        bus_type = BusType.SESSION
        if arguments.authoring_state:
            authoring_path = arguments.authoring_state
            practice_path = authoring_path.parent / "practice.sqlite3"
        else:
            temporary_authoring = tempfile.TemporaryDirectory(prefix="cyberlab-test-authoring-")
            authoring_path = Path(temporary_authoring.name) / "drafts.sqlite3"
            practice_path = Path(temporary_authoring.name) / "practice.sqlite3"
    else:
        if os.geteuid() != 0:
            raise ValueError("Production daemon requires the administrator-installed system service")
        if arguments.catalog is not None or arguments.authoring_state is not None:
            raise ValueError("Production paths must come from the trusted config")
        config = load_config(arguments.config)
        from cyberlab.runtime.docker import DockerRuntime

        runtime = DockerRuntime()
        allowed_uids, catalog, images = config.allowed_uids, config.catalog, config.allowed_images
        bus_type = BusType.SYSTEM
        if config.authoring:
            authoring_path = Path("/var/lib/cyberlab/authoring/drafts.sqlite3")
            trusted_path(authoring_path.parent)
            practice_path = Path("/var/lib/cyberlab/authoring/practice.sqlite3")
            if authoring_path.parent.stat().st_mode & 0o077:
                raise ValueError("Authoring state directory must be private to root")
            for entry in authoring_path.parent.iterdir():
                trusted_path(entry)
                status = entry.stat()
                if not stat.S_ISREG(status.st_mode) or status.st_nlink != 1 or status.st_mode & 0o077:
                    raise ValueError("Authoring state files must be private regular files without hardlinks")

    practice_store = None
    if practice_path is not None:
        from cyberlab.session.persistence import PracticeStore
        practice_store = PracticeStore(practice_path)
    engine = Engine(catalog, RuntimePolicy(images), runtime, practice_store=practice_store)
    engine.labs()
    bus = await MessageBus(bus_type=bus_type).connect()
    server = None
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    try:
        reply = await bus.request_name(BUS_NAME, NameFlag.DO_NOT_QUEUE)
        if reply != RequestNameReply.PRIMARY_OWNER:
            raise ValueError("Another cyberlabd instance owns the bus name")
        await asyncio.to_thread(runtime.cleanup)
        authoring = None
        if authoring_path is not None:
            from cyberlab.authoring import Authoring

            authoring = Authoring(authoring_path, catalog, engine.policy, engine._lock,
                                  runtime_checker=engine.check_runtime, update_checker=engine.check_lab_update)
        server = Server(bus, engine, allowed_uids, authoring)
        bus.add_message_handler(server.handle)
        for signum in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(signum, stop.set)
        logging.info("Ready: %s, runtime=%s", BUS_NAME, runtime.name)
        stop_task = asyncio.create_task(stop.wait())
        disconnect_task = asyncio.create_task(bus.wait_for_disconnect())
        await asyncio.wait({stop_task, disconnect_task}, return_when=asyncio.FIRST_COMPLETED)
        stop_task.cancel()
        if server is not None:
            await server.shutdown()
            server = None
        bus.disconnect()
        await asyncio.gather(stop_task, disconnect_task, return_exceptions=True)
    finally:
        try:
            if server is not None:
                await server.shutdown()
        finally:
            bus.disconnect()
            if temporary_authoring is not None:
                temporary_authoring.cleanup()


def main():
    parser = argparse.ArgumentParser(description="CyberLab System D-Bus daemon")
    parser.add_argument("--config", type=Path, default=Path("/etc/cyberlab/daemon.toml"))
    parser.add_argument("--test-session-bus", action="store_true", help="Unprivileged in-memory test runtime only")
    parser.add_argument("--catalog", type=Path, help="Catalog override for test mode only")
    parser.add_argument("--authoring-state", type=Path, help="Persistent draft database for test mode only; defaults to a temporary database")
    arguments = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    try:
        asyncio.run(serve(arguments))
    except Exception as error:
        logging.error("Daemon stopped: %s", error)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
