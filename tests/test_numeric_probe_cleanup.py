"""The numeric map probe must reap the client on errors."""
import importlib.util
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import Mock, call

ROOT = Path(__file__).resolve().parents[1]
path = ROOT / 'docs/verification/numeric-mapid-1.0.0/process_cleanup.py'
spec = importlib.util.spec_from_file_location('numeric_probe_cleanup', path)
cleanup = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cleanup)


class NumericProbeCleanupTests(unittest.TestCase):
    def test_error_terminates_and_reaps_a_real_child(self):
        child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(120)'])
        try:
            with self.assertRaisesRegex(RuntimeError, 'probe failed'):
                with cleanup.managed_client(child, timeout=10):
                    raise RuntimeError('probe failed')
            self.assertIsNotNone(child.poll())
        finally:
            if child.poll() is None:
                child.kill()
                child.wait(timeout=10)

    def test_terminate_timeout_kills_and_reaps(self):
        child = Mock()
        child.poll.return_value = None
        child.wait.side_effect = [subprocess.TimeoutExpired('client', 1), 0]
        with cleanup.managed_client(child, timeout=1):
            pass
        child.terminate.assert_called_once_with()
        child.kill.assert_called_once_with()
        self.assertEqual(child.wait.call_args_list, [call(timeout=1), call()])

    def test_exited_child_is_not_terminated_again(self):
        child = Mock()
        child.poll.return_value = 0
        with cleanup.managed_client(child):
            pass
        child.terminate.assert_not_called()
        child.kill.assert_not_called()


if __name__ == '__main__':
    unittest.main()
