import hashlib
import importlib.util
import io
import json
import tempfile
import unittest
import warnings
import zipfile
from pathlib import Path
from unittest.mock import patch

PATH = Path(__file__).resolve().parents[1] / "diagnostics/issue45-runtime/verify_http_artifacts.py"
SPEC = importlib.util.spec_from_file_location("verify_http_artifacts", PATH)
http = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(http)


class HttpArtifactTests(unittest.TestCase):
    def jar(self, entries):
        buffer = io.BytesIO()
        with warnings.catch_warnings(), zipfile.ZipFile(buffer, "w") as jar:
            warnings.simplefilter("ignore", UserWarning)
            for name, data in entries:
                jar.writestr(name, data)
        return buffer.getvalue()

    def fixture(self, raw):
        netty = "4.2.15.Final"
        path = f"io/netty/netty-codec-http/{netty}/netty-codec-http-{netty}.jar"
        coordinate = "io.netty:netty-codec-http:" + netty
        item = {"path": path, "url": "https://libraries.minecraft.net/" + path,
                "sha1": hashlib.sha1(raw).hexdigest(), "size": len(raw)}
        manifest = {"id": "26.2", "libraries": [{"name": coordinate, "downloads": {"artifact": item}}]}
        return manifest

    def parse(self, manifest):
        data = json.dumps(manifest).encode()
        with patch.dict(http.MANIFEST_SHA256, {"26.2": http.sha256(data)}, clear=True):
            return http.manifest_artifact(data, "26.2", "4.2.15.Final")

    def test_verified_inventory_and_scope(self):
        name = http.PREFIX + "SpdyFrameCodec.class"
        raw = self.jar([(name, b"\xca\xfe\xba\xbe fixture"), ("other.class", b"unrelated")])
        manifest = self.fixture(raw)
        data = json.dumps(manifest).encode()
        artifact = self.parse(manifest)
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "26.2.json").write_bytes(data)
            path = root / artifact["path"]
            path.parent.mkdir(parents=True)
            path.write_bytes(raw)
            with patch.object(http, "GROUPS", (("26.1-26.2", "a" * 40, "4.2.15.Final", ("26.2",)),)), \
                    patch.dict(http.MANIFEST_SHA256, {"26.2": http.sha256(data)}, clear=True):
                report = http.verify(root, root)
                self.assertEqual(report["artifacts"][artifact["coordinate"]]["spdy_class_sha256"],
                                 {name: http.sha256(b"\xca\xfe\xba\xbe fixture")})
                self.assertEqual(report["runtime_reachability"], "not_established")
                self.assertTrue(report["release_blocking"])
                self.assertFalse(report["risk_accepted"])
                self.assertNotIn(str(root), json.dumps(report))
                path.write_bytes(raw[:-1] + bytes([raw[-1] ^ 1]))
                with self.assertRaisesRegex(http.VerificationError, "SHA-1 mismatch"):
                    http.verify(root, root)
                path.unlink()
                with self.assertRaises(FileNotFoundError):
                    http.verify(root, root)

    def test_manifest_validation(self):
        raw = b"fixture"
        manifest = self.fixture(raw)
        with self.assertRaisesRegex(http.VerificationError, "manifest digest mismatch"):
            http.manifest_artifact(json.dumps(manifest).encode(), "26.2", "4.2.15.Final")
        for label, mutate in (
            ("wrong game", lambda m: m.update(id="26.1")),
            ("duplicate", lambda m: m["libraries"].append(m["libraries"][0])),
            ("wrong origin", lambda m: m["libraries"][0]["downloads"]["artifact"].update(url="https://example.org/x")),
            ("traversal", lambda m: m["libraries"][0]["downloads"]["artifact"].update(path="../x")),
            ("wrong version", lambda m: m["libraries"][0].update(name="io.netty:netty-codec-http:4.2.16.Final")),
        ):
            with self.subTest(label=label):
                changed = self.fixture(raw)
                mutate(changed)
                with self.assertRaises(http.VerificationError):
                    self.parse(changed)

    def test_retained_manifest_metadata(self):
        expected = {
            "4.1.118.Final": ("eda08a71294afe78c779b85fd696bc13491507a8", 674362),
            "4.2.7.Final": ("b734c108854099c421fd94d92d9f865e4d4da853", 683327),
            "4.2.15.Final": ("e611826aa054371bb9a17f27bdb05755a4cac5f0", 674986),
        }
        games_seen = set()
        for group, source, netty, games in http.GROUPS:
            for game in games:
                with self.subTest(game=game):
                    self.assertNotIn(game, games_seen)
                    games_seen.add(game)
                    artifact = http.manifest_artifact((http.MANIFESTS / (game + ".json")).read_bytes(), game, netty)
                    self.assertEqual((artifact["sha1"], artifact["size_bytes"]), expected[netty])
        self.assertEqual(games_seen, set(http.MANIFEST_SHA256))

    def test_complete_occurrence_matrix_deduplicates_and_checks_every_manifest(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            pins = {}
            for group, source, netty, games in http.GROUPS:
                raw = self.jar([(http.PREFIX + "SpdyFrameCodec.class", b"\xca\xfe\xba\xbe" + netty.encode())])
                relative = f"io/netty/netty-codec-http/{netty}/netty-codec-http-{netty}.jar"
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(raw)
                for game in games:
                    manifest = self.fixture(raw)
                    manifest["id"] = game
                    entry = manifest["libraries"][0]
                    entry["name"] = "io.netty:netty-codec-http:" + netty
                    entry["downloads"]["artifact"].update(path=relative, url="https://libraries.minecraft.net/" + relative)
                    data = json.dumps(manifest).encode()
                    (root / (game + ".json")).write_bytes(data)
                    pins[game] = http.sha256(data)
            with patch.dict(http.MANIFEST_SHA256, pins, clear=True):
                report = http.verify(root, root)
                self.assertEqual(len(report["occurrences"]), 4)
                self.assertEqual(len(report["artifacts"]), 3)
                self.assertEqual({game for row in report["occurrences"] for game in row["manifest_sha256_by_game"]}, set(pins))
                path = root / "26.1.2.json"
                manifest = json.loads(path.read_bytes())
                manifest["libraries"][0]["downloads"]["artifact"]["sha1"] = "0" * 40
                data = json.dumps(manifest).encode()
                path.write_bytes(data)
                http.MANIFEST_SHA256["26.1.2"] = http.sha256(data)
                with self.assertRaisesRegex(http.VerificationError, "conflicting artifact identities"):
                    http.verify(root, root)

    def test_invalid_inventory(self):
        name = http.PREFIX + "SpdyFrameCodec.class"
        for entries in ([], [(name, b"wrong header")], [(name, b"\xca\xfe\xba\xbe"), (name, b"\xca\xfe\xba\xbe")]):
            with self.subTest(entries=entries):
                raw = self.jar(entries)
                with self.assertRaises(http.VerificationError):
                    http.inspect_jar(raw, self.parse(self.fixture(raw)))


if __name__ == "__main__":
    unittest.main()
