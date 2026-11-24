"""Isolated updater readiness checks; never invokes services or Docker."""

import subprocess
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import upgrade_runtime as updater


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


if __name__ == '__main__':
    unittest.main(verbosity=2)
