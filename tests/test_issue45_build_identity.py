import hashlib
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

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

    def test_digest_without_python311_api(self):
        path = self.root / "large.bin"
        data = b"abc" * (1024 * 1024) + b"last block"
        path.write_bytes(data)
        # Simulate the unavailable API even on newer CI interpreters.
        with patch.object(hashlib, "file_digest", create=True,
                          side_effect=AssertionError("Python 3.11 API used")):
            self.assertEqual(hashlib.sha256(data).hexdigest(), gate.digest(path))
            path.write_bytes(b"")
            self.assertEqual(hashlib.sha256(b"").hexdigest(), gate.digest(path))

    def cli_failure(self, root=None):
        with patch.object(sys, "argv", ["build_identity.py", "compare", "--reports",
                                      str(root if root is not None else self.root)]), \
                patch.object(gate, "context", return_value=(self.checkout, self.run, self.attempt)):
            with self.assertRaises(SystemExit) as raised:
                gate.cli()
        self.assertIsInstance(raised.exception.code, str)
        return raised.exception.code

    def test_cli_distinguishes_safe_validation_failures(self):
        original = json.loads(self.target.read_text(encoding="utf-8"))
        for field in ("python_version", "inputs", "agent", "profiles", "java_runtime"):
            value = json.loads(json.dumps(original))
            if field == "python_version":
                value[field] = "3.15.3"
            elif field == "java_runtime":
                value[field] = "25.0.2+1"
            elif field == "inputs":
                value[field]["compiler"] = "6" * 64
            elif field == "agent":
                value[field]["jar_sha256"] = "7" * 64
            else:
                value[field][gate.PROFILE_IDS[0]]["archive"]["jar_sha256"] = "8" * 64
            self.target.write_text(json.dumps(value), encoding="utf-8")
            with self.subTest(field=field):
                self.assertEqual(f"compiled build identity: compiled build mismatch: windows-latest Java 25 {field}",
                                 self.cli_failure())
        self.target.unlink()
        self.assertEqual("compiled build identity: missing or unexpected Java reports: windows-latest",
                         self.cli_failure())
        self.assertEqual("compiled build identity: missing or unexpected OS reports",
                         self.cli_failure(self.root / "absent"))

    def test_cli_never_echoes_untrusted_error_details(self):
        secret = "synthetic-secret-do-not-echo"
        expected = "compiled build identity collection or comparison failed"
        # The JSON decoder itself can include untrusted property text.
        self.target.write_text('{"' + secret + '":', encoding="utf-8")
        self.assertEqual(expected, self.cli_failure())
        for error in (ValueError(secret), OSError(secret), KeyError(secret),
                      zipfile.BadZipFile(secret), subprocess.CalledProcessError(1, [secret])):
            with self.subTest(error=type(error).__name__):
                with patch.object(gate, "compare", side_effect=error):
                    self.assertEqual(expected, self.cli_failure())
        value = {"untrusted": secret}
        self.target.write_text(json.dumps(value), encoding="utf-8")
        self.assertEqual("compiled build identity: invalid report fields", self.cli_failure())


    def test_workflow_preserves_matrix_evidence_on_compatibility_failure(self):
        workflow = (GATE_PATH.parents[2] / ".github/workflows/credential-guard-tests.yml").read_text(
            encoding="utf-8")
        guard, compare = workflow.split("  compare-builds:\n")
        ordered_steps = (
            "Collect Java 21 compiled build identity",
            "Collect Java 25 compiled build identity",
            "Upload compiled build identities only",
            "Set up minimum Python for real collection smoke test",
            "Collect real Java 25 compiled build identity on Python 3.10",
            "Verify minimum Python collection matches canonical identity",
            "Test compiled build identity on Python 3.10",
        )
        positions = []
        for name in ordered_steps:
            label = "      - name: " + name + "\n"
            self.assertEqual(guard.count(label), 1)
            positions.append(guard.index(label))
        self.assertEqual(positions, sorted(positions))
        self.assertIn("    needs: guard\n", compare)
        self.assertIn(
            "    if: ${{ !cancelled() && (needs.guard.result == 'success' || needs.guard.result == 'failure') }}\n",
            compare)
        self.assertIn("      - name: Download this attempt's compiled identity reports\n", compare)
        self.assertIn("      - name: Require complete equal compiled artifact matrix\n", compare)
        self.assertNotIn("3.10.22", compare)
        self.assertNotIn("continue-on-error:", workflow)

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
