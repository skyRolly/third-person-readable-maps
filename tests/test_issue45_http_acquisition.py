import hashlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
DIAGNOSTICS = ROOT / "diagnostics/issue45-runtime"

def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

http = load("verify_http_artifacts", DIAGNOSTICS / "verify_http_artifacts.py")
official = load("verify_official_http_artifacts", DIAGNOSTICS / "verify_official_http_artifacts.py")


class HttpAcquisitionTests(unittest.TestCase):
    def test_prepare_reconciles_all_manifests_before_acquisition(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            manifests = root / "manifests"
            manifests.mkdir()
            libraries = root / "libraries"
            libraries.mkdir()
            pins, raws = {}, {}
            for _, _, version, games in http.GROUPS:
                raw = version.encode()
                raws[version] = raw
                relative = f"io/netty/netty-codec-http/{version}/netty-codec-http-{version}.jar"
                for game in games:
                    manifest = {"id": game, "libraries": [{
                        "name": "io.netty:netty-codec-http:" + version, "downloads": {"artifact": {
                            "path": relative, "url": "https://libraries.minecraft.net/" + relative,
                            "size": len(raw), "sha1": hashlib.sha1(raw).hexdigest()}}}]}
                    data = json.dumps(manifest).encode()
                    (manifests / (game + ".json")).write_bytes(data)
                    pins[game] = http.sha256(data)
            fetch = Mock(side_effect=lambda item: raws[item["coordinate"].split(":")[-1]])
            with patch.dict(http.MANIFEST_SHA256, pins, clear=True):
                official.prepare(http, manifests, libraries, fetch)
                self.assertEqual(fetch.call_count, 3)
                self.assertEqual(len(list(libraries.rglob("*.jar"))), 3)
                with self.assertRaises(FileExistsError):
                    official.prepare(http, manifests, libraries, fetch)
                with self.assertRaisesRegex(http.VerificationError, "size or SHA-1 mismatch"):
                    official.prepare(http, manifests, root / "bad", lambda item: b"bad")
                path = manifests / "26.1.2.json"
                manifest = json.loads(path.read_bytes())
                manifest["libraries"][0]["downloads"]["artifact"]["sha1"] = "0" * 40
                data = json.dumps(manifest).encode()
                path.write_bytes(data)
                http.MANIFEST_SHA256["26.1.2"] = http.sha256(data)
                fetch.reset_mock()
                with self.assertRaisesRegex(http.VerificationError, "conflicting artifact identities"):
                    official.prepare(http, manifests, root / "conflict", fetch)
                fetch.assert_not_called()


if __name__ == "__main__":
    unittest.main()
