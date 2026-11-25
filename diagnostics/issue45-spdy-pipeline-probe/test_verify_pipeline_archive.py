import hashlib
import json
from pathlib import Path
import shutil
import tempfile
import unittest

import verify_pipeline_archive as archive


class PipelineArchiveTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name)
        for name in ("provenance.json", archive.ZIP_NAME):
            shutil.copyfile(archive.ARCHIVE / name, self.directory / name)

    def mutate_zip(self):
        path = self.directory / archive.ZIP_NAME
        raw = bytearray(path.read_bytes())
        raw[len(raw) // 2] ^= 1
        path.write_bytes(raw)
        return raw

    def test_original_archive(self):
        report = archive.verify(self.directory)
        self.assertEqual(report["checkout"], archive.CHECKOUT)
        self.assertTrue(report["synthetic_pipeline_observed"])
        self.assertFalse(report["minecraft_pipeline_observed"])
        self.assertTrue(report["release_blocking"])

    def test_changed_zip(self):
        self.mutate_zip()
        with self.assertRaisesRegex(ValueError, "pipeline archive digest mismatch"):
            archive.verify(self.directory)

    def test_changed_provenance(self):
        path = self.directory / "provenance.json"
        p = json.loads(path.read_bytes())
        p["checkout"] = "0" * 40
        path.write_text(json.dumps(p), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "pipeline provenance blob mismatch"):
            archive.verify(self.directory)

    def test_coordinated_change(self):
        raw = self.mutate_zip()
        path = self.directory / "provenance.json"
        p = json.loads(path.read_bytes())
        p["archive"]["sha256"] = hashlib.sha256(raw).hexdigest()
        p["archive"]["git_blob"] = archive.historical.git_blob(raw)
        path.write_text(json.dumps(p), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "pipeline provenance blob mismatch"):
            archive.verify(self.directory)

    def test_missing_archive(self):
        (self.directory / archive.ZIP_NAME).unlink()
        with self.assertRaises(FileNotFoundError):
            archive.verify(self.directory)


if __name__ == "__main__":
    unittest.main()
