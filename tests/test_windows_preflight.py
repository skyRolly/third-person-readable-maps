"""The Windows entry point must never run Gradle after a failed preflight."""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(os.name == 'nt', 'requires Windows cmd.exe')
class WindowsPreflightTests(unittest.TestCase):
    def test_only_zero_exit_starts_gradle(self):
        for code in (0, 1, -1073741819):  # Last value has the bits of a Windows access violation.
            with self.subTest(preflight_exit=code), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                shutil.copy2(ROOT / 'Build-Windows.bat', root)
                (root / 'scripts').mkdir()
                (root / 'scripts' / 'verify_gradle_wrapper.py').write_text(
                    'import os\nos._exit(int(os.environ["TPRM_PREFLIGHT_TEST_EXIT"]))\n', encoding='utf-8')
                (root / 'gradlew.bat').write_bytes(
                    b'@echo off\r\necho ran > "%~dp0gradle-called.txt"\r\nexit /b 0\r\n')
                env = dict(os.environ, TPRM_PREFLIGHT_TEST_EXIT=str(code))
                env['PATH'] = str(Path(sys.executable).parent) + os.pathsep + env.get('PATH', '')
                result = subprocess.run(['cmd.exe', '/d', '/c', 'call', 'Build-Windows.bat'],
                                        cwd=root, env=env, capture_output=True, text=True, timeout=30)
                self.assertEqual((root / 'gradle-called.txt').exists(), code == 0, result.stdout + result.stderr)
                self.assertEqual(result.returncode == 0, code == 0, result.stdout + result.stderr)


if __name__ == '__main__':
    unittest.main()
