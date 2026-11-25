import importlib.util
import json
import tempfile
import unittest
import zipfile
from pathlib import Path

GATE_PATH = Path(__file__).resolve().parents[1] / "diagnostics/issue45-runtime/build_identity.py"
spec = importlib.util.spec_from_file_location("issue45_build_identity", GATE_PATH)
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)


class BuildIdentityTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.checkout, self.run, self.attempt = "a" * 40, "123", "1"
        self.archive = {"jar_sha256": "1" * 64, "member_count": 1,
                        "ordered_inventory_sha256": "2" * 64,
                        "compiled_count": 1, "compiled_sha256": "3" * 64}
        for system in gate.SYSTEMS:
            folder = self.root / f"issue45-build-{self.run}-{self.attempt}-{system}"
            folder.mkdir()
            for major in gate.MAJORS:
                value = {"schema": gate.SCHEMA, "checkout": self.checkout, "run": self.run,
                         "attempt": self.attempt, "os": system, "java_major": major,
                         "java_runtime": f"{major}.0.1+1", "python_version": "3.15.2",
                         "inputs": {k: "4" * 64 for k in ("compiler", "byteBuddy", "agent_sources",
                                    "control_source", "lock")}, "agent": self.archive,
                         "profiles": {name: {"archive": self.archive,
                                      "classpath": ["5" * 64] * (8 if i % 2 else 7)}
                                      for i, name in enumerate(gate.PROFILE_IDS)}}
                (folder / f"identity-j{major}.json").write_text(json.dumps(value), encoding="utf-8")
        self.target = self.root / "issue45-build-123-1-windows-latest/identity-j25.json"

    def check(self):
        return gate.compare(self.root, self.checkout, self.run, self.attempt)

    def test_complete_matrix(self):
        agent, profiles = self.check()
        self.assertEqual(self.archive["jar_sha256"], agent)
        self.assertEqual(set(gate.PROFILE_IDS), set(profiles))

    def test_mutations_fail(self):
        original = self.target.read_text(encoding="utf-8")
        mutations = [lambda v: v.update(checkout="b" * 40), lambda v: v.update(attempt="2"),
                     lambda v: v.update(os="ubuntu-latest"), lambda v: v.update(java_major=21),
                     lambda v: v.update(java_runtime="25.0.2+1"),
                     lambda v: v["inputs"].update(compiler="6" * 64),
                     lambda v: v["agent"].update(jar_sha256="7" * 64),
                     lambda v: v["agent"].update(compiled_sha256="8" * 64),
                     lambda v: v["agent"].update(ordered_inventory_sha256="9" * 64),
                     lambda v: v["profiles"].pop(gate.PROFILE_IDS[0]),
                     lambda v: v["profiles"][gate.PROFILE_IDS[0]]["classpath"].pop(),
                     lambda v: v["profiles"][gate.PROFILE_IDS[0]]["archive"].update(jar_sha256="a" * 64),
                     lambda v: v.update(extra="untrusted"), lambda v: v["agent"].update(member_count=True)]
        for mutate in mutations:
            with self.subTest(mutation=mutations.index(mutate)):
                value = json.loads(original)
                mutate(value)
                self.target.write_text(json.dumps(value), encoding="utf-8")
                with self.assertRaises(ValueError):
                    self.check()
        self.target.write_text(original[:-1] + ', "schema": "duplicate"}', encoding="utf-8")
        with self.assertRaises(ValueError):
            self.check()
        self.target.unlink()
        with self.assertRaises(ValueError):
            self.check()
        self.target.write_text(original, encoding="utf-8")
        (self.root / "unexpected").mkdir()
        with self.assertRaises(ValueError):
            self.check()

    def test_actual_archive_bytes_and_order(self):
        path = self.root / "control.jar"
        with zipfile.ZipFile(path, "w") as archive:
            archive.writestr("A.class", b"a")
            archive.writestr("B.class", b"b")
        first = gate.archive_identity(path)
        with zipfile.ZipFile(path, "w") as archive:
            archive.writestr("B.class", b"b")
            archive.writestr("A.class", b"a")
        second = gate.archive_identity(path)
        self.assertNotEqual(first["ordered_inventory_sha256"], second["ordered_inventory_sha256"])
        with zipfile.ZipFile(path, "w") as archive:
            archive.writestr("A.class", b"z")
            archive.writestr("B.class", b"b")
        third = gate.archive_identity(path)
        self.assertNotEqual(first["compiled_sha256"], third["compiled_sha256"])
        self.assertEqual(first["compiled_count"], third["compiled_count"])


if __name__ == "__main__":
    unittest.main()
