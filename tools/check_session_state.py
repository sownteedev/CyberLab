#!/usr/bin/env python3
"""Saved lifecycle regression checks using temporary storage and MemoryRuntime."""

from dataclasses import replace
from concurrent.futures import ThreadPoolExecutor
import importlib.util
import json
import os
from pathlib import Path
import selectors
import signal
import sqlite3
import subprocess
import sys
import tempfile
import time
from threading import Event
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "engine"), str(ROOT / "daemon"), str(ROOT / "tools")]
schema_spec = importlib.util.spec_from_file_location("cyberlab.schemas", ROOT / "schemas/__init__.py",
                                                   submodule_search_locations=[str(ROOT / "schemas")])
sys.modules["cyberlab.schemas"] = importlib.util.module_from_spec(schema_spec)
schema_spec.loader.exec_module(sys.modules["cyberlab.schemas"])

from cyberlab.policy import RuntimePolicy
from cyberlab.runtime import RuntimeFailure
from cyberlab.service import Engine, SessionNotFound
from cyberlab.session import SessionState
from cyberlab.session.persistence import PracticeStore
from cyberlab.lab.models import NodeSoftware
from cyberlab.submission_review import review_submissions
from cyberlabd.testing import MemoryRuntime
from upgrade_runtime import preserve_stopped_checkpoints


class SessionStateChecks(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory(prefix="cyberlab-session-state-")
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        package = self.root / "fixture"
        package.mkdir()
        (package / "lab.yaml").write_text(json.dumps({
            "apiVersion": "cyberlab.ptit/v1", "kind": "Lab",
            "metadata": {"id": "fixture", "name": "Fixture", "version": "1.0.0"},
            "nodes": [{"id": "client", "image": "busybox:1.37.0",
                       "command": ["sleep", "infinity"], "networks": []}],
            "networks": [], "terminals": ["client"],
        }))
        self.store = PracticeStore(self.root / "practice.sqlite3")
        self.policy = RuntimePolicy(frozenset({"busybox:1.37.0"}))
        self.runtime = MemoryRuntime()
        self.engine = Engine(self.root, self.policy, self.runtime, self.store)
        self.session = self.engine.start("fixture", 1234)
        self.assertEqual(self.session.state, SessionState.RUNNING)
        self.runtime.files[self.session.id]["client"]["kept.txt"] = b"saved"
        self.session = self.engine.save(self.session.id, 1234)

    def reload(self):
        return Engine(self.root, self.policy, MemoryRuntime(), PracticeStore(self.store.database))

    def row(self):
        with self.store.transaction() as connection:
            return dict(connection.execute("SELECT * FROM saved_sessions WHERE id=?", (self.session.id,)).fetchone())

    def upgrade_record(self):
        return {"id": self.session.id, "owner_uid": 1234, "state": "STOPPED", "saved": True,
                "checkpoint_at": self.session.checkpoint_at, "updated_at": "upgrade-stop-time"}

    def test_stopped_checkpoint_survives_restart_and_resumes_saved_not_unsaved_files(self):
        before = self.store.get_checkpoint(self.session.id)
        self.runtime.files[self.session.id]["client"]["kept.txt"] = b"unsaved"
        stopped = self.engine.stop(self.session.id, 1234)
        self.assertEqual(stopped.state, SessionState.STOPPED)
        self.assertNotIn(stopped.id, self.runtime.active)
        restored = self.reload()
        self.assertEqual(restored.status(stopped.id, 1234), stopped)
        self.assertEqual(self.store.get_checkpoint(stopped.id), {**before, "state": "STOPPED"})
        self.assertEqual(restored.resume(stopped.id, 1234).state, SessionState.RUNNING)
        self.assertEqual(restored.runtime.files[stopped.id]["client"]["kept.txt"], b"saved")

    def test_saved_checkpoint_captures_prepared_software_image(self):
        image = "sha256:" + "e" * 64
        session = replace(self.session, lab=replace(
            self.session.lab,
            nodes=(replace(self.session.lab.nodes[0], software=NodeSoftware(environment=image)),),
        ))
        definition = self.engine._checkpoint_definition(session, self.engine._session_packages[session.id]["definition"])
        document = json.loads(definition)
        self.assertEqual(document["nodes"][0]["software"]["environment"], image)

    def test_suspend_remains_suspended(self):
        suspended = self.engine.suspend(self.session.id, 1234)
        self.assertEqual(self.reload().status(suspended.id, 1234), suspended)

    def test_resume_replaces_stale_stopped_marker(self):
        self.engine.stop(self.session.id, 1234)
        resumed = self.engine.resume(self.session.id, 1234)
        self.assertEqual(resumed.state, SessionState.RUNNING)
        self.assertEqual(self.row()["state"], "RUNNING")
        restored = self.reload()
        self.assertEqual(restored.status(resumed.id, 1234).state, SessionState.SUSPENDED)
        self.assertFalse(restored.runtime.active)

    def test_legacy_saved_and_incomplete_transitions_restore_suspended(self):
        for state in ("SAVED", "PREPARING", "STOPPING", "RESETTING", "FAILED"):
            with self.subTest(state=state):
                with self.store.transaction() as connection:
                    connection.execute("UPDATE saved_sessions SET state=?", (state,))
                self.assertEqual(self.reload().status(self.session.id, 1234).state, SessionState.SUSPENDED)

    def test_stop_is_idempotent(self):
        stopped = self.engine.stop(self.session.id, 1234)
        before = self.row()
        self.assertEqual(self.engine.stop(stopped.id, 1234), stopped)
        self.assertEqual(self.row(), before)

    def test_cleanup_failure_never_records_stopped_or_loses_checkpoint(self):
        before = self.store.get_checkpoint(self.session.id)
        with patch.object(self.runtime, "remove", side_effect=RuntimeFailure("cleanup failed")):
            failed = self.engine.stop(self.session.id, 1234)
        self.assertEqual(failed.state, SessionState.FAILED)
        self.assertEqual(self.store.get_checkpoint(failed.id), {**before, "state": "FAILED"})
        self.assertEqual(self.engine.stop(failed.id, 1234).state, SessionState.STOPPED)

    def test_storage_failure_does_not_claim_stop_or_remove_runtime(self):
        with patch.object(self.store, "update_session_state", side_effect=sqlite3.OperationalError("full")):
            with self.assertRaises(sqlite3.OperationalError):
                self.engine.stop(self.session.id, 1234)
        self.assertIn(self.session.id, self.runtime.active)
        self.assertEqual(self.engine.status(self.session.id, 1234).state, SessionState.RUNNING)

    def test_other_owner_cannot_stop_saved_session(self):
        before = self.row()
        with self.assertRaises(SessionNotFound):
            self.engine.stop(self.session.id, 4321)
        self.assertEqual(self.row(), before)

    def test_stale_identity_or_checkpoint_cannot_update_row(self):
        before = self.row()
        for changes in ({"id": "missing"}, {"owner_uid": 4321}, {"checkpoint_at": "stale"}):
            with self.subTest(changes=changes):
                self.store.update_session_state(replace(self.session, state=SessionState.STOPPED, **changes))
                self.assertEqual(self.row(), before)

    def test_discard_and_reset_still_remove_checkpoint(self):
        self.engine.suspend(self.session.id, 1234)
        self.assertEqual(self.engine.discard(self.session.id, 1234).state, SessionState.STOPPED)
        self.assertIsNone(self.store.get_checkpoint(self.session.id))
        reset = self.engine.reset(self.session.id, 1234)
        self.assertEqual(reset.state, SessionState.RUNNING)
        self.engine.save(reset.id, 1234)
        self.assertEqual(self.engine.reset(reset.id, 1234).checkpoint_at, "")
        self.assertIsNone(self.store.get_checkpoint(reset.id))

    def test_unsaved_stop_does_not_create_checkpoint(self):
        self.engine.discard(self.session.id, 1234)
        stopped = self.engine.stop(self.session.id, 1234)
        self.assertEqual(stopped.state, SessionState.STOPPED)
        self.assertEqual(self.store.load_sessions(), [])

    def test_reset_preparation_failure_does_not_retain_deleted_checkpoint(self):
        def prepare(*arguments, **keywords):
            raise RuntimeFailure("software preparation failed")

        with patch.object(self.runtime, "prepared_software", SimpleNamespace(prepare_lab=prepare), create=True):
            reset = self.engine.reset(self.session.id, 1234)
        self.assertEqual(reset.state, SessionState.FAILED)
        self.assertEqual(reset.checkpoint_at, "")
        self.assertIsNone(self.store.get_checkpoint(reset.id))
        self.assertNotIn(reset.id, self.engine._starting)

    def test_reset_storage_failure_preserves_checkpoint_and_quiz_for_recovery(self):
        payload = json.dumps({"session_id": self.session.id, "answers": {"question": "answer"}})
        self.store.save_quiz_attempt(self.session.id, 1234, self.session.updated_at, payload)
        checkpoint = self.store.get_checkpoint(self.session.id)
        with self.store.transaction() as connection:
            connection.execute("""
                CREATE TRIGGER fail_quiz_delete BEFORE DELETE ON quiz_attempts
                BEGIN SELECT RAISE(ABORT, 'injected storage failure'); END
            """)
        with self.assertRaises(Exception) as failure:
            self.engine.reset(self.session.id, 1234)
        failed = self.engine.status(self.session.id, 1234)
        retained = self.store.get_checkpoint(failed.id)
        self.assertIsNotNone(retained)
        self.assertIsInstance(failure.exception, RuntimeFailure)
        self.assertEqual(failed.state, SessionState.FAILED)
        self.assertEqual(failed.checkpoint_at, self.session.checkpoint_at)
        self.assertEqual(retained["workspaces"], checkpoint["workspaces"])
        self.assertEqual(self.store.get_quiz_attempt(failed.id, 1234), json.loads(payload))
        self.assertNotIn(failed.id, self.engine._starting)
        self.engine.stop(failed.id, 1234)
        self.assertEqual(self.engine.resume(failed.id, 1234).state, SessionState.RUNNING)
        self.assertEqual(self.runtime.files[failed.id]["client"]["kept.txt"], b"saved")

    def test_stop_during_reset_does_not_advertise_deleted_checkpoint(self):
        entered, release = Event(), Event()

        def prepare(lab, owner, cancel, **keywords):
            entered.set()
            if not release.wait(5):
                raise RuntimeFailure("test preparation timed out")
            return lab

        with patch.object(self.runtime, "prepared_software", SimpleNamespace(prepare_lab=prepare), create=True):
            with ThreadPoolExecutor(max_workers=1) as executor:
                pending = executor.submit(self.engine.reset, self.session.id, 1234)
                try:
                    self.assertTrue(entered.wait(5))
                    resetting = self.engine.status(self.session.id, 1234)
                    stopped = self.engine.stop(self.session.id, 1234)
                finally:
                    release.set()
                result = pending.result(timeout=5)
        self.assertEqual(resetting.state, SessionState.RESETTING)
        self.assertEqual(resetting.checkpoint_at, "")
        self.assertEqual(result, stopped)
        self.assertEqual(stopped.state, SessionState.STOPPED)
        self.assertEqual(stopped.checkpoint_at, "")
        self.assertIsNone(self.store.get_checkpoint(stopped.id))
        self.assertNotIn(stopped.id, self.engine._starting)
        self.assertNotIn(stopped.id, self.runtime.active)

    def test_cleanup_read_failure_does_not_interrupt_committed_lifecycle_changes(self):
        systems = SimpleNamespace(capture=Mock(return_value={}), release=Mock(), collect=Mock())
        with patch.object(self.runtime, "system_checkpoints", systems, create=True):
            with patch.object(self.store, "system_image_ids", side_effect=sqlite3.OperationalError("database locked")):
                with self.assertLogs(level="WARNING"):
                    saved = self.engine.save(self.session.id, 1234)
                    self.assertEqual(saved.checkpoint_at, self.row()["checkpoint_at"])
                    reset = self.engine.reset(self.session.id, 1234)
        self.assertEqual(reset.state, SessionState.RUNNING)
        self.assertEqual(reset.checkpoint_at, "")
        self.assertIsNone(self.store.get_checkpoint(reset.id))
        systems.collect.assert_not_called()
        systems.release.assert_not_called()

    def test_submission_export_finish_restart_and_resume_preserves_checkpoint(self):
        report = self.engine.prepare_submission(self.session.id, 1234)
        archive = self.engine.export_submission(report["id"], 1234)
        review = review_submissions([("fixture.zip", archive)])
        self.assertEqual(review["summary"]["valid"], 1)
        self.assertEqual(self.engine.status(self.session.id, 1234).state, SessionState.RUNNING)
        stopped = self.engine.finalize_submission(self.session.id, report["id"], 1234)
        self.assertEqual(stopped.state, SessionState.STOPPED)
        restored = self.reload()
        self.assertEqual(restored.status(stopped.id, 1234).state, SessionState.STOPPED)
        restored.resume(stopped.id, 1234)
        self.assertEqual(restored.runtime.files[stopped.id]["client"]["kept.txt"], b"saved")

    def test_changed_work_after_submission_capture_keeps_session_running(self):
        report = self.engine.prepare_submission(self.session.id, 1234)
        self.runtime.files[self.session.id]["client"]["kept.txt"] = b"new work"
        with self.assertRaisesRegex(RuntimeFailure, "Workspace changed"):
            self.engine.finalize_submission(self.session.id, report["id"], 1234)
        self.assertEqual(self.engine.status(self.session.id, 1234).state, SessionState.RUNNING)
        self.assertEqual(self.runtime.files[self.session.id]["client"]["kept.txt"], b"new work")

    def test_failed_suspend_capture_keeps_previous_checkpoint_and_live_files(self):
        before = self.store.get_checkpoint(self.session.id)
        self.runtime.files[self.session.id]["client"]["kept.txt"] = b"new work"
        with patch.object(self.runtime, "workspace", side_effect=RuntimeFailure("capture failed")):
            with self.assertRaisesRegex(RuntimeFailure, "capture failed"):
                self.engine.suspend(self.session.id, 1234)
        self.assertEqual(self.engine.status(self.session.id, 1234).state, SessionState.RUNNING)
        self.assertEqual(self.store.get_checkpoint(self.session.id), before)
        self.assertEqual(self.runtime.files[self.session.id]["client"]["kept.txt"], b"new work")

    def test_updater_preserves_only_state_and_transition_time(self):
        before = self.row()
        checkpoint = self.store.get_checkpoint(self.session.id)
        record = self.upgrade_record()
        preserve_stopped_checkpoints(Path(self.store.database), [record])
        self.assertEqual(self.row(), {**before, "state": "STOPPED", "updated_at": record["updated_at"]})
        self.assertEqual(self.store.get_checkpoint(self.session.id), {**checkpoint, "state": "STOPPED"})
        self.assertEqual(self.reload().status(self.session.id, 1234).state, SessionState.STOPPED)

    def test_updater_rolls_back_entire_batch_on_stale_or_unsafe_record(self):
        before = self.row()
        record = self.upgrade_record()
        for changes in ({"id": "missing"}, {"owner_uid": 4321}, {"checkpoint_at": "stale"},
                        {"state": "RUNNING"}, {"state": "SUSPENDED"}, {"saved": False}):
            with self.subTest(changes=changes):
                with self.assertRaises(ValueError):
                    preserve_stopped_checkpoints(Path(self.store.database), [record, {**record, **changes}])
                self.assertEqual(self.row(), before)

    def test_updater_never_creates_database(self):
        missing = self.root / "missing.sqlite3"
        preserve_stopped_checkpoints(missing, [])
        self.assertFalse(missing.exists())
        with self.assertRaises(sqlite3.OperationalError):
            preserve_stopped_checkpoints(missing, [self.upgrade_record()])
        self.assertFalse(missing.exists())

    def test_private_bus_stop_state_survives_daemon_restart(self):
        processes = []
        state = self.root / "bus-state"
        state.mkdir()
        try:
            bus = subprocess.Popen(["dbus-daemon", "--session", "--nofork", "--print-address=1"],
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, start_new_session=True)
            processes.append(bus)
            with selectors.DefaultSelector() as selector:
                selector.register(bus.stdout, selectors.EVENT_READ)
                self.assertTrue(selector.select(timeout=5), "Private bus did not start")
            environment = dict(os.environ, DBUS_SESSION_BUS_ADDRESS=bus.stdout.readline().strip(),
                               PYTHONDONTWRITEBYTECODE="1",
                               PYTHONPATH=os.pathsep.join(str(ROOT / name) for name in ("engine", "daemon", "cli")))
            bootstrap = ("import importlib.util,sys; from pathlib import Path; "
                         f"root=Path({str(ROOT)!r}); "
                         "spec=importlib.util.spec_from_file_location('cyberlab.schemas',root/'schemas/__init__.py',submodule_search_locations=[str(root/'schemas')]); "
                         "sys.modules['cyberlab.schemas']=importlib.util.module_from_spec(spec); spec.loader.exec_module(sys.modules['cyberlab.schemas']); "
                         "from cyberlabd.main import main; raise SystemExit(main())")

            def cli(*arguments, check=True):
                return subprocess.run([sys.executable, "-B", "-m", "cyberlab_cli.main", "--test-session-bus", *arguments],
                                      env=environment, capture_output=True, text=True, timeout=15, check=check)

            with (state / "daemon.log").open("w") as log:
                def start_daemon():
                    daemon = subprocess.Popen([sys.executable, "-B", "-c", bootstrap, "--test-session-bus",
                                               "--catalog", str(self.root), "--authoring-state", str(state / "drafts.sqlite3")],
                                              env=environment, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
                    processes.append(daemon)
                    for _ in range(40):
                        ready = cli("info", check=False)
                        if ready.returncode == 0:
                            self.assertIn("runtime:memory-test", json.loads(ready.stdout)["capabilities"])
                            return daemon
                        if daemon.poll() is not None:
                            self.fail((state / "daemon.log").read_text())
                        time.sleep(0.1)
                    self.fail(ready.stderr)

                daemon = start_daemon()
                session = json.loads(cli("start", "fixture", "--no-terminals").stdout)
                saved = json.loads(cli("save", session["id"]).stdout)
                stopped = json.loads(cli("stop", session["id"]).stdout)
                self.assertEqual(stopped["state"], "STOPPED")
                os.killpg(daemon.pid, signal.SIGTERM)
                daemon.wait(timeout=5)
                start_daemon()
                restored = json.loads(cli("status", session["id"]).stdout)
                self.assertEqual(restored, stopped)
                self.assertEqual(restored["checkpoint_at"], saved["checkpoint_at"])
                resumed = json.loads(cli("resume", session["id"], "--no-terminals").stdout)
                self.assertEqual(resumed["state"], "RUNNING")
                self.assertEqual(json.loads(cli("suspend", session["id"]).stdout)["state"], "SUSPENDED")
        finally:
            for process in reversed(processes):
                if process.poll() is None:
                    os.killpg(process.pid, signal.SIGTERM)
                    try:
                        process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        os.killpg(process.pid, signal.SIGKILL)
                        process.wait()
                for stream in (process.stdout, process.stderr):
                    if stream:
                        stream.close()


if __name__ == "__main__":
    unittest.main(verbosity=2)
