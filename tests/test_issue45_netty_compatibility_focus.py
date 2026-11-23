"""Regression coverage for the source-bound Netty compatibility focus erratum."""

import copy
import hashlib
import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "diagnostics/issue45-runtime/assess_upstream_compatibility.py"
REGISTER = ROOT / "docs/dependency-evidence/issue45-netty-lz4-high-2026-11-23/priority-register-v6.json"
OLD = ROOT / "docs/dependency-evidence/issue45-runtime-pipeline-2026-11-23/remediation-compatibility.json"
CORRECTED = ROOT / "docs/dependency-evidence/issue45-runtime-pipeline-2026-11-23/remediation-compatibility-v2.json"

SPEC = importlib.util.spec_from_file_location("issue45_netty_focus", SCRIPT)
FOCUS = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(FOCUS)
VALIDATOR_SPEC = importlib.util.spec_from_file_location(
    "issue45_runtime_validator_for_focus",
    ROOT / "diagnostics/issue45-runtime/validate_runtime_evidence.py")
VALIDATOR = importlib.util.module_from_spec(VALIDATOR_SPEC)
VALIDATOR_SPEC.loader.exec_module(VALIDATOR)


class NettyFocusErratumTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.register = json.loads(REGISTER.read_text(encoding="utf-8"))
        cls.report = json.loads(CORRECTED.read_text(encoding="utf-8"))

    def test_cross_platform_java_tests_have_independent_native_exit_codes(self):
        workflow = (ROOT / ".github/workflows/credential-guard-tests.yml").read_text(
            encoding="utf-8")
        archive_cmd = ("python diagnostics/issue45-runtime/validate_runtime_evidence.py "
                       "--evidence-dir docs/dependency-evidence/issue45-runtime-pipeline-2026-11-23")
        runtime_cmd = ('python -m unittest discover -s tests '
                       '-p "test_issue45_runtime_pipeline_evidence.py" -v')
        erratum_cmd = ('python -m unittest discover -s tests '
                       '-p "test_issue45_netty_compatibility_focus.py" -v')
        for major in (21, 25):
            for label, cmd in (
                    (f"Validate regenerated Java {major} runtime archive", archive_cmd),
                    (f"Test Java {major} runtime evidence and privacy regressions", runtime_cmd),
                    (f"Test Java {major} Netty erratum mutation regressions", erratum_cmd)):
                with self.subTest(java=major, step=label):
                    # GitHub checks individual native process exit codes only
                    # when each command has its own step, not a PowerShell
                    # multiline script whose last command masks previous ones.
                    self.assertIn(f"      - name: {label}\n        run: {cmd}\n",
                                  workflow)
        self.assertEqual(2, workflow.count(f"        run: {archive_cmd}"))
        self.assertEqual(2, workflow.count(f"        run: {runtime_cmd}"))
        self.assertEqual(2, workflow.count(f"        run: {erratum_cmd}"))
        # Regression control: silently combining commands into one multiline
        # step must invalidate the explicit fail-closed workflow invariant.
        masked = workflow.replace(f"        run: {archive_cmd}",
                                  f"        run: |\n          {archive_cmd}", 1)
        self.assertNotIn(
            f"      - name: Validate regenerated Java 21 runtime archive\n"
            f"        run: {archive_cmd}\n", masked)

    def test_historical_v1_report_is_immutable_and_source_bound(self):
        self.assertEqual(
            "8312b41b86992cb3dc6aff10f8d01184248abe9cadaf58b754967f157962ee09",
            hashlib.sha256(OLD.read_bytes()).hexdigest())
        self.assertEqual(
            "f4e024727fea2fd9afebf19892e5a3982fc7868c1ca294f6e16396a106871798",
            hashlib.sha256(REGISTER.read_bytes()).hexdigest())
        self.assertEqual([], FOCUS.validate_compatibility_erratum(self.report, self.register))

    def test_15_indexed_boundaries_are_not_15_focused_investigations(self):
        indexed = FOCUS.fixed_boundaries(self.register)
        focused = [row for row in indexed if row["focused_evidence"]]
        unfocused = [row for row in indexed if not row["focused_evidence"]]
        self.assertEqual((15, 7, 8), (len(indexed), len(focused), len(unfocused)))
        self.assertEqual({row["advisory_id"] for row in indexed},
                         {row["advisory_id"] for row in focused} |
                         {row["advisory_id"] for row in unfocused})
        self.assertFalse({row["advisory_id"] for row in focused} &
                         {row["advisory_id"] for row in unfocused})
        self.assertEqual(
            {"4.1": "4.1.137.Final", "4.2": "4.2.17.Final"},
            FOCUS.maximum_fixed_boundaries(indexed))
        self.assertEqual(
            FOCUS.maximum_fixed_boundaries(indexed),
            FOCUS.maximum_fixed_boundaries(focused))

    def test_forged_unfocused_advisory_cannot_claim_review(self):
        mutated = copy.deepcopy(self.register)
        item = next(row for row in mutated["advisories"]
                    if row["advisory_id"] == "GHSA-6jqx-86gh-f27w")
        self.assertIsNone(item["focused_evidence"])
        item["focused_evidence"] = "forged-review.json"
        errors = FOCUS.validate_compatibility_erratum(self.report, mutated)
        self.assertTrue(any("focus or fixed-boundary mismatch" in e for e in errors), errors)

    def test_duplicate_advisory_identity_is_rejected(self):
        mutated = copy.deepcopy(self.register)
        mutated["advisories"].append(copy.deepcopy(mutated["advisories"][0]))
        errors = FOCUS.validate_compatibility_erratum(self.report, mutated)
        self.assertTrue(any("duplicate advisory identity" in e for e in errors), errors)

    def test_modified_upstream_boundary_requires_review(self):
        mutated = copy.deepcopy(self.register)
        item = next(row for row in mutated["advisories"]
                    if row["advisory_id"] == "GHSA-c4c3-7fpv-j4q5")
        groups = item["affected_ranges"]["pkg:maven/io.netty/netty-handler"]
        changed = False
        for group in groups:
            for entry in group:
                for event in entry.get("events", []):
                    if event.get("fixed") == "4.1.137.Final":
                        event["fixed"] = "4.1.138.Final"
                        changed = True
        self.assertTrue(changed)
        errors = FOCUS.validate_compatibility_erratum(self.report, mutated)
        self.assertTrue(any("fixed-boundary mismatch" in e for e in errors), errors)

    def test_wrong_historical_and_source_provenance_rejected(self):
        for field, subfield in (("historical_v1_report", "sha256"),
                                ("source_register", "sha256")):
            with self.subTest(field=field):
                mutated = copy.deepcopy(self.report)
                mutated[field][subfield] = "0" * 64
                errors = FOCUS.validate_compatibility_erratum(mutated, self.register)
                self.assertTrue(any("report" in e or "register" in e for e in errors), errors)

    def test_full_archive_fails_closed_on_tampered_or_missing_v2(self):
        evidence = ROOT / "docs/dependency-evidence/issue45-runtime-pipeline-2026-11-23"
        with tempfile.TemporaryDirectory(prefix="issue45-focus-archive-") as tmp:
            copied = Path(tmp) / "archive"
            shutil.copytree(evidence, copied)
            errors, result = VALIDATOR.validate_evidence(copied, ROOT)
            self.assertEqual([], errors)
            self.assertEqual(0, result["captured_runtime_environment_count"])
            v2_path = copied / "remediation-compatibility-v2.json"
            amended = json.loads(v2_path.read_text(encoding="utf-8"))
            amended["focused_netty_advisory_count"] = 15
            v2_path.write_text(json.dumps(amended), encoding="utf-8")
            errors, _ = VALIDATOR.validate_evidence(copied, ROOT)
            self.assertTrue(any("corrected Netty compatibility" in e for e in errors), errors)
            v2_path.unlink()
            errors, _ = VALIDATOR.validate_evidence(copied, ROOT)
            self.assertTrue(any("corrected Netty compatibility record missing" in e
                                for e in errors), errors)

    def test_empty_duplicate_and_partial_v2_environment_matrices_are_rejected(self):
        for changed in ([], [copy.deepcopy(self.report["environments"][0])],
                        self.report["environments"][:-1]):
            with self.subTest(rows=len(changed)):
                modified = copy.deepcopy(self.report)
                modified["environments"] = changed
                errors = FOCUS.validate_compatibility_erratum(modified, self.register)
                self.assertTrue(any("environment" in error for error in errors), errors)
        duplicate = copy.deepcopy(self.report)
        duplicate["environments"][1]["environment_id"] = duplicate["environments"][0]["environment_id"]
        errors = FOCUS.validate_compatibility_erratum(duplicate, self.register)
        self.assertTrue(any("duplicated" in error for error in errors), errors)

    def test_26_2_forged_fixed_version_with_self_consistent_flags_is_rejected(self):
        forged = copy.deepcopy(self.report)
        row = next(row for row in forged["environments"]
                   if row["environment_id"] == "minecraft-26.2-client")
        row["manifest_or_bundle_netty_version"] = "4.2.17.Final"
        row["all_indexed_netty_boundaries_met"] = True
        row["focused_netty_boundaries_met"] = True
        row["lz4_advisory_fixed_boundary_met_by_selected_artifact_version"] = True
        errors = FOCUS.validate_compatibility_erratum(forged, self.register)
        self.assertTrue(any("pinned matrix" in error for error in errors), errors)

    def test_forged_matrix_version_cannot_override_independent_verified_pin(self):
        matrix_path = ROOT / "docs/dependency-evidence/issue45-runtime-pipeline-2026-11-23/environment-matrix.json"
        matrix = json.loads(matrix_path.read_text(encoding="utf-8"))
        trusted_pins = {
            row["environment_id"]:
            (row.get("expected_netty_codec") or row.get("expected_bundled_netty_codec"))
            for row in matrix["environments"]}
        modified = copy.deepcopy(matrix)
        target = next(row for row in modified["environments"]
                      if row["environment_id"] == "minecraft-26.2-client")
        target["expected_netty_codec"] = "4.2.17.Final"
        errors = FOCUS.validate_compatibility_erratum(
            self.report, self.register, matrix=modified, pinned_versions=trusted_pins)
        self.assertTrue(any("independently verified artifact pin" in error
                            for error in errors), errors)

    def test_wrong_lz4_flag_and_unsupported_runtime_claims_are_rejected(self):
        mutations = (
            ("lz4_advisory_fixed_boundary_met_by_selected_artifact_version", True,
             "incorrect lz4_advisory"),
            ("supported_jvm_execution_verified", True, "overstates runtime"),
            ("runtime_loader_selection_verified", True, "overstates runtime"),
            ("minecraft_fabric_abi_verified", True, "overstates runtime"),
            ("no_dependency_override_performed", False, "overstates runtime"),
            ("outcome", "fixed", "overstates runtime"),
        )
        for field, value, expected_error in mutations:
            with self.subTest(field=field):
                modified = copy.deepcopy(self.report)
                modified["environments"][0][field] = value
                errors = FOCUS.validate_compatibility_erratum(modified, self.register)
                self.assertTrue(any(expected_error in error for error in errors), errors)

    def test_archived_v1_reformat_without_value_change_is_rejected(self):
        evidence = ROOT / "docs/dependency-evidence/issue45-runtime-pipeline-2026-11-23"
        with tempfile.TemporaryDirectory(prefix="issue45-v1-copy-") as tmp:
            copied = Path(tmp) / "archive"
            shutil.copytree(evidence, copied)
            original = copied / "remediation-compatibility.json"
            original.write_text(json.dumps(json.loads(original.read_text(encoding="utf-8")),
                                           indent=3, sort_keys=False) + "\n",
                                encoding="utf-8")
            self.assertNotEqual(hashlib.sha256(OLD.read_bytes()).hexdigest(),
                                hashlib.sha256(original.read_bytes()).hexdigest())
            errors, _ = VALIDATOR.validate_evidence(copied, ROOT)
            self.assertTrue(any("archived Netty v1 historical report SHA-256" in error
                                for error in errors), errors)

    def test_forged_client_manifest_from_another_minecraft_release_fails_full_archive(self):
        evidence = ROOT / "docs/dependency-evidence/issue45-runtime-pipeline-2026-11-23"
        with tempfile.TemporaryDirectory(prefix="issue45-forged-manifest-") as tmp:
            archive = Path(tmp) / "archive"
            shutil.copytree(evidence, archive)
            matrix_path = archive / "environment-matrix.json"
            matrix = json.loads(matrix_path.read_text(encoding="utf-8"))
            one19 = next(r for r in matrix["environments"]
                         if r["environment_id"] == "minecraft-1.19-client")
            newest = next(r for r in matrix["environments"]
                          if r["environment_id"] == "minecraft-26.2-client")
            # Every mutable field agrees internally; only the source-controlled
            # game identity mapping can detect the substitution.
            for name in ("manifest_path", "manifest_sha256", "expected_netty_codec"):
                one19[name] = newest[name]
            matrix_path.write_text(json.dumps(matrix), encoding="utf-8")
            v2_path = archive / "remediation-compatibility-v2.json"
            report = json.loads(v2_path.read_text(encoding="utf-8"))
            row = next(r for r in report["environments"]
                       if r["environment_id"] == "minecraft-1.19-client")
            row.update(manifest_or_bundle_netty_version="4.2.15.Final",
                       expected_dependency_family="4.2",
                       lz4_advisory_fixed_boundary_met_by_selected_artifact_version=True,
                       module_family_consistent_at_source_manifest=True,
                       all_indexed_netty_boundaries_met=False,
                       focused_netty_boundaries_met=False)
            v2_path.write_text(json.dumps(report), encoding="utf-8")
            errors, _ = VALIDATOR.validate_evidence(archive, ROOT)
            self.assertTrue(any("source-controlled environment pin mismatch" in error
                                for error in errors), errors)
            self.assertTrue(any("verified Netty artifact pins do not cover" in error
                                for error in errors), errors)

    def test_manifest_internal_id_and_digest_are_independently_checked(self):
        evidence = ROOT / "docs/dependency-evidence/issue45-runtime-pipeline-2026-11-23"
        matrix = json.loads((evidence / "environment-matrix.json").read_text(encoding="utf-8"))
        client = next(row for row in matrix["environments"]
                      if row["environment_id"] == "minecraft-1.19-client")
        with tempfile.TemporaryDirectory(prefix="issue45-manifest-id-") as tmp:
            root = Path(tmp)
            manifest = ROOT / client["manifest_path"]
            manifest_copy = root / client["manifest_path"]
            manifest_copy.parent.mkdir(parents=True)
            value = json.loads(manifest.read_text(encoding="utf-8"))
            value["id"] = "26.2"
            manifest_copy.write_text(json.dumps(value), encoding="utf-8")
            modified = copy.deepcopy(client)
            modified["manifest_sha256"] = hashlib.sha256(manifest_copy.read_bytes()).hexdigest()
            # A tampered manifest or archive row cannot override the independent pin.
            errors, _ = VALIDATOR.validate_environment_artifact_pin(
                modified, root, json.loads((evidence / "baseline-lock.json").read_text())["retained_files"])
            self.assertTrue(any("source-controlled environment pin mismatch" in e
                                for e in errors), errors)
            # Force the trusted digest check to pass temporarily to isolate
            # validation of the manifest's internal release id.
            with mock.patch.dict(VALIDATOR.TRUSTED_ENVIRONMENTS,
                                 {"minecraft-1.19-client": {**VALIDATOR.TRUSTED_ENVIRONMENTS["minecraft-1.19-client"],
                                     "manifest_sha256": modified["manifest_sha256"]}}):
                errors, _ = VALIDATOR.validate_environment_artifact_pin(
                    modified, root, {})
            self.assertTrue(any("manifest id differs" in e for e in errors), errors)

    def test_missing_or_nonstring_environment_id_returns_structured_invalid_archive(self):
        evidence = ROOT / "docs/dependency-evidence/issue45-runtime-pipeline-2026-11-23"
        for bad in (None, ["invalid"], "", 123):
            with self.subTest(value=bad):
                with tempfile.TemporaryDirectory(prefix="issue45-malformed-id-") as tmp:
                    archive = Path(tmp) / "archive"
                    shutil.copytree(evidence, archive)
                    path = archive / "environment-matrix.json"
                    matrix = json.loads(path.read_text(encoding="utf-8"))
                    if bad is None:
                        matrix["environments"][0].pop("environment_id")
                    else:
                        matrix["environments"][0]["environment_id"] = bad
                    path.write_text(json.dumps(matrix), encoding="utf-8")
                    command = [sys.executable, str(ROOT /
                               "diagnostics/issue45-runtime/validate_runtime_evidence.py"),
                               "--evidence-dir", str(archive)]
                    process = subprocess.run(command, cwd=ROOT,
                                             capture_output=True, text=True)
                    self.assertEqual(1, process.returncode, process.stderr)
                    result = json.loads(process.stdout)
                    self.assertEqual("invalid_archive", result["result"])
                    self.assertTrue(any("identities" in e for e in result["errors"]))

    def test_v2_list_valued_id_is_normal_validation_error(self):
        bad = copy.deepcopy(self.report)
        bad["environments"][0]["environment_id"] = ["incorrect"]
        errors = FOCUS.validate_compatibility_erratum(bad, self.register)
        self.assertTrue(any("identities" in e for e in errors), errors)

    def test_v1_reformat_and_self_consistent_new_v2_digest_cannot_reanchor_history(self):
        evidence = ROOT / "docs/dependency-evidence/issue45-runtime-pipeline-2026-11-23"
        with tempfile.TemporaryDirectory(prefix="issue45-immutable-v1-") as tmp:
            archive = Path(tmp) / "archive"
            shutil.copytree(evidence, archive)
            v1_path = archive / "remediation-compatibility.json"
            v1_path.write_text(json.dumps(json.loads(v1_path.read_text(encoding="utf-8")),
                                          indent=4, sort_keys=False) + "\n", encoding="utf-8")
            new_hash = hashlib.sha256(v1_path.read_bytes()).hexdigest()
            self.assertNotEqual(FOCUS.HISTORICAL_V1_SHA256, new_hash)
            v2_path = archive / "remediation-compatibility-v2.json"
            derived = json.loads(v2_path.read_text(encoding="utf-8"))
            derived["historical_v1_report"]["sha256"] = new_hash
            v2_path.write_text(json.dumps(derived), encoding="utf-8")
            with mock.patch.object(FOCUS, "OUT", archive):
                errors = FOCUS.validate_compatibility_erratum(
                    derived, self.register, archive_v1_path=v1_path)
                self.assertTrue(any("Netty v1 historical report source provenance mismatch" in e
                                    for e in errors), errors)
                self.assertTrue(any("archived Netty v1 historical report SHA-256" in e
                                    for e in errors), errors)
                with self.assertRaisesRegex(SystemExit, "historical compatibility report SHA-256 mismatch"):
                    FOCUS.main()
            errors, _ = VALIDATOR.validate_evidence(archive, ROOT)
            self.assertTrue(any("historical report" in e for e in errors), errors)

    def test_server_summary_live_selection_or_artifact_forgery_is_rejected(self):
        for name in ("minecraft_1_19_server_bundle", "minecraft_26_1_2_server_bundle"):
            for field, value in (("live_selection_verified", True),
                                 ("server_bundle_sha256", "0" * 64),
                                 ("netty_module_versions", ["4.2.17.Final"])):
                with self.subTest(summary=name, mutation=field):
                    edited = copy.deepcopy(self.report)
                    edited[name][field] = value
                    errors = FOCUS.validate_compatibility_erratum(edited, self.register)
                    self.assertTrue(any("server bundle summary contradicts" in e
                                        for e in errors), errors)

    def test_incorrect_environment_boundary_claim_is_rejected(self):
        mutated = copy.deepcopy(self.report)
        mutated["environments"][0]["all_indexed_netty_boundaries_met"] = True
        errors = FOCUS.validate_compatibility_erratum(mutated, self.register)
        self.assertTrue(any("incorrect all_indexed_netty_boundaries_met" in e
                            for e in errors), errors)


if __name__ == "__main__":
    unittest.main()
