import hashlib
import json
from pathlib import Path
import shutil
import tempfile
import unittest

import verify_archive as archive


class ArchiveTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name)
        for name in ("provenance.json", archive.ZIP_NAME):
            shutil.copyfile(archive.ARCHIVE / name, self.directory / name)

    def test_original_archive(self):
        report = archive.verify(self.directory)
        self.assertEqual(report["checkout"], archive.CHECKOUT)
        self.assertFalse(report["pipeline_observed"])
        self.assertTrue(report["release_blocking"])

    def test_changed_zip(self):
        path = self.directory / archive.ZIP_NAME
        raw = bytearray(path.read_bytes())
        raw[len(raw) // 2] ^= 1
        path.write_bytes(raw)
        with self.assertRaisesRegex(ValueError, "archive digest mismatch"):
            archive.verify(self.directory)

    def test_changed_provenance(self):
        path = self.directory / "provenance.json"
        p = json.loads(path.read_bytes())
        p["checkout"] = "0" * 40
        path.write_text(json.dumps(p), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "historical provenance blob mismatch"):
            archive.verify(self.directory)

    def test_coordinated_zip_and_provenance_change(self):
        path = self.directory / archive.ZIP_NAME
        raw = bytearray(path.read_bytes())
        raw[len(raw) // 2] ^= 1
        path.write_bytes(raw)
        provenance = self.directory / "provenance.json"
        p = json.loads(provenance.read_bytes())
        p["archive"]["sha256"] = hashlib.sha256(raw).hexdigest()
        p["archive"]["git_blob"] = archive.git_blob(raw)
        provenance.write_text(json.dumps(p), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "historical provenance blob mismatch"):
            archive.verify(self.directory)

    def test_missing_archive(self):
        (self.directory / archive.ZIP_NAME).unlink()
        with self.assertRaises(FileNotFoundError):
            archive.verify(self.directory)


if __name__ == "__main__":
    unittest.main()
