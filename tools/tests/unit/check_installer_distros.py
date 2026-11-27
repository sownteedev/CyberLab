#!/usr/bin/env python3
"""Installer fixtures only: never run a host package manager or change services."""

from pathlib import Path
from contextlib import redirect_stdout
import importlib.util
import io
import gzip
import os
import pty
import shlex
import stat
import subprocess
from types import SimpleNamespace
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
            ('kali', 'debian', 'debian apt-get'),
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

    def dependency_confirmation(self, *, distro='ubuntu', answer=None,
                                approve='no', assume_yes='no', mode='install',
                                action='upgrade', version='2'):
        script = f'''
source {shlex.quote(str(ROOT / 'tools/install/transactions.sh'))}
fail() {{ printf '%s\\n' "$*" >&2; exit 1; }}
family=debian; ID={distro}; mode={mode}
allow_dependency_upgrades={approve}; assume_yes={assume_yes}
package_installed() {{ [[ {action} != install ]]; }}
package_version() {{ printf '1'; }}
dpkg() {{
    case "$3" in
        lt) (( $2 < $4 )) ;;
        eq) (( $2 == $4 )) ;;
        *) exit 99 ;;
    esac
}}
review_package_transaction <(printf '{action}\\txserver-common\\t{version}\\n')
if [[ $mode == plan ]]; then exit 0; fi
confirm_package_transaction
printf 'APPROVED: %s\\n' "${{approved_packages[*]}}"
'''
        if answer is None:
            return subprocess.run(['/bin/bash', '-eu', '-c', script],
                                  stdin=subprocess.DEVNULL, capture_output=True,
                                  text=True, timeout=5, start_new_session=True)
        master, slave = pty.openpty()
        try:
            with subprocess.Popen(['/bin/bash', '-eu', '-c', script], stdin=slave,
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                  text=True) as process:
                os.write(master, answer)
                output, error = process.communicate(timeout=5)
                return subprocess.CompletedProcess(process.args, process.returncode,
                                                   output, error)
        finally:
            os.close(slave)
            os.close(master)

    def test_dependency_upgrades_can_be_approved_at_terminal_without_flag(self):
        for distro in ('ubuntu', 'kali'):
            with self.subTest(distro=distro):
                result = self.dependency_confirmation(distro=distro, answer=b'y\n')
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn('APPROVED: xserver-common=2', result.stdout)
                self.assertIn('[y/N]', result.stdout)

    def test_dependency_upgrade_refusal_empty_and_eof_never_approve(self):
        for answer in (b'n\n', b'\n', b'\x04'):
            with self.subTest(answer=answer):
                result = self.dependency_confirmation(answer=answer)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn('[y/N]', result.stdout)
                self.assertNotIn('APPROVED:', result.stdout)

    def test_unattended_upgrades_require_both_explicit_flags(self):
        for approve, assume_yes, expected in (
            ('no', 'no', 1), ('no', 'yes', 1), ('yes', 'no', 1), ('yes', 'yes', 0),
        ):
            with self.subTest(approve=approve, assume_yes=assume_yes):
                result = self.dependency_confirmation(approve=approve, assume_yes=assume_yes)
                self.assertEqual(result.returncode, expected, result.stdout + result.stderr)
                self.assertEqual('APPROVED:' in result.stdout, expected == 0)

    def test_dependency_plan_does_not_prompt_or_approve(self):
        result = self.dependency_confirmation(mode='plan')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('REQUIRES APPROVAL', result.stdout)
        self.assertNotIn('[y/N]', result.stdout)
        self.assertNotIn('APPROVED:', result.stdout)

    def test_package_removal_or_downgrade_cannot_be_confirmed(self):
        for action, version in (('remove', '2'), ('upgrade', '0')):
            with self.subTest(action=action):
                result = self.dependency_confirmation(action=action, version=version,
                                                      approve='yes', assume_yes='yes')
                self.assertNotEqual(result.returncode, 0)
                self.assertNotIn('APPROVED:', result.stdout)

    def test_new_dependencies_still_require_confirmation_without_yes(self):
        result = self.dependency_confirmation(action='install', answer=b'y\n')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('[y/N]', result.stdout)
        self.assertIn('APPROVED: xserver-common=2', result.stdout)

    def test_old_python_is_added_to_review_before_upgrade_consent(self):
        result = self.shell('''
family=debian; mode=install; allow_dependency_upgrades=no; forced_packages=()
select_python() { return 1; }
python3() { return 0; }
apt-cache() { printf 'Candidate: 3.12.3\n'; }
dpkg() { [[ $* == '--compare-versions 3.12.3 ge 3.12' ]]; }
check_python_candidate
printf 'REVIEW: %s\n' "${forced_packages[*]}"
printf 'CONSENT: %s\n' "$allow_dependency_upgrades"
''')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('REVIEW: python3', result.stdout)
        self.assertIn('CONSENT: no', result.stdout)

    def test_guarded_upgrade_rechecks_plan_and_scopes_terminal_consent(self):
        import tempfile
        for changed_plan in (False, True):
            with self.subTest(changed_plan=changed_plan), tempfile.TemporaryDirectory() as directory:
                script = f'''
source {shlex.quote(str(ROOT / 'tools/install/transactions.sh'))}
fail() {{ printf '%s\\n' "$*" >&2; exit 1; }}
family=debian; mode=install; allow_dependency_upgrades=no; assume_yes=no
mktemp() {{ printf '%s' {shlex.quote(directory)}; }}
package_inventory() {{ printf 'fixture 1\\n'; }}
package_installed() {{ return 0; }}
package_version() {{ printf '1'; }}
dpkg() {{ return 1; }}
resolve_package_transaction() {{
    local version=2
    if [[ $1 == */rechecked.txt && {str(changed_plan)} == True ]]; then version=3; fi
    printf 'upgrade\\tfixture\\t%s\\n' "$version" > "$1"
}}
transaction_records() {{ cat "$1"; }}
apply_package_transaction() {{
    [[ $allow_dependency_upgrades == yes ]] || fail 'missing upgrade consent'
    printf 'APPLIED: %s\\n' "${{approved_packages[*]}}"
}}
guarded_package_install
printf 'OUTSIDE CONSENT: %s\\n' "$allow_dependency_upgrades"
'''
                master, slave = pty.openpty()
                try:
                    with subprocess.Popen(['/bin/bash', '-eu', '-c', script], stdin=slave,
                                          stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                          text=True) as process:
                        os.write(master, b'y\n')
                        output, error = process.communicate(timeout=5)
                        self.assertEqual(process.returncode, 1 if changed_plan else 0, output + error)
                        if changed_plan:
                            self.assertNotIn('APPLIED:', output)
                            self.assertIn('Dependency resolution changed', error)
                        else:
                            self.assertIn('APPLIED: fixture=2', output)
                            self.assertIn('OUTSIDE CONSENT: no', output)
                finally:
                    os.close(slave)
                    os.close(master)

    def test_incompatible_distro_quickshell_reaches_review_without_upgrade_flag(self):
        result = self.shell('''
family=debian; mode=install; allow_dependency_upgrades=no; gui_runtime=native
distro_name=fixture; desktop_user=fixture
configure_packages() { host_packages=(); }
check_python_candidate() { :; }
collect_terminal_package() { :; }
collect_update_package() { :; }
collect_gui_package() { :; }
native_quickshell_present() { return 0; }
package_available() { return 1; }
package_installed() { [[ $1 == quickshell ]]; }
python3() { [[ $* != *native-version* ]]; }
select_docker_packages() { docker_packages=(); }
collect_native_packages
printf 'REVIEW: %s\n' "${missing_packages[*]}"
printf 'CONSENT: %s\n' "$allow_dependency_upgrades"
''')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('REVIEW: quickshell', result.stdout)
        self.assertIn('CONSENT: no', result.stdout)

    def test_kali_abi_transition_is_explained_without_applying(self):
        import tempfile
        with tempfile.TemporaryDirectory() as directory:
            result = self.shell(f'''
source "$ROOT/tools/install/transactions.sh"
family=debian; ID=kali; mode=install; allow_dependency_upgrades=yes
missing_packages=(quickshell xpra)
apt-get() {{
    [[ $1 == --simulate ]] || fail 'must never apply packages'
    printf '%s\\n' 'Remv libpyside6-py3-6.10 [6.10.2]' 'Remv libshiboken6-py3-6.10 [6.10.2]' 'Inst libpyside6-py3-6.11 (6.11.0 kali-rolling [amd64])'
    return 100
}}
resolve_package_transaction {shlex.quote(directory + '/plan.txt')}
''')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('libpyside6-py3-6.10', result.stderr)
        self.assertIn('apt-get -s full-upgrade', result.stderr)
        self.assertIn('--allow-dependency-upgrades', result.stderr)

    def test_apt_simulation_removal_records_are_rejected_even_on_success(self):
        import tempfile
        with tempfile.TemporaryDirectory() as directory:
            result = self.shell(f'''
source "$ROOT/tools/install/transactions.sh"
family=debian; ID=kali; missing_packages=(quickshell)
apt-get() {{ printf '%s\\n' 'Remv important-desktop [1.0]'; }}
resolve_package_transaction {shlex.quote(directory + '/plan.txt')}
''')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('important-desktop', result.stderr)

    def test_suse_transaction_reads_saved_resolver_output(self):
        import tempfile
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'plan.xml'
            output.write_text('<install-summary><to-install><solvable name="quickshell" edition="0.3.2"/></to-install></install-summary>')
            result = self.shell(f'''
source "$ROOT/tools/install/transactions.sh"
family=suse
transaction_records {shlex.quote(str(output))} < /dev/null
''')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), 'install\tquickshell\t0.3.2')

    def test_apt_success_does_not_retry_without_removal_guard(self):
        import tempfile
        with tempfile.TemporaryDirectory() as directory:
            result = self.shell(f'''
source "$ROOT/tools/install/transactions.sh"
family=debian; ID=ubuntu; missing_packages=(quickshell)
apt-get() {{
    [[ " $* " == *' --simulate '* && " $* " == *' --no-remove '* ]] || fail 'unsafe resolver call'
    printf '%s\\n' 'Inst quickshell (0.3.2 Ubuntu [amd64])'
}}
resolve_package_transaction {shlex.quote(directory + '/plan.txt')}
transaction_records {shlex.quote(directory + '/plan.txt')}
''')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), 'install\tquickshell\t0.3.2')

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
verify_quickshell_repository() {{ fail 'Ubuntu 24.04 / Linux Mint 22: no quickshell package'; }}
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
verify_quickshell_repository() { :; }
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
verify_quickshell_repository() { :; }
refresh_native_metadata() { fail 'plan must not modify package metadata'; }
enable_quickshell_repository
''')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('plan only', result.stdout)

    def test_empty_repository_is_rejected_before_any_package_change(self):
        result = self.shell('''
family=debian; mode=install; ID=ubuntu; VERSION_CODENAME=resolute; UBUNTU_CODENAME=
verify_quickshell_repository() { fail 'no compatible package in source'; }
refresh_native_metadata() { fail 'unexpected metadata write'; }
guarded_package_install() { fail 'unexpected package change'; }
enable_quickshell_repository
''')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('no compatible package in source', result.stderr)
        self.assertNotIn('unexpected', result.stderr)

    def test_native_or_enabled_repository_does_not_prompt_for_external_source(self):
        for installed, available in [(True, False), (False, True)]:
            with self.subTest(installed=installed):
                result = self.shell(f'''
family=debian; mode=install; enable_quickshell_repo=no
native_quickshell_present() {{ return {0 if installed else 1}; }}
package_available() {{ return {0 if available else 1}; }}
configure_quickshell_repository() {{ fail 'unexpected external source'; }}
ensure_quickshell_source
''')
                self.assertEqual(result.returncode, 0, result.stderr)

    def test_source_consent_is_not_implied_by_yes(self):
        result = self.shell('''
family=debian; mode=install; enable_quickshell_repo=no; assume_yes=yes
native_quickshell_present() { return 1; }
package_available() { return 1; }
configure_quickshell_repository() { repository_format=apt; repository_url=https://example.invalid; repository_fingerprint=fixture; }
verify_quickshell_repository() { :; }
confirm_quickshell_repository() { fail 'repository consent required'; }
enable_quickshell_repository() { fail 'unexpected source change'; }
ensure_quickshell_source
''')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('repository consent required', result.stderr)

    def test_real_source_prompt_requires_terminal_even_with_yes(self):
        result = self.shell('''
assume_yes=yes; repository_url=https://example.invalid; repository_fingerprint=fixture
confirm_quickshell_repository
''')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('--yes', result.stderr)

    def test_real_source_prompt_accepts_and_rejects_terminal_input(self):
        script = f'''
source {shlex.quote(str(ROOT / 'tools/install/repositories.sh'))}
fail() {{ printf '%s' "$*" >&2; exit 1; }}
repository_url=https://example.invalid; repository_fingerprint=fixture
confirm_quickshell_repository
'''
        for answer, expected in [(b'y\n', 0), (b'n\n', 1)]:
            with self.subTest(answer=answer):
                master, slave = pty.openpty()
                try:
                    with subprocess.Popen(['/bin/bash', '-eu', '-c', script], stdin=slave,
                                          stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True) as process:
                        os.write(master, answer)
                        output, error = process.communicate(timeout=5)
                        self.assertEqual(process.returncode, expected, output + error)
                finally:
                    os.close(slave)
                    os.close(master)

    def test_approved_source_is_rechecked_after_refresh(self):
        result = self.shell('''
family=debian; mode=install; enable_quickshell_repo=yes; refreshed=no
native_quickshell_present() { return 1; }
package_available() { [[ $refreshed == yes ]]; }
enable_quickshell_repository() { printf 'APPROVED\n'; }
refresh_native_metadata() { refreshed=yes; }
ensure_quickshell_source
printf 'READY'
''')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('APPROVED', result.stdout)
        self.assertIn('READY', result.stdout)

    def test_read_only_modes_do_not_enable_sources(self):
        for mode in ('plan', 'check', 'update'):
            with self.subTest(mode=mode):
                result = self.shell(f'''
mode={mode}; enable_quickshell_repo=yes
enable_quickshell_repository() {{ fail 'source mutation'; }}
ensure_quickshell_source
''')
                self.assertEqual(result.returncode, 0, result.stderr)

    def test_noble_preflight_selects_private_without_repository_changes(self):
        result = self.shell('''
mode=install; dependencies=yes; family=debian; ID=ubuntu; VERSION_CODENAME=noble; UBUNTU_CODENAME=
native_quickshell_present() { return 1; }
package_available() { return 1; }
verify_quickshell_repository() { fail 'noble has no compatible package'; }
refresh_native_metadata() { fail 'unexpected metadata change'; }
preflight_native_install
''')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('riêng', result.stdout)
        system = (ROOT / 'tools/install/system.sh').read_text()
        self.assertLess(system.index('\npreflight_native_install\n'), system.index('exec sudo'))

    def test_prepared_noble_runtime_is_not_rejected_by_codename(self):
        result = self.shell('''
mode=install; dependencies=yes; ID=linuxmint; UBUNTU_CODENAME=noble
native_quickshell_present() { return 0; }
configure_quickshell_repository() { fail 'unexpected source requirement'; }
preflight_native_install
''')
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_manual_upstream_install_is_recognized_without_path_wrappers(self):
        spec = importlib.util.spec_from_file_location('source_launcher', ROOT / 'ui/launcher.py')
        launcher = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(launcher)
        candidate = Path('/usr/local/bin/quickshell')
        safe = SimpleNamespace(st_uid=0, st_mode=stat.S_IFREG | 0o755)
        with patch.object(Path, 'is_file', lambda path: path == candidate), \
             patch.object(launcher.os, 'access', return_value=True), \
             patch.object(Path, 'resolve', lambda path, **options: path), \
             patch.object(Path, 'stat', return_value=safe), \
             patch.object(Path, 'open', side_effect=lambda *args, **kwargs: io.BytesIO(b'\x7fELF' + b'\0' * 8)):
            self.assertEqual(launcher.native_quickshell(), candidate)
            with patch.object(Path, 'stat', return_value=SimpleNamespace(st_uid=1000, st_mode=stat.S_IFREG | 0o755)):
                self.assertIsNone(launcher.native_quickshell())
            with patch.object(Path, 'stat', return_value=SimpleNamespace(st_uid=0, st_mode=stat.S_IFREG | 0o777)):
                self.assertIsNone(launcher.native_quickshell())
        packages = (ROOT / 'tools/install/packages.sh').read_text()
        for executable in launcher.NATIVE_QUICKSHELL:
            self.assertIn(str(executable), packages)


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


class QuickshellSourceChecks(unittest.TestCase):
    def setUp(self):
        spec = importlib.util.spec_from_file_location('quickshell_source', ROOT / 'tools/install/quickshell_source.py')
        self.source = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.source)

    def package(self, version='0.3.2ppa1', architecture='amd64', name='quickshell'):
        return f'Package: {name}\nVersion: {version}\nArchitecture: {architecture}\n\n'

    def test_exact_package_architecture_and_runtime_version(self):
        source = self.package(name='quickshell-doc') + self.package(architecture='arm64') + self.package('0.2.1')
        with self.assertRaises(ValueError):
            self.source.select_package(source, 'amd64')
        self.assertEqual(self.source.select_package(source + self.package(), 'amd64'), '0.3.2ppa1')

    def test_old_or_malformed_version_is_rejected(self):
        for version in ('0.3.0', '0.3.1~rc1', 'unknown', '1:0.1.0'):
            with self.subTest(version=version), self.assertRaises(ValueError):
                self.source.select_package(self.package(version), 'amd64')

    def test_empty_or_wrong_architecture_source_is_rejected(self):
        for text in ('', self.package(architecture='arm64')):
            with self.assertRaises(ValueError):
                self.source.select_package(text, 'amd64')

    def test_duplicate_fields_are_rejected(self):
        with self.assertRaises(ValueError):
            self.source.select_package(self.package().replace('Version:', 'Package: other\nVersion:'), 'amd64')

    def test_expansion_and_download_are_bounded(self):
        for data, compressed, expanded in [(b'a' * 101, 100, 1000), (gzip.compress(b'a' * 101), 1000, 100)]:
            with self.subTest(compressed=compressed):
                with patch.object(self.source, 'MAX_COMPRESSED', compressed), patch.object(self.source, 'MAX_EXPANDED', expanded):
                    with self.assertRaises(ValueError):
                        self.source.decode_index(data)
        data = self.package().encode()
        self.assertEqual(self.source.decode_index(gzip.compress(data)), data.decode())

    def test_source_url_stays_with_matching_suite_and_architecture(self):
        base = 'https://ppa.launchpadcontent.net/avengemedia/danklinux/ubuntu'
        self.assertEqual(self.source.index_url(base, 'noble', 'amd64'), base + '/dists/noble/main/binary-amd64/Packages.gz')
        for suite, architecture in [('../resolute', 'amd64'), ('noble', '../arm64')]:
            with self.assertRaises(ValueError):
                self.source.index_url(base, suite, architecture)
        with self.assertRaises(ValueError):
            self.source.index_url('https://unreviewed.invalid', 'noble', 'amd64')

    def test_https_redirect_cannot_downgrade_transport(self):
        import urllib.request
        handler = self.source.HttpsRedirect()
        with self.assertRaises(ValueError):
            handler.redirect_request(urllib.request.Request('https://example.invalid'), None, 302, '', {}, 'http://example.invalid')

if __name__ == '__main__':
    unittest.main(verbosity=2)
