"""Regression coverage for the source-bound Netty compatibility focus erratum."""

import copy
import hashlib
import importlib.util
import json
import shutil
import tempfile
import unittest
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

    def test_incorrect_environment_boundary_claim_is_rejected(self):
        mutated = copy.deepcopy(self.report)
        mutated["environments"][0]["all_indexed_netty_boundaries_met"] = True
        errors = FOCUS.validate_compatibility_erratum(mutated, self.register)
        self.assertTrue(any("environment classification" in e for e in errors), errors)


if __name__ == "__main__":
    unittest.main()
