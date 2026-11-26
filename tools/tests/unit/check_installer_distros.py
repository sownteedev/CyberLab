#!/usr/bin/env python3
"""Installer fixtures only: never run a host package manager or change services."""

from pathlib import Path
from contextlib import redirect_stdout
import importlib.util
import io
import shlex
import subprocess
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]
SPEC = importlib.util.spec_from_file_location('installer_admin', ROOT / 'tools/install/runtime_admin.py')
ADMIN = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ADMIN)


class InstallerDistroChecks(unittest.TestCase):
    def shell(self, script):
        prefix = f'''
set -euo pipefail
ROOT={shlex.quote(str(ROOT))}
source "$ROOT/tools/install/packages.sh"
source "$ROOT/tools/install/repositories.sh"
source "$ROOT/tools/install/docker.sh"
fail() {{ printf '%s\\n' "$*" >&2; exit 1; }}
'''
        return subprocess.run(['/bin/bash', '-c', prefix + script], capture_output=True,
                              text=True, timeout=10)

    def test_priority_distribution_families(self):
        for identifier, like, expected in (
            ('ubuntu', 'debian', 'debian apt-get'),
            ('linuxmint', 'ubuntu debian', 'debian apt-get'),
            ('debian', '', 'debian apt-get'),
            ('arch', '', 'arch pacman'),
            ('endeavouros', 'arch', 'arch pacman'),
            ('fedora', '', 'fedora dnf'),
            ('opensuse-tumbleweed', 'opensuse suse', 'suse zypper'),
        ):
            with self.subTest(identifier=identifier):
                result = self.shell(f'ID={identifier}; ID_LIKE={shlex.quote(like)}; '
                                    'distro_name=fixture; classify_distribution; '
                                    'printf "%s %s" "$family" "$manager"')
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stdout, expected)

    def test_unknown_distribution_is_not_guessed(self):
        result = self.shell('ID=nixos; ID_LIKE=""; distro_name=NixOS; classify_distribution')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('NixOS', result.stderr)

    def test_update_package_for_clean_desktops(self):
        for family, package in [('debian', 'pkexec'), ('arch', 'polkit'),
                                ('fedora', 'polkit-pkexec'), ('suse', 'polkit-1')]:
            with self.subTest(family=family):
                result = self.shell(f'''
family={family}; host_packages=()
native_pkexec_present() {{ return 1; }}
package_installed() {{ return 1; }}
package_available() {{ [[ $1 == {package} ]]; }}
collect_update_package
printf '%s\\n' "${{host_packages[@]}}"
''')
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn(package, result.stdout.splitlines())

    def test_existing_pkexec_is_reused(self):
        result = self.shell('''
family=debian; host_packages=()
native_pkexec_present() { return 0; }
package_available() { fail 'must not query repositories'; }
collect_update_package
printf '%s' "${#host_packages[@]}"
''')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, '0')

    def test_unavailable_pkexec_is_explained(self):
        result = self.shell('''
family=debian; host_packages=()
native_pkexec_present() { return 1; }
package_installed() { return 1; }
package_available() { return 1; }
collect_update_package
''')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('pkexec', result.stderr)

    def test_known_empty_noble_source_is_not_offered(self):
        for identifier, codename in [('ubuntu', 'noble'), ('linuxmint', 'xia')]:
            with self.subTest(identifier=identifier):
                result = self.shell(f'''
family=debian; ID={identifier}; VERSION_CODENAME={codename}; UBUNTU_CODENAME=noble
mode=plan
enable_quickshell_repository
''')
                self.assertNotEqual(result.returncode, 0)
                self.assertIn('24.04', result.stderr)
                self.assertIn('Mint 22', result.stderr)

    def test_reviewed_sources_keep_matching_release(self):
        for identity, expected in [
            ('ID=ubuntu; VERSION_CODENAME=resolute; UBUNTU_CODENAME=', '/ubuntu resolute'),
            ('ID=debian; VERSION_ID=13; UBUNTU_CODENAME=', '/Debian_13 /'),
        ]:
            with self.subTest(identity=identity):
                result = self.shell('family=debian; ' + identity + '; configure_quickshell_repository; '
                                    'printf "%s %s" "$repository_url" "$repository_suite"')
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertTrue(result.stdout.endswith(expected), result.stdout)

    def test_no_guessed_ubuntu_source_for_debian_derivative(self):
        result = self.shell('family=debian; ID=kali; VERSION_ID=2026.4; '
                            'VERSION_CODENAME=kali-rolling; UBUNTU_CODENAME=; '
                            'configure_quickshell_repository')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('No reviewed', result.stderr)

    def test_debian_source_uses_origin_without_mirror_redirect(self):
        result = self.shell('family=debian; ID=debian; VERSION_ID=13; UBUNTU_CODENAME=; '
                            'configure_quickshell_repository; printf "%s" "$repository_url"')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout,
                         'https://downloadcontent.opensuse.org/repositories/home:/AvengeMedia:/danklinux/Debian_13')

    def test_missing_quickshell_guidance_matches_base(self):
        result = self.shell('ID=linuxmint; UBUNTU_CODENAME=noble; VERSION_CODENAME=xia; '
                            'distro_name="Linux Mint 22"; quickshell_install_hint')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('24.04', result.stdout)
        self.assertNotIn('--enable-quickshell-repo', result.stdout)

    def test_authorization_probe_warns_without_blocking_cli(self):
        for available in (True, False):
            with self.subTest(available=available), patch.object(ADMIN.os, 'access', return_value=available) as access:
                output = io.StringIO()
                with redirect_stdout(output):
                    self.assertEqual(ADMIN.probe_update_authorization(), available)
                access.assert_called_once_with('/usr/bin/pkexec', ADMIN.os.X_OK)
                if available:
                    self.assertIn('agent', output.getvalue())
                else:
                    self.assertIn('cyberlab update', output.getvalue())

    def test_missing_optional_xpra_does_not_block_native_install(self):
        result = self.shell('''
family=debian
configure_packages
package_installed() { return 1; }
package_available() { return 1; }
collect_gui_package
printf '\\nPACKAGES:%s\\n' "${host_packages[*]}"
''')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('WARNING', result.stdout)
        self.assertNotIn('xpra', result.stdout.split('PACKAGES:')[1])

    def test_native_xpra_package_is_used_when_available(self):
        for package in ('xpra', 'xpra-client'):
            with self.subTest(package=package):
                result = self.shell(f'''
family=debian; host_packages=()
package_installed() {{ return 1; }}
package_available() {{ [[ $1 == {package} ]]; }}
collect_gui_package
printf '%s\\n' "${{host_packages[@]}}"
''')
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn(package, result.stdout.splitlines())

    def test_repository_prerequisites_refresh_metadata_first(self):
        result = self.shell('''
family=debian; mode=install; refreshed=no
configure_quickshell_repository() {
    repository_format=apt; repository_url=https://example.invalid;
    repository_fingerprint=fixture; repository_destination=/nonexistent/fixture;
}
refresh_native_metadata() { refreshed=yes; }
package_installed() { [[ $refreshed == yes ]] || fail 'stale package metadata'; return 1; }
guarded_package_install() { printf 'REFRESHED:%s' "$refreshed"; exit 0; }
enable_quickshell_repository
''')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('REFRESHED:yes', result.stdout)

    def test_source_plan_never_refreshes_metadata(self):
        result = self.shell('''
family=debian; mode=plan; ID=ubuntu; VERSION_CODENAME=resolute; UBUNTU_CODENAME=
refresh_native_metadata() { fail 'plan must not modify package metadata'; }
enable_quickshell_repository
''')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('plan only', result.stdout)


    def test_debian_split_docker_cli_is_installed_with_engine(self):
        result = self.shell('''
family=debian
docker_unit_state() { printf not-found; }
docker_cli_present() { return 1; }
unmanaged_docker_present() { return 1; }
package_installed() { return 1; }
package_available() { [[ $1 == docker.io || $1 == docker-cli ]]; }
command() { if [[ ${2:-} == docker ]]; then return 1; fi; builtin command "$@"; }
select_docker_packages
printf 'PACKAGES:%s' "${docker_packages[*]}"
''')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('PACKAGES:docker.io docker-cli', result.stdout)

    def test_debian_known_engine_can_complete_missing_split_cli(self):
        result = self.shell('''
family=debian
docker_unit_state() { printf loaded; }
docker_cli_present() { return 1; }
package_installed() { [[ $1 == docker.io ]]; }
package_available() { [[ $1 == docker-cli ]]; }
command() { if [[ ${2:-} == docker ]]; then return 1; fi; builtin command "$@"; }
select_docker_packages
printf 'PACKAGES:%s' "${docker_packages[*]}"
''')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('PACKAGES:docker-cli', result.stdout)

    def test_missing_custom_docker_cli_is_not_replaced(self):
        result = self.shell('''
family=debian
docker_unit_state() { printf loaded; }
docker_cli_present() { return 1; }
package_installed() { return 1; }
package_available() { return 0; }
command() { if [[ ${2:-} == docker ]]; then return 1; fi; builtin command "$@"; }
select_docker_packages
''')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Repair', result.stderr)

    def test_conflicting_docker_providers_are_still_rejected(self):
        for packages, message in [('podman-docker', 'podman-docker'),
                                  ('docker-ce docker.io', 'Mixed Docker')]:
            with self.subTest(packages=packages):
                result = self.shell(f'''
family=debian
docker_unit_state() {{ printf loaded; }}
package_installed() {{ [[ " {packages} " == *" $1 "* ]]; }}
select_docker_packages
''')
                self.assertNotEqual(result.returncode, 0)
                self.assertIn(message, result.stderr)

    def test_existing_repository_is_never_overwritten(self):
        import tempfile
        with tempfile.TemporaryDirectory(prefix='cyberlab-source-check-') as directory:
            root = Path(directory)
            source, destination = root / 'source', root / 'destination'
            source.write_text('new')
            destination.write_text('existing')
            result = self.shell(f'write_repository_file {shlex.quote(str(source))} {shlex.quote(str(destination))}')
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(destination.read_text(), 'existing')

    def test_metadata_refresh_rejects_partial_apt_failure(self):
        result = self.shell('''
family=debian
apt-get() { [[ "$*" == 'update --error-on=any' ]] || exit 99; return 100; }
refresh_native_metadata
printf 'must not continue'
''')
        self.assertEqual(result.returncode, 100)
        self.assertNotIn('must not continue', result.stdout)


if __name__ == '__main__':
    unittest.main(verbosity=2)
