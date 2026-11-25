import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LAUNCHER = ROOT / "scripts/run_pinned_python.py"


class PinnedPythonTests(unittest.TestCase):
    def run_launcher(self, executable, version, *args):
        return subprocess.run([sys.executable, str(LAUNCHER), executable, version, *args],
                              capture_output=True, text=True, check=False)

    def test_actual_child_receives_arguments_and_propagates_exit(self):
        version = sys.version.split()[0]
        result = self.run_launcher(sys.executable, version, "-c",
                                   "import sys; print(ascii(sys.argv[1])); sys.exit(17)", "space café")
        self.assertEqual(result.returncode, 17)
        self.assertEqual(result.stdout.strip(), ascii("space café"))
        self.assertEqual(result.stderr, "")

    def test_distinct_interpreter_handoff(self):
        if "ISSUE45_PINNED_TEST_TARGET" not in os.environ:
            self.skipTest("hosted two-interpreter test target not configured")
        target = os.environ["ISSUE45_PINNED_TEST_TARGET"]
        self.assertEqual(sys.version.split()[0], "3.10.22")
        self.assertNotEqual(Path(sys.executable).resolve(), Path(target).resolve())
        result = self.run_launcher(target, "3.15.2", "-c",
                                   "import sys; print(sys.version.split()[0]); print(ascii(sys.argv[1])); sys.exit(23)",
                                   "space café")
        self.assertEqual(result.returncode, 23)
        self.assertEqual(result.stdout.splitlines(), ["3.15.2", ascii("space café")])
        self.assertEqual(result.stderr, "")

    def test_wrong_version_does_not_execute_payload(self):
        result = self.run_launcher(sys.executable, "0.0.0", "-c", "print('must not execute')")
        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stdout, "")
        self.assertIn("interpreter version mismatch", result.stderr)

    def test_missing_or_relative_executable_rejected_without_path_leak(self):
        with tempfile.TemporaryDirectory() as temporary:
            for executable in ("python", str(Path(temporary).resolve() / "missing python")):
                with self.subTest(executable=executable):
                    result = self.run_launcher(executable, sys.version.split()[0], "-c", "print('unexpected')")
                    self.assertEqual(result.returncode, 2)
                    self.assertEqual(result.stdout, "")
                    self.assertNotIn(temporary, result.stderr)
                    self.assertIn("absolute setup-python executable required", result.stderr)


if __name__ == "__main__":
    unittest.main()
