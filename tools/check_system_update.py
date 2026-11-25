#!/usr/bin/env python3
import importlib.util
import gzip
import io
import json
from pathlib import Path
import sys
import tarfile
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'cli'))
from cyberlab_cli import system_update as update
spec = importlib.util.spec_from_file_location('runtime_admin', ROOT / 'tools/runtime_admin.py')
admin = importlib.util.module_from_spec(spec)
spec.loader.exec_module(admin)

COMMIT = 'a' * 40

def archive(entries):
    output = io.BytesIO()
    with tarfile.open(fileobj=output, mode='w:gz') as bundle:
        for name, content, kind in entries:
            entry = tarfile.TarInfo('CyberLab-' + COMMIT + '/' + name)
            entry.type = kind
            entry.size = len(content) if kind == tarfile.REGTYPE else 0
            entry.linkname = '/etc/passwd' if kind == tarfile.SYMTYPE else ''
            bundle.addfile(entry, io.BytesIO(content))
    return output.getvalue()

class UpdateTests(unittest.TestCase):
    def test_extract_regular_only(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / 'source.tar.gz'
            source.write_bytes(archive([('install.sh', b'echo ok', tarfile.REGTYPE)]))
            update.extract_snapshot(source, root / 'out', COMMIT)
            self.assertEqual((root / 'out/install.sh').read_bytes(), b'echo ok')

    def test_reject_unsafe_and_duplicate_entries(self):
        for entries in [
            [('../escape', b'x', tarfile.REGTYPE)],
            [('link', b'', tarfile.SYMTYPE)],
            [('file', b'a', tarfile.REGTYPE), ('file', b'b', tarfile.REGTYPE)],
            [('a//b', b'x', tarfile.REGTYPE)],
        ]:
            with self.subTest(entries=entries), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                source = root / 'archive'
                source.write_bytes(archive(entries))
                with self.assertRaises(ValueError):
                    update.extract_snapshot(source, root / 'out', COMMIT)

    def test_bounded_expansion(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(update, 'MAX_EXPANDED', 5):
            root = Path(directory)
            source = root / 'archive'
            source.write_bytes(archive([('file', b'123456', tarfile.REGTYPE)]))
            with self.assertRaises(ValueError):
                update.extract_snapshot(source, root / 'out', COMMIT)

    def test_tar_padding_also_counts_toward_expansion(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(update, 'MAX_EXPANDED', 10240):
            root = Path(directory)
            source = root / 'archive'
            source.write_bytes(gzip.compress(b'\0' * 10241))
            with self.assertRaises(ValueError):
                update.extract_snapshot(source, root / 'out', COMMIT)

    def test_unknown_receipt_not_latest(self):
        with tempfile.TemporaryDirectory() as directory:
            receipt = Path(directory) / 'installation.json'
            self.assertIsNone(update.installed_commit(receipt))
            receipt.write_text(json.dumps({'sha256': COMMIT}))
            self.assertIsNone(update.installed_commit(receipt))
            receipt.write_text(json.dumps({'commit': COMMIT}))
            self.assertEqual(update.installed_commit(receipt), COMMIT)

    def test_check_never_installs(self):
        with patch.object(update, 'latest_commit', return_value=COMMIT), patch.object(update, 'installed_commit', return_value=None), patch.object(update, 'install_snapshot') as install:
            self.assertEqual(update.run_update(check=True), 0)
            install.assert_not_called()

    def test_remote_reference_must_resolve_to_commit(self):
        for payload in ({'object': {'type': 'commit', 'sha': COMMIT}}, {'object': {'type': 'tag', 'sha': COMMIT}}, [], {'object': None}):
            def fetch(url, stream, limit):
                self.assertTrue(url.endswith('/git/ref/heads/master'))
                stream.write(json.dumps(payload).encode())
            with self.subTest(payload=payload), patch.object(update, 'download', side_effect=fetch):
                if payload == {'object': {'type': 'commit', 'sha': COMMIT}}:
                    self.assertEqual(update.latest_commit(), COMMIT)
                else:
                    with self.assertRaises(ValueError):
                        update.latest_commit()

    def test_offline_check_keeps_installation_unchanged(self):
        with patch.object(update, 'latest_commit', side_effect=OSError('offline')), patch.object(update, 'install_snapshot') as install:
            self.assertEqual(update.run_update(check=True), 1)
            install.assert_not_called()

    def test_cli_update_dispatch_does_not_contact_daemon(self):
        from cyberlab_cli import main
        with patch.object(sys, 'argv', ['cyberlab', 'update', '--check']), patch.object(update, 'run_update', return_value=0) as operation, patch.object(main.asyncio, 'run') as daemon:
            self.assertEqual(main.main(), 0)
            operation.assert_called_once_with(check=True, json_output=False)
            daemon.assert_not_called()

    def test_same_commit_no_install(self):
        with patch.object(update, 'latest_commit', return_value=COMMIT), patch.object(update, 'installed_commit', return_value=COMMIT), patch.object(update, 'install_snapshot') as install:
            self.assertEqual(update.run_update(), 0)
            install.assert_not_called()

    def test_new_install_config_private(self):
        spec = importlib.util.spec_from_file_location('runtime_admin', ROOT / 'tools/runtime_admin.py')
        admin = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(admin)
        from types import SimpleNamespace
        catalog, config, dropin = admin.configuration(SimpleNamespace(pw_dir='/home/test', pw_uid=1000, pw_gid=1000))
        self.assertEqual(catalog, Path('/var/lib/cyberlab/labs'))
        self.assertNotIn(b'/home', config + dropin)
        self.assertNotIn(b'BindPaths', dropin)
        self.assertNotIn(b'SupplementaryGroups', dropin)

    def test_build_environment_applied_after_switching_user(self):
        from types import SimpleNamespace
        account = SimpleNamespace(pw_dir='/home/learner', pw_uid=1000, pw_name='learner')
        with patch.object(admin.os, 'geteuid', return_value=0), patch.object(admin.subprocess, 'run', return_value=SimpleNamespace(returncode=0)) as run:
            admin.run('/usr/bin/python3', account=account, build_home=Path('/var/tmp/private-build'))
        command = run.call_args.args[0]
        self.assertIn('/usr/bin/env', command)
        self.assertIn('HOME=/var/tmp/private-build', command)

    def test_root_snapshot_readable_but_not_writable_by_desktop_group(self):
        from types import SimpleNamespace
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / 'source'
            source.mkdir(mode=0o700)
            script = source / 'probe.py'
            script.write_text('pass')
            with patch.object(update.os, 'geteuid', return_value=0), patch.object(update.os, 'chown') as ownership, patch.object(update.pwd, 'getpwnam', return_value=SimpleNamespace(pw_uid=1000, pw_gid=1000)):
                update.root_probe_access(root, source, ('--user', 'learner'))
            self.assertEqual(root.stat().st_mode & 0o777, 0o750)
            self.assertEqual(source.stat().st_mode & 0o777, 0o750)
            self.assertEqual(script.stat().st_mode & 0o777, 0o640)
            self.assertTrue(all(call.args[1:3] == (0, 1000) for call in ownership.call_args_list))

    def test_repeated_cancellation_waits_for_child_exit(self):
        import signal
        from unittest.mock import Mock
        process = Mock()
        process.poll.side_effect = [None, None, None, 0]
        def wait():
            self.assertEqual(signal.getsignal(signal.SIGTERM), signal.SIG_IGN)
            raise SystemExit(143)
        process.wait.side_effect = wait
        previous = signal.getsignal(signal.SIGTERM)
        update.finish_interrupted(process)
        self.assertEqual(process.wait.call_count, 2)
        self.assertEqual(signal.getsignal(signal.SIGTERM), previous)

    def test_snapshot_failure_cleans_system_temp(self):
        with tempfile.TemporaryDirectory() as directory:
            created = []
            temporary = tempfile.TemporaryDirectory
            def staging(**kwargs):
                stage = temporary(prefix=kwargs['prefix'], dir=directory)
                created.append(Path(stage.name))
                return stage
            with patch.object(update.tempfile, 'TemporaryDirectory', side_effect=staging), patch.object(update, 'download', side_effect=OSError('offline')), patch.object(update.shutil, 'disk_usage', return_value=type('Usage', (), {'free': 10**10})()):
                with self.assertRaises(OSError):
                    update.install_snapshot(COMMIT)
            self.assertTrue(created)
            self.assertFalse(created[0].exists())

    def test_installer_runs_exact_snapshot_and_cleans(self):
        with tempfile.TemporaryDirectory() as directory:
            temporary = tempfile.TemporaryDirectory
            def staging(**kwargs):
                return temporary(prefix=kwargs['prefix'], dir=directory)
            def fetch(url, stream, limit):
                self.assertIn(COMMIT, url)
                stream.write(archive([('tools/install/system.sh', b'echo test', tarfile.REGTYPE)]))
            def install(command, **kwargs):
                source = Path(kwargs['cwd'])
                self.assertEqual(json.loads((source / '.cyberlab-source.json').read_text())['commit'], COMMIT)
                self.assertEqual(command[-1], '--update')
                from types import SimpleNamespace
                return SimpleNamespace(wait=lambda: 0)
            with patch.object(update.tempfile, 'TemporaryDirectory', side_effect=staging), patch.object(update, 'download', side_effect=fetch), patch.object(update.subprocess, 'Popen', side_effect=install), patch.object(update.shutil, 'disk_usage', return_value=type('Usage', (), {'free': 10**10})()):
                self.assertEqual(update.install_snapshot(COMMIT, ('--update',)), 0)
            self.assertEqual(list(Path(directory).iterdir()), [])

    def test_receipt_source_requires_valid_metadata(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(admin, 'ROOT', Path(directory)):
            marker = Path(directory) / '.cyberlab-source.json'
            marker.write_text(json.dumps({'repository': update.REPOSITORY, 'commit': COMMIT}))
            self.assertEqual(admin.source_identity(None)['commit'], COMMIT)
            marker.write_text(json.dumps({'repository': 'other/repo', 'commit': COMMIT}))
            with self.assertRaises(ValueError):
                admin.source_identity(None)

    def test_retain_only_own_successful_backup(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            app = root / 'app'
            app.mkdir()
            old = root / 'cyberlab-app-install-old'
            old.mkdir(mode=0o700)
            (old / 'managed-backup.json').write_text(json.dumps({'managed_by': 'cyberlab-update-v1', 'result': 'passed'}))
            (app / 'managed-backup.json').write_text(json.dumps({'path': str(old)}))
            new = root / 'cyberlab-app-install-new'
            new.mkdir()
            with patch.object(admin, 'APP', app), patch.object(admin, 'BACKUP_ROOT', root):
                admin.retain_backup(new)
            self.assertFalse(old.exists())
            self.assertTrue(new.exists())

    def test_never_clean_unmanaged_backup(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            app = root / 'app'
            app.mkdir()
            old = root / 'cyberlab-app-install-old'
            old.mkdir(mode=0o700)
            (old / 'evidence').write_text('keep')
            (app / 'managed-backup.json').write_text(json.dumps({'path': str(old)}))
            new = root / 'cyberlab-app-install-new'
            new.mkdir()
            with patch.object(admin, 'APP', app), patch.object(admin, 'BACKUP_ROOT', root):
                admin.retain_backup(new)
            self.assertEqual((old / 'evidence').read_text(), 'keep')

if __name__ == '__main__':
    unittest.main()
