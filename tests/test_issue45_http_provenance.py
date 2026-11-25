import contextlib
import hashlib
import importlib.util
import io
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
DIAGNOSTICS = ROOT / "diagnostics/issue45-runtime"


def load(name):
    spec = importlib.util.spec_from_file_location(name, DIAGNOSTICS / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


http = load("verify_http_artifacts")
with patch.dict(sys.modules, {"verify_http_artifacts": http}):
    official = load("verify_official_http_artifacts")


class HttpProvenanceTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.directory = self.root / "diagnostics/issue45-runtime"
        self.directory.mkdir(parents=True)
        self.paths = [self.directory / Path(module.__file__).name for module in (official, http)]
        for path, module in zip(self.paths, (official, http)):
            path.write_bytes(Path(module.__file__).read_bytes())
        self.git("init", "-q")
        self.git("config", "core.autocrlf", "false")
        self.git("config", "user.name", "Fixture")
        self.git("config", "user.email", "fixture@example.invalid")
        self.git("config", "commit.gpgsign", "false")
        self.git("add", "diagnostics")
        self.git("-c", "core.hooksPath=" + str(self.root / "no-hooks"), "commit", "-qm", "fixture")
        self.checkout = self.git("rev-parse", "HEAD").strip()
        for module, path in zip((official, http), self.paths):
            self.enterContext(patch.object(module, "__file__", str(path)))
        self.enterContext(patch.object(http, "ROOT", self.root))
        self.output = self.root / "report.json"

    def git(self, *args):
        return subprocess.check_output(["git", *args], cwd=self.root, stderr=subprocess.DEVNULL, text=True)

    def test_actual_git_source_bytes_and_unrelated_changes(self):
        expected = {p.relative_to(self.root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                    for p in self.paths}
        (self.root / "unrelated.txt").write_text("local notes", encoding="utf-8")
        self.assertEqual(official.source_identity(), (self.checkout, expected))
        for path in self.paths:
            original = path.read_bytes()
            for state in ("unstaged", "staged", "assume-unchanged"):
                with self.subTest(path=path.name, state=state):
                    path.write_bytes(original + b"\n# local edit\n")
                    relative = path.relative_to(self.root).as_posix()
                    if state == "staged":
                        self.git("add", relative)
                    if state == "assume-unchanged":
                        self.git("update-index", "--assume-unchanged", relative)
                    try:
                        with self.assertRaisesRegex(http.VerificationError, "verifier source differs from HEAD"):
                            official.source_identity()
                    finally:
                        if state == "assume-unchanged":
                            self.git("update-index", "--no-assume-unchanged", relative)
                        path.write_bytes(original)
                        self.git("add", relative)
        self.assertEqual(official.source_identity(), (self.checkout, expected))

    def run_main(self, *, success):
        stdout, stderr = io.StringIO(), io.StringIO()
        with patch.object(sys, "argv", ["verify", "--output", str(self.output)]), \
                contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            if success:
                self.assertEqual(official.main(), 0)
            else:
                with self.assertRaises(SystemExit) as exit_code:
                    official.main()
                self.assertEqual(exit_code.exception.code, 1)
                self.assertEqual(stdout.getvalue(), "")
                self.assertFalse(self.output.exists())
        return stdout.getvalue(), stderr.getvalue()

    def test_dirty_input_fails_before_acquisition(self):
        self.paths[1].write_bytes(self.paths[1].read_bytes() + b"\n# edit\n")
        with patch.object(official, "prepare") as prepare, patch.object(official, "run_verifier") as verifier:
            _, error = self.run_main(success=False)
        self.assertIn("verifier source differs from HEAD", error)
        prepare.assert_not_called()
        verifier.assert_not_called()

    def test_source_drift_during_acquisition_fails_before_cli(self):
        def prepare(*args):
            self.paths[0].write_bytes(self.paths[0].read_bytes() + b"\n# edit\n")
        with patch.object(official, "prepare", side_effect=prepare), patch.object(official, "run_verifier") as verifier:
            _, error = self.run_main(success=False)
        self.assertIn("verifier source differs from HEAD", error)
        verifier.assert_not_called()

    def fake_verifier(self, libraries, output):
        report = {"occurrences": [1, 2, 3, 4], "artifacts": {
            name: {"observed_sha256": "a" * 64, "spdy_class_sha256": {}}
            for name in ("one", "two", "three")}, "runtime_reachability": "not_established",
            "release_blocking": True, "risk_accepted": False, "scope": "static_artifact_identity_and_class_inventory_only"}
        output.write_text(json.dumps(report), encoding="utf-8")

    def test_head_drift_after_cli_rejects_report(self):
        def verifier(libraries, output):
            self.fake_verifier(libraries, output)
            self.git("-c", "core.hooksPath=" + str(self.root / "no-hooks"), "commit", "--allow-empty", "-qm", "advance")
        with patch.object(official, "prepare"), patch.object(official, "run_verifier", side_effect=verifier):
            _, error = self.run_main(success=False)
        self.assertIn("verifier checkout changed", error)

    def test_clean_run_logs_script_and_report_hashes(self):
        identity = official.source_identity()
        with patch.object(official, "prepare"), patch.object(official, "run_verifier", side_effect=self.fake_verifier):
            stdout, _ = self.run_main(success=True)
        record = json.loads(stdout)
        self.assertEqual(record["checkout"], identity[0])
        self.assertEqual(record["source_sha256"], identity[1])
        self.assertEqual(record["report_sha256"], hashlib.sha256(self.output.read_bytes()).hexdigest())
        self.assertNotIn(str(self.root), stdout)
        self.assertEqual(record["result"], "pass")


if __name__ == "__main__":
    unittest.main()
