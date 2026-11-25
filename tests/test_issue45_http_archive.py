import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ARCHIVE_DIR = ROOT / "docs/dependency-evidence/issue45-official-http-observation-2026-11-25"


class HttpArchiveTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name) / "archive"
        shutil.copytree(ARCHIVE_DIR, self.directory)
        readme = (self.directory / "README.md").read_text(encoding="utf-8")
        self.code = readme.split("```python\n", 1)[1].split("\n```", 1)[0]
        self.provenance_path = self.directory / "provenance.json"
        self.provenance = json.loads(self.provenance_path.read_bytes())
        self.identity = self.provenance["archive"]
        self.archive = self.directory / self.identity["path"]

    def verify(self, optimized):
        flags = ["-O"] if optimized else []
        return subprocess.run([sys.executable, *flags, "-c", self.code], cwd=self.directory,
                              capture_output=True, text=True, check=False)

    def test_original_archive_passes_with_or_without_optimization(self):
        for optimized in (False, True):
            with self.subTest(optimized=optimized):
                result = self.verify(optimized)
                self.assertEqual(result.returncode, 0, result.stderr)

    def test_modified_report_fails_archive_json_and_scope_checks(self):
        with zipfile.ZipFile(self.archive) as z:
            report = json.loads(z.read(self.identity["json_member"]))
        report["risk_accepted"] = True
        raw = json.dumps(report).encode("utf-8")
        with zipfile.ZipFile(self.archive, "w", compression=zipfile.ZIP_DEFLATED) as z:
            z.writestr(self.identity["json_member"], raw)
        with zipfile.ZipFile(self.archive) as z:
            self.assertIsNone(z.testzip())
        archive_bytes = self.archive.read_bytes()
        self.identity["size_bytes"] = len(archive_bytes)
        for mode in ("archive", "JSON", "scope"):
            if mode == "JSON":
                self.identity["sha256"] = hashlib.sha256(archive_bytes).hexdigest()
                self.identity["json_size_bytes"] = len(raw)
            elif mode == "scope":
                self.identity["json_sha256"] = hashlib.sha256(raw).hexdigest()
            self.provenance_path.write_text(json.dumps(self.provenance), encoding="utf-8")
            expected = {"archive": "archive SHA-256 mismatch", "JSON": "JSON SHA-256 mismatch",
                        "scope": "report risk_accepted mismatch"}[mode]
            for optimized in (False, True):
                with self.subTest(mode=mode, optimized=optimized):
                    result = self.verify(optimized)
                    self.assertEqual(result.returncode, 1)
                    self.assertIn(expected, result.stderr)


if __name__ == "__main__":
    unittest.main()
