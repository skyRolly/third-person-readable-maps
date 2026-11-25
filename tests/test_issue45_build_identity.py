import hashlib
import importlib.util
import json
import os
import shlex
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path, PurePosixPath
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
                                      "classpath": [f"{j + 1:064x}" for j in range(8 if i % 2 else 7)]}
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
                     lambda v: v["profiles"][gate.PROFILE_IDS[0]]["classpath"].reverse(),
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
            "Test cross-version pinned Python handoff",
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
        self.assert_workflow_artifact_paths(workflow)

    def assert_workflow_artifact_paths(self, workflow):
        guard = workflow.split("  compare-builds:\n", 1)[0]
        attempt = "${{ github.run_id }}-${{ github.run_attempt }}"
        canonical_dir = "${{ runner.temp }}/issue45-compiled-identity-" + attempt
        smoke_dir = "${{ runner.temp }}/issue45-compiled-identity-smoke-" + attempt

        def field(name, key, indent):
            label = f"      - name: {name}\n"
            self.assertEqual(guard.count(label), 1, name)
            block = guard.split(label, 1)[1].split("\n      - ", 1)[0]
            prefix = " " * indent + key + ": "
            values = [line[len(prefix):] for line in block.splitlines()
                      if line.startswith(prefix)]
            self.assertEqual(len(values), 1, f"{name}: {key}")
            return values[0]

        def output(name):
            args = shlex.split(field(name, "run", 8))
            minimum = name == "Collect real Java 25 compiled build identity on Python 3.10"
            pin = ["python", "scripts/run_pinned_python.py",
                   "${{ steps.minimum_python.outputs.python-path }}" if minimum else
                   "${{ steps.canonical_python.outputs.python-path }}",
                   "3.10.22" if minimum else "3.15.2"]
            self.assertEqual(args[:6], pin + ["diagnostics/issue45-runtime/build_identity.py", "collect"])
            # argparse accepts both --option value and --option=value, and
            # normally allows abbreviations and repeated options (last wins).
            # For this workflow require exactly one of each full option name.
            allowed = {"--work-dir", "--java-major", "--os", "--output"}
            values = {}
            index = 6
            while index < len(args):
                option, equals, value = args[index].partition("=")
                self.assertIn(option, allowed, "unexpected collector option")
                self.assertNotIn(option, values, f"duplicate collector option: {option}")
                index += 1
                if not equals:
                    self.assertLess(index, len(args), f"missing collector value: {option}")
                    value = args[index]
                    index += 1
                self.assertTrue(value and not value.startswith("-"),
                                f"missing collector value: {option}")
                values[option] = value
            self.assertEqual(set(values), allowed, "missing collector option")
            major = 21 if name == "Collect Java 21 compiled build identity" else 25
            work = "issue45-agent-j21" if major == 21 else "issue45-agent-café-j25"
            self.assertEqual(values["--work-dir"], "${{ runner.temp }}/" + work)
            self.assertEqual(values["--java-major"], str(major))
            self.assertEqual(values["--os"], "${{ matrix.os }}")
            return values["--output"]

        upload = field("Upload compiled build identities only", "path", 10)
        self.assertEqual(upload, canonical_dir, "canonical upload must use only its attempt directory")
        reports = {}
        for major in (21, 25):
            reports[major] = output(f"Collect Java {major} compiled build identity")
            self.assertEqual(reports[major], f"{upload}/identity-j{major}.json",
                             "canonical collection output must match upload directory")

        smoke = output("Collect real Java 25 compiled build identity on Python 3.10")
        self.assertFalse(PurePosixPath(smoke).is_relative_to(PurePosixPath(upload)),
                         "smoke report must be outside canonical upload directory")
        self.assertEqual(smoke, f"{smoke_dir}/identity-j25.json",
                         "smoke report must use its separate attempt directory")
        parity = shlex.split(field("Verify minimum Python collection matches canonical identity", "run", 8))
        self.assertEqual(parity[:5], ["python", "scripts/run_pinned_python.py",
                                     "${{ steps.minimum_python.outputs.python-path }}", "3.10.22", "-c"])
        self.assertEqual(parity[6:], [reports[25], smoke],
                         "parity must compare the actual canonical and smoke outputs")

    def assert_handoff_matrix(self, workflow):
        # This contract intentionally accepts only the two explicit OS entries.
        # Strip comments, but keep indentation and entry boundaries intact.
        strategy = workflow.split("    strategy:\n", 1)[1].split("    steps:\n", 1)[0]
        matrix = [line for line in strategy.splitlines()
                  if line.strip() and not line.lstrip().startswith("#")]
        self.assertEqual(matrix, [
            "      fail-fast: false",
            "      matrix:",
            "        os: [ubuntu-latest, windows-latest]",
            "        include:",
            "          - os: ubuntu-latest",
            "            handoff_python: '3.10.22'",
            "          - os: windows-latest",
            "            handoff_python: '3.10.11'",
        ], "handoff Python versions must be bound to the exact OS matrix entries")

    def test_workflow_rejects_handoff_matrix_mutations(self):
        workflow = (GATE_PATH.parents[2] / ".github/workflows/credential-guard-tests.yml").read_text(
            encoding="utf-8")
        self.assert_handoff_matrix(workflow)
        pin = "            handoff_python: '3.10.11'\n"
        mutations = {
            "pin moved to another entry": workflow.replace(pin, "          - os: macos-latest\n" + pin),
            "missing Windows pin": workflow.replace(pin, ""),
            "wrong Windows version": workflow.replace(pin, "            handoff_python: '3.10.22'\n"),
            "duplicate Windows entry": workflow.replace(pin, pin + "          - os: windows-latest\n" + pin),
            "wrong Windows indentation": workflow.replace(pin, "          handoff_python: '3.10.11'\n"),
        }
        for name, mutated in mutations.items():
            with self.subTest(name=name):
                self.assertNotEqual(mutated, workflow)
                with self.assertRaisesRegex(AssertionError, "handoff Python versions must be bound"):
                    self.assert_handoff_matrix(mutated)

    def test_workflow_uses_explicit_setup_python_executables(self):
        workflow = (GATE_PATH.parents[2] / ".github/workflows/credential-guard-tests.yml").read_text(
            encoding="utf-8")
        guard, comparison = workflow.split("  compare-builds:\n", 1)
        canonical, minimum = guard.split("      - name: Set up minimum Python for real collection smoke test\n", 1)
        self.assert_handoff_matrix(workflow)
        for block, step, version in ((canonical, "canonical_python", "3.15.2"),
                                     (minimum, "minimum_python", "${{ matrix.handoff_python }}"),
                                     (comparison, "canonical_python", "3.15.2")):
            self.assertEqual(block.count("        id: " + step + "\n"), 1)
            self.assertIn("          python-version: '" + version + "'", block)
            commands = [shlex.split(line.strip()[5:]) for line in block.splitlines()
                        if line.strip().startswith("run: ")]
            self.assertTrue(commands)
            for args in commands:
                expected = version
                if step == "minimum_python" and "test_pinned_python.py" not in args:
                    expected = "3.10.22"
                self.assertEqual(args[:4], ["python", "scripts/run_pinned_python.py",
                                           "${{ steps." + step + ".outputs.python-path }}", expected])
        self.assertNotIn("shell:", workflow)
        setup, handoff = minimum.split("      - name: Test cross-version pinned Python handoff\n", 1)
        handoff = handoff.split("\n      - ", 1)[0]
        for step in (setup, handoff):
            self.assertNotIn("        if:", step, "handoff must run on both OS runners")
            self.assertNotIn("continue-on-error:", step)
        self.assertIn(' -m unittest discover -s tests -p "test_pinned_python.py" -v', handoff)
        self.assertIn("          ISSUE45_PINNED_TEST_TARGET: ${{ steps.canonical_python.outputs.python-path }}", handoff)
        self.assertIn("          ISSUE45_PINNED_TEST_REQUIRED: '1'", handoff)

    def test_workflow_requires_guard_success_after_comparison(self):
        workflow = (GATE_PATH.parents[2] / ".github/workflows/credential-guard-tests.yml").read_text(
            encoding="utf-8")
        comparison = workflow.split("  compare-builds:\n", 1)[1]
        label = "      - name: Require successful guard and interpreter handoff\n"
        self.assertEqual(comparison.count(label), 1)
        before, final = comparison.split(label, 1)
        self.assertIn("      - name: Require complete equal compiled artifact matrix\n", before)
        # This is a separate native step after the actual comparison, not a
        # replacement for it. No status override can suppress its exit code.
        lines = final.splitlines()
        self.assertEqual(len(lines), 3)
        self.assertTrue(lines[0].startswith("        run: "))
        self.assertEqual(lines[1:], ["        env:",
                                   "          ISSUE45_GUARD_RESULT: ${{ needs.guard.result }}"])
        args = shlex.split(lines[0].strip()[5:])
        self.assertEqual(args[:5], ["python", "scripts/run_pinned_python.py",
                                   "${{ steps.canonical_python.outputs.python-path }}", "3.15.2", "-c"])
        self.assertEqual(len(args), 6)
        for result in ("success", "failure", "skipped", "cancelled", None):
            with self.subTest(guard_result=result):
                env = dict(os.environ)
                env.pop("ISSUE45_GUARD_RESULT", None)
                if result is not None:
                    env["ISSUE45_GUARD_RESULT"] = result
                process = subprocess.run([sys.executable, *args[4:]], env=env,
                                         capture_output=True, text=True, check=False)
                self.assertEqual(process.returncode, 0 if result == "success" else 1)
                if result != "success":
                    self.assertIn("diagnostic guard or interpreter handoff did not pass", process.stderr)

    def test_workflow_rejects_artifact_path_mutations(self):
        workflow = (GATE_PATH.parents[2] / ".github/workflows/credential-guard-tests.yml").read_text(
            encoding="utf-8")
        attempt = "${{ github.run_id }}-${{ github.run_attempt }}"
        canonical = "${{ runner.temp }}/issue45-compiled-identity-" + attempt
        smoke = "${{ runner.temp }}/issue45-compiled-identity-smoke-" + attempt
        mutations = (
            ("smoke in canonical", smoke, canonical, 2, "smoke report must be outside"),
            ("nested smoke", smoke, canonical + "/smoke", 2, "smoke report must be outside"),
            ("parent traversal", smoke, smoke + "/../" + canonical.rsplit("/", 1)[1], 2,
             "smoke report must use its separate attempt directory"),
            ("broader upload", "path: " + canonical, "path: ${{ runner.temp }}", 1,
             "canonical upload must use only"),
            ("wildcard upload", "path: " + canonical, "path: " + canonical + "*", 1,
             "canonical upload must use only"),
            ("wrong Java 21 output", canonical + "/identity-j21.json",
             smoke + "/identity-j21.json", 1, "canonical collection output must match"),
            ("wrong parity input", f'"{canonical}/identity-j25.json" "{smoke}/identity-j25.json"',
             f'"{canonical}/identity-j25.json" "{canonical}/identity-j25.json"', 1,
             "parity must compare"),
        )
        self.assert_workflow_artifact_paths(workflow)
        for name, before, after, count, message in mutations:
            with self.subTest(mutation=name):
                self.assertEqual(workflow.count(before), count)
                changed = workflow.replace(before, after)
                with self.assertRaisesRegex(AssertionError, message):
                    self.assert_workflow_artifact_paths(changed)

    def test_workflow_rejects_collector_output_overrides(self):
        workflow = (GATE_PATH.parents[2] / ".github/workflows/credential-guard-tests.yml").read_text(
            encoding="utf-8")
        attempt = "${{ github.run_id }}-${{ github.run_attempt }}"
        canonical = "${{ runner.temp }}/issue45-compiled-identity-" + attempt
        smoke = "${{ runner.temp }}/issue45-compiled-identity-smoke-" + attempt
        cases = (
            ("Collect Java 21 compiled build identity", f"{canonical}/identity-j21.json",
             f"{smoke}/identity-j21.json"),
            ("Collect Java 25 compiled build identity", f"{canonical}/identity-j25.json",
             f"{smoke}/identity-j25.json"),
            ("Collect real Java 25 compiled build identity on Python 3.10", f"{smoke}/identity-j25.json",
             f"{canonical}/identity-j25.json"),
        )

        def with_output(source, name, expected, replacement):
            label = f"      - name: {name}\n"
            self.assertEqual(source.count(label), 1)
            before, block = source.split(label, 1)
            step, separator, after = block.partition("\n      - ")
            self.assertTrue(separator)
            lines = step.split("\n")
            run_prefix = "        run: "
            indices = [i for i, line in enumerate(lines) if line.startswith(run_prefix)]
            self.assertEqual(len(indices), 1, name)
            line = indices[0]
            args = shlex.split(lines[line][len(run_prefix):])
            outputs = [i for i, arg in enumerate(args)
                       if arg == "--output" or arg.startswith("--output=")]
            self.assertEqual(len(outputs), 1, name)
            index = outputs[0]
            if args[index] == "--output":
                self.assertLess(index + 1, len(args), name)
                self.assertEqual(args[index + 1], expected, name)
                end = index + 2
            else:
                self.assertEqual(args[index], f"--output={expected}", name)
                end = index + 1
            # Serialize only the in-memory fixture; never execute this shell text.
            lines[line] = run_prefix + shlex.join(args[:index] + replacement + args[end:])
            return before + label + "\n".join(lines) + separator + after

        self.assert_workflow_artifact_paths(workflow)
        for name, expected, wrong in cases:
            split = ["--output", expected]
            equals = [f"--output={expected}"]
            for spelling, original in (("split", split), ("equals", equals)):
                baseline = with_output(workflow, name, expected, original)
                with self.subTest(step=name, spelling=spelling, form="valid baseline"):
                    self.assert_workflow_artifact_paths(baseline)

                mutations = (
                    ("trailing equals", original + [f"--output={wrong}"], "duplicate collector option"),
                    ("leading equals", [f"--output={wrong}"] + original, "duplicate collector option"),
                    ("two equals", equals + [f"--output={wrong}"], "duplicate collector option"),
                    ("two split", split + ["--output", wrong], "duplicate collector option"),
                    ("same path twice", original + equals, "duplicate collector option"),
                    ("abbreviated equals", original + [f"--out={wrong}"], "unexpected collector option"),
                    ("abbreviated split", original + ["--out", wrong], "unexpected collector option"),
                    ("abbreviated alone", [f"--out={expected}"], "unexpected collector option"),
                    ("missing value", ["--output"], "missing collector value"),
                    ("empty equals", ["--output="], "missing collector value"),
                    ("missing option", [], "missing collector option"),
                    ("extra token", original + ["unexpected"], "unexpected collector option"),
                )
                for form, replacement, message in mutations:
                    with self.subTest(step=name, spelling=spelling, form=form):
                        changed = with_output(baseline, name, expected, replacement)
                        with self.assertRaisesRegex(AssertionError, message):
                            self.assert_workflow_artifact_paths(changed)

    def load_controls(self):
        spec = importlib.util.spec_from_file_location("identity_control_harness",
                                                      GATE_PATH.with_name("run_controls.py"))
        controls = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(controls)
        return controls

    def test_control_build_record_uses_observed_classpath_order(self):
        controls = self.load_controls()
        root = self.root / "control-build"
        root.mkdir()
        source, compiler = root / "ControlMain.java", root / "compiler.jar"
        source.write_bytes(b"synthetic source")
        compiler.write_bytes(b"synthetic compiler")
        first, second = root / "first.jar", root / "second.jar"
        first.write_bytes(b"first input")
        second.write_bytes(b"second input")
        jar = root / "issue45-synthetic-control.jar"
        expected = [gate.digest(first), gate.digest(second)]
        actual_cp = os.pathsep.join(map(str, (second, first)))

        invoked = []

        def compile_fake(command, check):
            self.assertTrue(check)
            invoked.append(list(command))
            self.assertEqual(command[command.index("-classpath") + 1], actual_cp)
            (Path(command[command.index("-d") + 1]) / "Control.class").write_bytes(b"class")
            return subprocess.CompletedProcess(command, 0)

        with patch.object(controls.subprocess, "run", side_effect=compile_fake):
            observed_cp, observed_flags = controls.compile_control_jar(root, compiler, source, actual_cp, jar)
        profile_id = gate.PROFILE_IDS[0]
        with patch.dict(os.environ, {"GITHUB_RUN_ID": self.run, "GITHUB_RUN_ATTEMPT": self.attempt,
                                     "RUNNER_OS": "Linux"}), patch("builtins.print"):
            controls.record_control_build_identity(root, profile_id, self.checkout,
                                                   source, compiler, jar, observed_cp, observed_flags,
                                                   "25.0.1+1")
        archive = gate.archive_identity(jar)
        inputs = {"compiler": gate.digest(compiler), "control_source": gate.digest(source)}

        def verify():
            return gate.observed_control_classpath(
                root, profile_id, expected, checkout=self.checkout, run=self.run,
                attempt=self.attempt, system="ubuntu-latest", java_runtime="25.0.1+1",
                inputs=inputs, archive=archive)

        self.assertEqual(verify(), list(reversed(expected)))
        path = root / "control-build-identity.json"
        original = path.read_text(encoding="utf-8")
        self.assertEqual(len(invoked), 1)
        self.assertEqual(json.loads(original)["compiler_flags"],
                         invoked[0][3:invoked[0].index("-classpath")])
        mutations = (
            ("wrong checkout", "source_sha", "b" * 40),
            ("wrong run", "run_id", "456"),
            ("wrong attempt", "run_attempt", "2"),
            ("wrong OS", "runner_os", "Windows"),
            ("wrong Java", "java_runtime", "21.0.1+1"),
            ("wrong profile", "profile_id", gate.PROFILE_IDS[1]),
            ("wrong compiler", "compiler_sha256", "0" * 64),
            ("wrong source", "control_source_sha256", "0" * 64),
            ("wrong JAR", "control_jar_sha256", "0" * 64),
            ("wrong member", "compiled_member_sha256", {"Control.class": "0" * 64}),
            ("wrong flags", "compiler_flags", ["-17"]),
            ("wrong Python", "python_version", "untrusted"),
            ("missing member", "classpath_sha256", expected[:1]),
            ("duplicate member", "classpath_sha256", [expected[0], expected[0]]),
            ("unknown member", "classpath_sha256", [expected[0], "0" * 64]),
            ("invalid hash", "classpath_sha256", [expected[0], 42]),
        )
        for name, key, value in mutations:
            with self.subTest(mutation=name):
                record = json.loads(original)
                record[key] = value
                path.write_text(json.dumps(record), encoding="utf-8")
                with self.assertRaises(gate.IdentityValidationError):
                    verify()
        path.write_text(original.rstrip()[:-1] + ', "profile_id": "duplicate"}', encoding="utf-8")
        with self.assertRaisesRegex(gate.IdentityValidationError, "duplicate JSON key"):
            verify()
        path.unlink()
        with self.assertRaisesRegex(gate.IdentityValidationError, "missing control build identity record"):
            verify()

    def test_java_runtime_probe_ignores_unrelated_non_utf8_properties(self):
        controls = self.load_controls()
        for ending in (b"\n", b"\r\n"):
            for before in (False, True):
                with self.subTest(ending=ending, before=before):
                    property_line = b"    user.name = Jos\xe9"
                    version = b"    java.runtime.version = 25.0.5+8"
                    lines = (property_line, version) if before else (version, property_line)
                    stderr = ending.join(lines) + ending
                    result = subprocess.CompletedProcess([], 0, stdout=b"", stderr=stderr)
                    with patch.object(controls.subprocess, "run", return_value=result) as run:
                        self.assertEqual(controls.current_java_runtime(), "25.0.5+8")
                    run.assert_called_once_with(["java", "-XshowSettings:properties", "-version"],
                                                capture_output=True, check=True)
                    # Exercise the collector's real entry point as well; a wrong
                    # major must reach its identity check, not a Unicode error.
                    with patch.dict(sys.modules, {"run_controls": controls}), \
                            patch.dict(os.environ, {"RUNNER_OS": "Linux"}), \
                            patch.object(gate, "context", return_value=(self.checkout, self.run, self.attempt)), \
                            patch.object(controls.subprocess, "run", return_value=result):
                        with self.assertRaisesRegex(gate.IdentityValidationError, "runtime Java major mismatch"):
                            gate.collect(self.root, 21, "ubuntu-latest")

        for stderr in (b"    user.name = Jos\xe9\n",
                       b"    java.runtime.version = 25.0.5+\xe9\n",
                       b"    java.runtime.version = 25.0.5+8\n    java.runtime.version = 21.0.1+1\n"):
            with self.subTest(invalid_version=stderr):
                with patch.object(controls.subprocess, "run",
                                  return_value=subprocess.CompletedProcess([], 0, b"", stderr)):
                    with self.assertRaisesRegex(SystemExit, "^control compiler Java runtime identity unavailable$"):
                        controls.current_java_runtime()

    def test_java_runtime_ga_and_update_versions_reach_collector(self):
        controls = self.load_controls()
        cases = (
            (21, "21+35-LTS"), (25, "25+36"), (21, "21"),
            (25, "25-ea+17"), (21, "21.0.13+9"),
            (25, "25.0.5+8"), (21, "21.0.12.1+1-1-deb13u1-Debian"),
        )
        for major, version in cases:
            for ending in (b"\n", b"\r\n"):
                with self.subTest(version=version, ending=ending):
                    stderr = ending.join((b"    user.name = Jos\xe9",
                                          b"    java.runtime.version = " + version.encode("ascii"),
                                          b"    user.home = Jos\xe9")) + ending
                    result = subprocess.CompletedProcess([], 0, b"", stderr)
                    with patch.object(controls.subprocess, "run", return_value=result):
                        self.assertEqual(controls.current_java_runtime(), version)
                        with patch.dict(sys.modules, {"run_controls": controls}), \
                                patch.dict(os.environ, {"RUNNER_OS": "Linux"}), \
                                patch.object(gate, "context", return_value=(self.checkout, self.run, self.attempt)), \
                                patch.object(gate, "digest", side_effect=RuntimeError("past runtime check")) as digest:
                            # Correct majors must pass the collector's runtime gate.
                            # Stop at the first pinned dependency read; no network or real build.
                            with self.assertRaisesRegex(RuntimeError, "^past runtime check$"):
                                gate.collect(self.root, major, "ubuntu-latest")
                            digest.assert_called_once()
                            digest.reset_mock()
                            other = 25 if major == 21 else 21
                            with self.assertRaisesRegex(gate.IdentityValidationError, "runtime Java major mismatch"):
                                gate.collect(self.root, other, "ubuntu-latest")
                            digest.assert_not_called()

        for version in ("21.", "21+", "21foo", "21.0.x", "21.0..1", "21+35 LTS", "21+35-é"):
            with self.subTest(invalid=version):
                stderr = b"    java.runtime.version = " + version.encode("utf-8") + b"\n"
                with patch.object(controls.subprocess, "run",
                                  return_value=subprocess.CompletedProcess([], 0, b"", stderr)):
                    with self.assertRaisesRegex(SystemExit, "^control compiler Java runtime identity unavailable$"):
                        controls.current_java_runtime()
                self.assertIsNone(gate.java_runtime_major(version))

    def test_compare_accepts_ga_versions_but_rejects_runtime_drift(self):
        def set_runtime(system, major, version):
            path = self.root / f"issue45-build-{self.run}-{self.attempt}-{system}/identity-j{major}.json"
            report = json.loads(path.read_text(encoding="utf-8"))
            report["java_runtime"] = version
            path.write_text(json.dumps(report), encoding="utf-8")

        for j21, j25 in (("21+35-LTS", "25+36"), ("21", "25"), ("21.0.13+9", "25-ea+17")):
            with self.subTest(java21=j21, java25=j25):
                for system in gate.SYSTEMS:
                    set_runtime(system, 21, j21)
                    set_runtime(system, 25, j25)
                self.assertEqual(self.check()[0], self.archive["jar_sha256"])

        for system in gate.SYSTEMS:
            set_runtime(system, 21, "21+35-LTS")
            set_runtime(system, 25, "25+36")
        for version in ("21+36-LTS", "21.0.1+1", "21-ea+17"):
            with self.subTest(drift=version):
                set_runtime("windows-latest", 21, version)
                with self.assertRaisesRegex(gate.IdentityValidationError,
                                            "compiled build mismatch: windows-latest Java 21 java_runtime"):
                    self.check()
        for version in ("210+35-LTS", "25+36", "21.", "21+", "21foo", "21.0.x",
                        "21.0..1", "21+35 LTS", "21+35-é", 21, None):
            with self.subTest(invalid_or_wrong_major=version):
                set_runtime("windows-latest", 21, version)
                with self.assertRaisesRegex(gate.IdentityValidationError, "invalid Java runtime identity"):
                    self.check()

    def test_compiler_command_drift_fails_before_execution(self):
        controls = self.load_controls()
        root = self.root / "compiler-drift"
        root.mkdir()
        compiler, source, jar = root / "compiler.jar", root / "Control.java", root / "control.jar"
        original = controls.control_compile_command
        mutations = (
            ("changed release", lambda cmd: cmd.__setitem__(5, "-21")),
            ("changed encoding", lambda cmd: cmd.__setitem__(4, "US-ASCII")),
            ("missing release", lambda cmd: cmd.pop(5)),
            ("extra option", lambda cmd: cmd.insert(6, "-g")),
            ("trailing option", lambda cmd: cmd.append("-g")),
            ("duplicate classpath", lambda cmd: cmd.extend(["-classpath", "other"])),
            ("unexpected path-bearing option", lambda cmd: cmd.insert(6, "-processorpath=/private/value")),
        )
        for name, mutate in mutations:
            with self.subTest(mutation=name):
                def changed(compiler, source, classes, compile_cp):
                    command = original(compiler, source, classes, compile_cp)
                    mutate(command)
                    return command

                with patch.object(controls, "control_compile_command", side_effect=changed), \
                        patch.object(controls.subprocess, "run") as run:
                    with self.assertRaisesRegex(SystemExit, "^unexpected control compiler (flags|command)$"):
                        controls.compile_control_jar(root, compiler, source, "classpath", jar)
                    run.assert_not_called()
                self.assertFalse(jar.exists())

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
