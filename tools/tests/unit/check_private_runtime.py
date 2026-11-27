"""Private GUI runtime checks; no package manager or host installation."""

import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class PrivateRuntimeChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.runtime = load('private_runtime', ROOT / 'tools/install/private_runtime.py')
        cls.launcher = load('private_launcher', ROOT / 'ui/launcher.py')

    def test_pinned_downloads_have_integrity_and_https(self):
        manifest = self.runtime.manifest()
        self.assertEqual(manifest['qt'], '6.10.3')
        self.assertEqual(manifest['quickshell'], '0.3.2')
        self.assertEqual(len(manifest['downloads']), 7)
        for item in manifest['downloads']:
            self.assertTrue(item['url'].startswith('https://'))
            self.assertRegex(item['sha256'], r'^[0-9a-f]{64}$')
            self.assertGreater(item['size'], 0)

    def test_archive_listing_rejects_paths_and_limits(self):
        for path in ('/etc/passwd', '../escape', 'lib/../../escape', 'C:/escape', r'lib\escape'):
            with self.subTest(path=path), self.assertRaises(ValueError):
                self.runtime.validate_listing(f'Path = {path}\nSize = 12\n')
        with self.assertRaises(ValueError):
            self.runtime.validate_listing('Path = lib/large\nSize = 4000000000\n')
        self.runtime.validate_listing('Path = lib/qt.so\nSize = 123\n')

    def test_payload_audit_rejects_escape_link_and_special_file(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'escape').symlink_to('/etc/passwd')
            with self.assertRaises(ValueError):
                self.runtime.audit_tree(root)
            (root / 'escape').unlink()
            os.mkfifo(root / 'pipe')
            with self.assertRaises(ValueError):
                self.runtime.audit_tree(root)

    def test_internal_relative_symlinks_remain_relocatable(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'real').write_text('fixture')
            (root / 'link').symlink_to('real')
            self.runtime.audit_tree(root)

    def test_install_parent_is_readable_despite_restrictive_umask(self):
        with tempfile.TemporaryDirectory() as directory:
            parent = Path(directory) / 'cyberlab'
            previous = os.umask(0o077)
            try:
                self.runtime.create_runtime_parent(parent)
            finally:
                os.umask(previous)
            self.assertEqual(parent.stat().st_mode & 0o777, 0o755)
            parent.chmod(0o700)
            with self.assertRaises(FileExistsError):
                self.runtime.create_runtime_parent(parent)
            self.assertEqual(parent.stat().st_mode & 0o777, 0o700)

    def test_source_archive_rejects_traversal_before_extracting(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            archive = root / 'source.tar.gz'
            with tarfile.open(archive, 'w:gz') as bundle:
                entry = tarfile.TarInfo('../escape')
                entry.size = 4
                bundle.addfile(entry, io.BytesIO(b'evil'))
            with self.assertRaises(ValueError):
                self.runtime.extract_source(archive, root / 'source')
            self.assertFalse((root / 'escape').exists())

    def test_source_archive_rejects_writing_through_a_link(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            archive = root / 'source.tar'
            with tarfile.open(archive, 'w') as bundle:
                link = tarfile.TarInfo('alias')
                link.type = tarfile.SYMTYPE
                link.linkname = 'real'
                bundle.addfile(link)
                entry = tarfile.TarInfo('alias/file')
                entry.size = 4
                bundle.addfile(entry, io.BytesIO(b'data'))
            with self.assertRaises(ValueError):
                self.runtime.extract_source(archive, root / 'output')
            self.assertFalse((root / 'output').exists())

    def test_bad_checksum_stops_before_extraction(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / 'archive'
            def fetch(*args, **kwargs):
                target.write_bytes(b'bad')
            with patch.object(self.runtime.subprocess, 'run', side_effect=fetch):
                with self.assertRaisesRegex(ValueError, 'SHA-256'):
                    self.runtime.download({'size': 3, 'sha256': '0' * 64,
                                           'url': 'https://example.invalid/qt', 'name': 'qt'}, target)

    def test_root_cannot_build_downloaded_code(self):
        with patch.object(self.runtime.os, 'geteuid', return_value=0), \
             patch.object(self.runtime, 'download') as fetch:
            with self.assertRaisesRegex(ValueError, 'without root'):
                self.runtime.build(Path('/unused'))
            fetch.assert_not_called()

    def test_timeout_terminates_build_process_group(self):
        with tempfile.TemporaryDirectory() as directory:
            marker = Path(directory) / 'child'
            program = ('import subprocess,time; from pathlib import Path; '
                       'child=subprocess.Popen(["sleep","30"]); '
                       f'Path({str(marker)!r}).write_text(str(child.pid)); time.sleep(30)')
            with self.assertRaises(subprocess.TimeoutExpired):
                self.runtime.run_group([sys.executable, '-c', program], timeout=1)
            pid = marker.read_text()
            status = Path('/proc') / pid / 'stat'
            try:
                state = status.read_text().split()[2]
            except (FileNotFoundError, ProcessLookupError):
                state = 'X'
            self.assertIn(state, ('Z', 'X'))

    def test_launcher_does_not_inherit_host_qt_plugins(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'studio').mkdir()
            (root / 'studio/shell.qml').write_text('fixture')
            inherited = {'DISPLAY': ':99', 'QT_PLUGIN_PATH': '/evil', 'QML_IMPORT_PATH': '/evil',
                         'QT_QPA_PLATFORMTHEME': 'evil', 'LD_LIBRARY_PATH': '/evil',
                         'QT_QPA_PLATFORM_PLUGIN_PATH': '/evil', 'LD_PRELOAD': '/evil'}
            with patch.dict(os.environ, inherited, clear=True), \
                 patch.object(self.launcher.os, 'geteuid', return_value=1000), \
                 patch.object(self.launcher, 'resolve_quickshell', return_value=Path('/fixture/quickshell')), \
                 patch.object(self.launcher, 'files', return_value=root), \
                 patch.object(self.launcher.subprocess, 'call', return_value=0) as launch:
                self.assertEqual(self.launcher.launch(), 0)
                environment = launch.call_args.kwargs['env']
                for key in inherited:
                    if key != 'DISPLAY':
                        self.assertNotIn(key, environment)
                self.assertEqual(environment['DISPLAY'], ':99')

    def test_runtime_choice_prefers_managed_private_over_native(self):
        private = Path('/usr/lib/cyberlab/gui-runtime/bin/quickshell')
        with patch.object(self.launcher, 'private_quickshell', return_value=private), \
             patch.object(self.launcher, 'native_quickshell') as native:
            self.assertEqual(self.launcher.runtime_quickshell(), private)
            native.assert_not_called()

    def test_no_private_runtime_preserves_native_selection(self):
        with patch.object(self.launcher, 'private_quickshell', return_value=None), \
             patch.object(self.launcher, 'native_quickshell', return_value=Path('/usr/bin/qs')):
            self.assertEqual(self.launcher.runtime_quickshell(), Path('/usr/bin/qs'))

    def test_untrusted_private_runtime_is_not_silently_used(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'bin').mkdir()
            (root / 'bin/quickshell').write_bytes(b'\x7fELF' + b'\0' * 20)
            (root / 'bin/quickshell').chmod(0o755)
            (root / 'manifest.json').write_text('{}')
            with patch.object(self.launcher, 'PRIVATE_RUNTIME', root):
                with self.assertRaises(ValueError):
                    self.launcher.private_quickshell()

    def test_private_runtime_manifest_must_be_a_mapping(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name in ('bin', 'qt/lib', 'qt/plugins', 'qt/qml'):
                (root / name).mkdir(parents=True, exist_ok=True)
            (root / 'bin/quickshell').write_bytes(b'\x7fELF' + b'\0' * 20)
            (root / 'bin/quickshell').chmod(0o755)
            (root / 'bin/qt.conf').write_text('[Paths]\nPrefix=../qt\n')
            (root / 'manifest.json').write_text('[]')
            original = Path.lstat
            def trusted(path):
                info = list(original(path))
                info[4] = 0
                info[0] &= ~0o022
                return os.stat_result(info)
            with patch.object(self.launcher, 'PRIVATE_RUNTIME', root), patch.object(Path, 'lstat', trusted):
                with self.assertRaisesRegex(ValueError, 'Unsupported'):
                    self.launcher.private_quickshell()

    def test_noble_private_selection_does_not_add_qt_packages(self):
        script = f'''
set -euo pipefail
source "{ROOT}/tools/install/packages.sh"
family=debian; ID=ubuntu; VERSION_CODENAME=noble; gui_runtime=private
configure_packages
printf '%s\\n' "${{host_packages[@]}}"
'''
        result = subprocess.run(['/bin/bash', '-c', script], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        packages = result.stdout.splitlines()
        self.assertIn('libcli11-dev', packages)
        self.assertIn('cmake', packages)
        self.assertIn('libxcb-shape0', packages)
        self.assertFalse(any('qt6' in item or 'qml6' in item for item in packages))

    def test_missing_display_library_is_not_hidden_by_offscreen_probe(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            plugins = root / 'qt/plugins/platforms'
            plugins.mkdir(parents=True)
            (plugins / 'libqxcb.so').touch()
            (plugins / 'libqwayland.so').touch()
            with patch.object(self.runtime.subprocess, 'check_output', return_value='libxcb-shape.so.0 => not found'):
                with self.assertRaisesRegex(ValueError, 'not found'):
                    self.runtime.verify_display_libraries(root)

    def test_private_selection_never_adds_a_repository(self):
        result = subprocess.run(['/bin/bash', '-c', f'''
set -euo pipefail
source "{ROOT}/tools/install/repositories.sh"
mode=install; gui_runtime=private
native_quickshell_present() {{ exit 9; }}
enable_quickshell_repository() {{ exit 10; }}
ensure_quickshell_source
'''], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_runtime_selection_keeps_platform_and_architecture_boundaries(self):
        cases = (
            ('debian', 'noble', 'x86_64', False, False, False, 'private'),
            ('debian', 'noble', 'aarch64', False, False, False, 'native'),
            ('debian', 'trixie', 'x86_64', False, False, False, 'native'),
            ('arch', '', 'x86_64', False, False, False, 'native'),
            ('debian', 'noble', 'x86_64', True, False, False, 'native'),
            ('debian', 'noble', 'x86_64', False, True, False, 'native'),
            ('debian', 'noble', 'x86_64', True, True, True, 'private'),
        )
        for family, suite, machine, native, package, private, expected in cases:
            with self.subTest(case=(family, suite, machine, native, package, private)):
                result = subprocess.run(['/bin/bash', '-c', f'''
set -euo pipefail
source "{ROOT}/tools/install/packages.sh"
family={family}; UBUNTU_CODENAME={suite}
uname() {{ printf '%s' {machine}; }}
native_quickshell_present() {{ return {0 if native else 1}; }}
private_quickshell_present() {{ return {0 if private else 1}; }}
package_available() {{ return {0 if package else 1}; }}
select_gui_runtime
printf '%s' "$gui_runtime"
'''], capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stdout, expected)


if __name__ == '__main__':
    unittest.main()
