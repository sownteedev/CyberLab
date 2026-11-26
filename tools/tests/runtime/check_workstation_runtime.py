#!/usr/bin/env python3
"""Administrator-only real Docker acceptance, isolated from the production catalog/database."""

import argparse
from dataclasses import asdict
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
from uuid import uuid4

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "engine"))
schema_spec = importlib.util.spec_from_file_location("cyberlab.schemas", ROOT / "schemas/__init__.py",
                                                   submodule_search_locations=[str(ROOT / "schemas")])
sys.modules["cyberlab.schemas"] = importlib.util.module_from_spec(schema_spec)
schema_spec.loader.exec_module(sys.modules["cyberlab.schemas"])

from cyberlab.lab.workstation import UBUNTU_IMAGE, workstation_user
from cyberlab.policy import RuntimePolicy
from cyberlab.runtime.docker import DockerRuntime
from cyberlab.service import Engine
from cyberlab.session import SessionState
from cyberlab.session.persistence import PracticeStore

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--uid", type=int, required=True)
    parser.add_argument("--username", default="student")
    args = parser.parse_args()
    if os.geteuid() != 0 or args.uid <= 0:
        parser.error("Run as administrator with the desktop UID; never give users Docker access")
    user = workstation_user(args.username)
    with tempfile.TemporaryDirectory(prefix="cyberlab-ubuntu-acceptance-", dir="/var/tmp") as temporary:
        root = Path(temporary)
        catalog = root / "catalog"
        package = catalog / "fixture"
        package.mkdir(parents=True)
        (package / "assets").mkdir()
        (package / "assets/welcome.txt").write_text("fixture\n")
        document = {"apiVersion": "cyberlab.ptit/v1", "kind": "Lab",
                    "metadata": {"id": "fixture", "name": "Isolated Ubuntu acceptance", "version": "1.0.0"},
                    "networks": [{"id": "lan"}], "terminals": ["client"],
                    "nodes": [{"id": "client", "image": UBUNTU_IMAGE, "networks": ["lan"],
                               "command": ["sleep", "infinity"], "user": asdict(user),
                               "files": [{"source": "assets/welcome.txt", "target": "welcome.txt"}],
                               "resources": {"memory_mb": 512, "cpu_millicores": 1000}}]}
        (package / "lab.yaml").write_text(json.dumps(document))
        runtime = DockerRuntime(workstation_images={UBUNTU_IMAGE}, checkpoint_scope="acceptance-" + uuid4().hex)
        runtime.client.api.timeout = 180
        policy = RuntimePolicy(frozenset({UBUNTU_IMAGE}), workstation_images=frozenset({UBUNTU_IMAGE}))
        store = PracticeStore(root / "practice.sqlite3")
        engine = Engine(catalog, policy, runtime, store)
        session = None
        checks = []
        def command(script):
            current = engine.status(session.id, args.uid)
            container = runtime._workspace_container(current, current.lab.nodes[0])
            if len(container.attrs['NetworkSettings']['Networks']) != 1:
                raise RuntimeError('Workstation must have only its declared LAN attachment')
            result = container.exec_run(["/bin/bash", "--noprofile", "--norc", "-c", script],
                                        user="2000:2000", workdir=user.home,
                                        environment={"HOME": user.home, "USER": user.name, "EXPECTED_USER": user.name, "EXPECTED_HOME": user.home})
            if result.exit_code:
                raise RuntimeError(f"Container acceptance failed ({result.exit_code}): {result.output.decode(errors='replace')[-3000:]}")
        try:
            session = engine.start("fixture", args.uid)
            if session.state != SessionState.RUNNING:
                raise RuntimeError(session.error)
            command('test "$(id -un)" = "$EXPECTED_USER" && test "$HOME" = "$EXPECTED_HOME" && test "$(pwd)" = "$EXPECTED_HOME" && test "$(stat -c %u welcome.txt)" = 2000 && test "$(cat welcome.txt)" = fixture && dir >/dev/null && sudo -n true')
            checks.append("student/bash/home/seed/dir/sudo")
            print("PASS: student, Bash, home, seed files, dir and sudo", flush=True)
            command('sudo -n apt-get update -qq && sudo -n env DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends neovim >/dev/null && nvim --version >/dev/null && printf "saved\\n" > saved.txt')
            checks.append("apt-update-and-install-neovim-over-egress")
            print("PASS: apt update and neovim install", flush=True)
            engine.suspend(session.id, args.uid)
            if engine.status(session.id, args.uid).state != SessionState.SUSPENDED:
                raise RuntimeError("Suspend failed")
            engine = Engine(catalog, policy, runtime, PracticeStore(root / "practice.sqlite3"))
            resumed = engine.resume(session.id, args.uid)
            if resumed.state != SessionState.RUNNING:
                raise RuntimeError(resumed.error)
            command('nvim --version >/dev/null && test "$(cat saved.txt)" = saved && sudo -n true')
            checks.append("suspend-reload-resume-preserves-installed-package-and-home")
            print("PASS: suspend, fresh Engine, resume with installed package and home", flush=True)
            reset = engine.reset(session.id, args.uid)
            if reset.state != SessionState.RUNNING:
                raise RuntimeError(reset.error)
            command('! command -v nvim && test ! -e saved.txt && test "$(cat welcome.txt)" = fixture')
            checks.append("reset-restores-original-image-and-seed")
        finally:
            if session is not None:
                runtime.remove(session.id)
                store.delete_checkpoint(session.id)
            runtime.system_checkpoints.collect(set())
            runtime.client.close()
        print(json.dumps({"passed": checks, "username": user.name, "home": user.home,
                          "production_catalog_used": False, "cleanup": "completed"}, indent=2))

if __name__ == "__main__":
    main()
