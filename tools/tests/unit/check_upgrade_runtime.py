"""Isolated updater readiness checks; never invokes services or Docker."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from contextlib import closing, ExitStack
import fcntl
import os
import sqlite3
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import zipfile

from tools.install import upgrade_runtime as updater


class ReadinessChecks(unittest.TestCase):
    def test_ready_api_returns_without_waiting(self):
        info = {'capabilities': ['runtime:docker']}
        with patch.object(updater, 'cli', return_value=info) as cli, \
             patch.object(updater, 'run'), patch.object(updater.time, 'sleep') as sleep:
            self.assertEqual(updater.wait_for_daemon(1000), info)
            self.assertEqual(cli.call_args.args, (1000, 'info'))
            sleep.assert_not_called()

    def test_bus_name_owned_before_api_is_ready(self):
        pending = subprocess.CalledProcessError(1, ['cyberlab', 'info'], stderr='FAIL: Unknown method GetInfo')
        info = {'capabilities': ['runtime:docker']}
        with patch.object(updater, 'cli', side_effect=[pending, info]) as cli, \
             patch.object(updater, 'run'), patch.object(updater.time, 'sleep'):
            self.assertEqual(updater.wait_for_daemon(1000), info)
            self.assertEqual(cli.call_count, 2)
            self.assertTrue(all(call.args == (1000, 'info') for call in cli.call_args_list))

    def test_deadline_keeps_the_actual_cli_error(self):
        pending = subprocess.CalledProcessError(1, ['cyberlab', 'info'], stderr='FAIL: Unknown method GetInfo')
        with patch.object(updater, 'cli', side_effect=pending), patch.object(updater, 'run'), \
             patch.object(updater.time, 'monotonic', side_effect=[0, 0, 2]), \
             patch.object(updater.time, 'sleep'):
            with self.assertRaisesRegex(RuntimeError, 'Unknown method GetInfo'):
                updater.wait_for_daemon(1000, timeout=1)

    def test_stopped_service_fails_without_retrying_api(self):
        stopped = subprocess.CalledProcessError(3, ['systemctl', 'is-active'])
        with patch.object(updater, 'run', side_effect=stopped), patch.object(updater, 'cli') as cli:
            with self.assertRaises(subprocess.CalledProcessError):
                updater.wait_for_daemon(1000)
            cli.assert_not_called()

    def test_probe_timeout_is_retried_without_mutating_state(self):
        pending = subprocess.TimeoutExpired(['cyberlab', 'info'], 5)
        info = {'capabilities': ['runtime:docker']}
        with patch.object(updater, 'cli', side_effect=[pending, info]), \
             patch.object(updater, 'run'), patch.object(updater.time, 'sleep'):
            self.assertEqual(updater.wait_for_daemon(1000), info)

    def test_invalid_api_response_is_not_hidden_by_retry(self):
        with patch.object(updater, 'cli', side_effect=ValueError('Invalid JSON')) as cli, \
             patch.object(updater, 'run'):
            with self.assertRaisesRegex(ValueError, 'Invalid JSON'):
                updater.wait_for_daemon(1000)
            self.assertEqual(cli.call_count, 1)

    def test_command_failure_reports_captured_stderr(self):
        error = subprocess.CalledProcessError(1, ['cyberlab', 'info'], stderr='FAIL: permission denied')
        self.assertIn('FAIL: permission denied', updater.error_detail(error))

    def test_cli_probe_has_a_bounded_subprocess_timeout(self):
        with patch.object(updater, 'run', return_value=SimpleNamespace(stdout='{}')) as run:
            self.assertEqual(updater.cli(1000, 'info', timeout=3), {})
            self.assertEqual(run.call_args.kwargs['timeout'], 3)


class UpgradeChecks(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.root = Path(self.stack.enter_context(tempfile.TemporaryDirectory()))
        self.app = self.root / 'app'
        self.venv = self.app / 'venv'
        self.venv.mkdir(parents=True)
        (self.venv / 'version').write_text('old')
        self.config = self.root / 'daemon.toml'
        self.config.write_text('allowed_uids = [1000, 1001]\n')
        self.state = self.root / 'authoring'
        self.state.mkdir(mode=0o700)
        self.database = self.state / 'practice.sqlite3'
        with closing(sqlite3.connect(self.database)) as connection, connection:
            connection.execute('CREATE TABLE saved_sessions (id TEXT, owner INTEGER, state TEXT, checkpoint_at TEXT, updated_at TEXT)')
        self.database.chmod(0o600)
        self.backup = self.root / 'backup'
        self.backup.mkdir(mode=0o700)
        self.proc = self.root / 'proc'
        self.proc.mkdir()
        self.lock = self.root / 'installer.lock'
        self.stack.enter_context(patch.object(updater, 'MAINTENANCE_LOCK', self.root / 'maintenance.lock', create=True))
        self.wheel = self.make_wheel(self.root, 'cyberlab_engine-1-py3-none-any.whl')
        self.receipt = self.app / 'installation.json'
        self.receipt.write_bytes(b'old receipt\n')
        self.receipt.chmod(0o640)
        self.commands = []
        self.sessions = {1000: [], 1001: []}
        self.on_stop = None
        self.on_install = None
        for name, value in {'APP': self.app, 'CONFIG': self.config, 'STATE': self.state,
                            'PROC': self.proc, 'INSTALLER_LOCK': self.lock}.items():
            self.stack.enter_context(patch.object(updater, name, value, create=True))
        self.stack.enter_context(patch.object(updater, 'check_admin_path'))
        self.stack.enter_context(patch.object(updater, 'run', side_effect=self.command))
        self.stack.enter_context(patch.object(updater, 'cli', side_effect=self.cli))

    def make_wheel(self, directory, name, dependency=None):
        wheel = directory / name
        with zipfile.ZipFile(wheel, 'w') as archive:
            archive.writestr('package/__init__.py', 'value = 1\n')
            metadata = 'Metadata-Version: 2.1\nName: package\nVersion: 1\n'
            if dependency:
                metadata += f'Requires-Dist: {dependency}\n'
            archive.writestr('package-1.dist-info/METADATA', metadata)
        return wheel

    def cli(self, uid, operation, **kwargs):
        if operation == 'info':
            return {'capabilities': ['runtime:docker', 'maintenance-lock-v1']}
        if operation == 'sessions':
            return self.sessions[uid]
        if operation == 'labs':
            return [{'id': 'lab', 'name': 'Lab', 'version': '1'}]
        raise AssertionError(operation)

    def command(self, *arguments, **kwargs):
        command = tuple(str(argument) for argument in arguments)
        self.commands.append(command)
        if command[:2] == ('/usr/bin/systemctl', 'stop') and self.on_stop:
            action, self.on_stop = self.on_stop, None
            action()
        if 'pip' in command and 'install' in command:
            (self.venv / 'version').write_text('new')
            if self.on_install:
                self.on_install()
        return SimpleNamespace(stdout='')

    def add_process(self, pid, arguments):
        process = self.proc / str(pid)
        process.mkdir()
        (process / 'cmdline').write_bytes(b'\0'.join(argument.encode() for argument in arguments) + b'\0')

    def assert_not_stopped(self):
        self.assertNotIn(('/usr/bin/systemctl', 'stop', updater.SERVICE), self.commands)

    def test_legacy_install_remains_no_deps(self):
        updater.upgrade(self.wheel, 1000, self.backup)
        install = next(command for command in self.commands if 'install' in command)
        self.assertIn('--no-deps', install)
        self.assertIn('--no-index', install)

    def test_legacy_daemon_without_barrier_is_not_stopped(self):
        with patch.object(updater, 'wait_for_daemon', return_value={'capabilities': ['runtime:docker']}):
            with self.assertRaisesRegex(ValueError, 'maintenance'):
                updater.upgrade(self.wheel, 1000, self.backup)
        self.assert_not_stopped()

    def test_background_preparation_is_not_cancelled_by_upgrade(self):
        with patch.object(updater, 'wait_for_daemon', return_value={'capabilities': ['runtime:docker', 'maintenance-lock-v1', 'maintenance-busy']}):
            with self.assertRaisesRegex(ValueError, 'preparation'):
                updater.upgrade(self.wheel, 1000, self.backup)
        self.assert_not_stopped()

    def test_active_request_prevents_upgrade_before_service_stop(self):
        import fcntl
        with updater.MAINTENANCE_LOCK.open('w') as active:
            fcntl.flock(active.fileno(), fcntl.LOCK_SH)
            with self.assertRaises(RuntimeError):
                updater.upgrade(self.wheel, 1000, self.backup)
        self.assert_not_stopped()

    def test_offline_migration_requires_explicitly_inactive_service(self):
        with patch.object(updater, 'run', return_value=SimpleNamespace(stdout='active\n')):
            with self.assertRaisesRegex(ValueError, 'inactive'):
                updater.upgrade(self.wheel, 1000, self.backup, offline=True)
        self.assert_not_stopped()

    def test_offline_migration_uses_stored_identity_not_live_legacy_api(self):
        def command(*arguments, **kwargs):
            if 'ActiveState' in arguments:
                return SimpleNamespace(stdout='inactive\n')
            if '-c' in arguments:
                return SimpleNamespace(stdout='[{"id":"lab","name":"Lab","version":"1"}]')
            return self.command(*arguments, **kwargs)
        with patch.object(updater, 'run', side_effect=command):
            updater.upgrade(self.wheel, 1000, self.backup, offline=True)
        self.assertEqual((self.venv / 'version').read_text(), 'new')

    def test_repeated_termination_cannot_interrupt_rollback(self):
        import signal
        import os
        previous = signal.signal(signal.SIGTERM, lambda *_: (_ for _ in ()).throw(SystemExit(143)))
        try:
            def interrupt_install():
                self.on_stop = lambda: os.kill(os.getpid(), signal.SIGTERM)
                raise KeyboardInterrupt()
            self.on_install = interrupt_install
            with self.assertRaises(KeyboardInterrupt):
                updater.upgrade(self.wheel, 1000, self.backup)
            self.assertEqual((self.venv / 'version').read_text(), 'old')
        finally:
            signal.signal(signal.SIGTERM, previous)

    def test_wheelhouse_installs_dependencies_from_private_staging(self):
        wheelhouse = self.root / 'dependencies'
        wheelhouse.mkdir()
        dependency = self.make_wheel(wheelhouse, 'dependency-1-py3-none-any.whl')
        updater.upgrade(self.wheel, 1000, self.backup, wheelhouse=wheelhouse)
        install = next(command for command in self.commands if 'install' in command)
        self.assertNotIn('--no-deps', install)
        self.assertIn('--no-index', install)
        self.assertIn('--only-binary=:all:', install)
        self.assertIn('--isolated', install)
        self.assertIn('--no-cache-dir', install)
        staged = Path(install[install.index('--find-links') + 1])
        self.assertTrue(staged.is_relative_to(self.backup))
        self.assertEqual((staged / dependency.name).read_bytes(), dependency.read_bytes())

    def test_wheelhouse_rejects_direct_url_dependencies_before_stop(self):
        wheelhouse = self.root / 'dependencies'
        wheelhouse.mkdir()
        self.make_wheel(wheelhouse, 'dependency-1-py3-none-any.whl', 'remote @ https://example.invalid/remote.whl')
        with self.assertRaisesRegex(ValueError, 'direct|URL'):
            updater.upgrade(self.wheel, 1000, self.backup, wheelhouse=wheelhouse)
        self.assert_not_stopped()

    def test_wheelhouse_rejects_symlinks_before_stop(self):
        wheelhouse = self.root / 'dependencies'
        wheelhouse.mkdir()
        (wheelhouse / self.wheel.name).symlink_to(self.wheel)
        with self.assertRaises((ValueError, OSError)):
            updater.upgrade(self.wheel, 1000, self.backup, wheelhouse=wheelhouse)
        self.assert_not_stopped()

    def test_low_disk_space_fails_before_stopping_daemon(self):
        with patch.object(updater.shutil, 'disk_usage', return_value=SimpleNamespace(free=0)):
            with self.assertRaisesRegex(ValueError, 'space'):
                updater.upgrade(self.wheel, 1000, self.backup)
        self.assert_not_stopped()

    def test_any_user_studio_blocks_without_killing(self):
        self.add_process(1234, ['/usr/bin/qs', '--path', '/home/other/venv/lib/python3.13/site-packages/cyberlab_studio/studio'])
        with self.assertRaisesRegex(ValueError, 'Studio.*1234'):
            updater.upgrade(self.wheel, 1000, self.backup)
        self.assert_not_stopped()
        self.assertTrue((self.proc / '1234').exists())

    def test_unrelated_quickshell_is_allowed(self):
        self.add_process(1234, ['/usr/bin/qs', '--path', '/home/other/SownteeShell'])
        updater.upgrade(self.wheel, 1000, self.backup)

    def test_launcher_process_blocks_before_quickshell_starts(self):
        self.add_process(1234, ['/usr/bin/python', '-I', '-m', 'cyberlab_studio.launcher'])
        with self.assertRaisesRegex(ValueError, 'Studio'):
            updater.upgrade(self.wheel, 1000, self.backup)
        self.assert_not_stopped()

    def test_callback_is_after_checks_and_receipt_commits_on_success(self):
        def verify():
            self.assertEqual((self.venv / 'version').read_text(), 'new')
            self.assertIn(('/usr/bin/systemctl', 'start', updater.SERVICE), self.commands)
            self.assertFalse((self.backup / 'verification.json').exists())
            self.receipt.write_bytes(b'new receipt\n')
        updater.upgrade(self.wheel, 1000, self.backup, verify_callback=verify)
        self.assertEqual(self.receipt.read_bytes(), b'new receipt\n')
        self.assertTrue((self.backup / 'verification.json').exists())

    def test_receipt_and_runtime_restore_after_callback_failure(self):
        def verify():
            updater.replace_file(self.receipt, b'new receipt\n', 0o600)
            raise RuntimeError('smoke failed')
        with self.assertRaisesRegex(RuntimeError, 'smoke failed'):
            updater.upgrade(self.wheel, 1000, self.backup, verify_callback=verify)
        self.assertEqual((self.venv / 'version').read_text(), 'old')
        self.assertEqual(self.receipt.read_bytes(), b'old receipt\n')
        self.assertEqual(self.receipt.stat().st_mode & 0o777, 0o640)
        self.assertEqual((self.backup / 'installation.json').read_bytes(), b'old receipt\n')

    def test_new_receipt_removed_after_callback_interrupt(self):
        self.receipt.unlink()
        def verify():
            self.receipt.write_bytes(b'new receipt\n')
            raise KeyboardInterrupt()
        with self.assertRaises(KeyboardInterrupt):
            updater.upgrade(self.wheel, 1000, self.backup, verify_callback=verify)
        self.assertFalse(self.receipt.exists())
        self.assertEqual((self.venv / 'version').read_text(), 'old')
        self.assertFalse((self.backup / 'verification.json').exists())

    def test_interrupt_during_install_restores_runtime(self):
        def interrupt():
            raise KeyboardInterrupt()
        self.on_install = interrupt
        with self.assertRaises(KeyboardInterrupt):
            updater.upgrade(self.wheel, 1000, self.backup)
        self.assertEqual((self.venv / 'version').read_text(), 'old')

    def test_saved_session_started_during_stop_blocks_install(self):
        def race():
            with closing(sqlite3.connect(self.database)) as connection, connection:
                connection.execute("INSERT INTO saved_sessions VALUES ('race', 1001, 'RUNNING', 'now', 'now')")
        self.on_stop = race
        with self.assertRaisesRegex(ValueError, 'Session'):
            updater.upgrade(self.wheel, 1000, self.backup)
        self.assertEqual((self.venv / 'version').read_text(), 'old')
        self.assertFalse(any('install' in command for command in self.commands))

    def test_new_stopped_checkpoint_after_preflight_is_not_overwritten(self):
        def race():
            with closing(sqlite3.connect(self.database)) as connection, connection:
                connection.execute("INSERT INTO saved_sessions VALUES ('race', 1001, 'STOPPED', 'now', 'now')")
        self.on_stop = race
        with self.assertRaisesRegex(ValueError, 'Session'):
            updater.upgrade(self.wheel, 1000, self.backup)
        self.assertFalse(any('install' in command for command in self.commands))
        with closing(sqlite3.connect(self.database)) as connection:
            self.assertEqual(connection.execute('SELECT id FROM saved_sessions').fetchall(), [('race',)])

    def test_standalone_upgrade_contends_with_installer(self):
        with self.lock.open('w') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            with self.assertRaisesRegex(RuntimeError, 'installation|update'):
                updater.upgrade(self.wheel, 1000, self.backup)
        self.assert_not_stopped()

    def test_inherited_lock_is_reused_and_remains_held(self):
        with self.lock.open('w') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            updater.upgrade(self.wheel, 1000, self.backup, lock_fd=lock.fileno())
            with self.lock.open('r') as competitor:
                with self.assertRaises(BlockingIOError):
                    fcntl.flock(competitor, fcntl.LOCK_EX | fcntl.LOCK_NB)

    def test_unrelated_inherited_descriptor_is_rejected(self):
        self.lock.touch()
        with self.config.open('r') as unrelated:
            with self.assertRaisesRegex(ValueError, 'lock'):
                updater.upgrade(self.wheel, 1000, self.backup, lock_fd=unrelated.fileno())
        self.assert_not_stopped()


if __name__ == '__main__':
    unittest.main(verbosity=2)
