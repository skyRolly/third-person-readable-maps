"""Planning-only evidence checks; never a runtime or risk-disposition validator."""
import copy
import importlib.util
import json
from collections import Counter
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "docs/dependency-evidence/issue45-review-preparation-2026-11-25"
SPEC = importlib.util.spec_from_file_location(
    "retained_http_verifier", ROOT / "diagnostics/issue45-runtime/verify_http_artifacts.py")
HTTP = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(HTTP)


def require(condition, message):
    if not condition:
        raise ValueError(message)


def validate_plan(plan):
    require(plan["schema"] == "issue45-spdy-runtime-plan/v1"
            and plan["scope"] == "planning_only"
            and plan["review_status"] == "independent_review_pending"
            and plan["advisory"] == "GHSA-6jqx-86gh-f27w"
            and plan["risk_accepted"] is False and plan["release_blocking"] is True
            and plan["runtime_reachability"] == "not_established", "planning scope changed")
    expected = {game: (group, source, netty) for group, source, netty, games in HTTP.GROUPS for game in games}
    require(plan["occurrences"] == len(HTTP.GROUPS) == 4
            and len(plan["rows"]) == len(expected) == 7, "incorrect manifest coverage")
    seen = set()
    for row in plan["rows"]:
        game = row["game"]
        require(game in expected and game not in seen, "unknown or duplicate game")
        seen.add(game)
        group, source, netty = expected[game]
        require((row["group"], row["source_commit"], row["client_http_coordinate"],
                 row["client_manifest_sha256"]) ==
                (group, source, "io.netty:netty-codec-http:" + netty, HTTP.MANIFEST_SHA256[game]),
                "plan source or manifest identity differs")
        HTTP.manifest_artifact((HTTP.MANIFESTS / (game + ".json")).read_bytes(), game, netty)
        require(row["processes"] == [{"role": "client", "status": "not_executed"},
                {"role": "dedicated_server", "status": "not_executed",
                 "server_bundle_identity": "pending_distribution_specific_verification"}],
                "process plan changed or misrepresents execution")
    return len(seen) * 2


def validate_pilot(pilot):
    require(pilot["schema"] == "issue45-pr22-review-preparation/v1"
            and pilot["scope"] == "unreviewed_comparison_only"
            and pilot["pr"] == 22 and pilot["runtime"] == "1.19.3"
            and pilot["source_sha"] == "a9cd58a4efdb5e9505006bb62914a89e19df0d71"
            and pilot["risk_accepted"] is False and pilot["release_blocking"] is True
            and pilot["local_scan"]["new_gradle_resolution"] is False, "pilot scope changed")
    rows = pilot["findings"]
    require(len(rows) == len({(r["purl"], r["advisory"]) for r in rows}) == 24
            and Counter(r["severity"] for r in rows) ==
            {"CRITICAL": 1, "HIGH": 7, "MODERATE": 15, "LOW": 1}, "pilot finding coverage changed")
    require(all(r["failing"] is True and r["review_status"] == "awaiting investigation"
                and r["scopes"] == ["gradle", "runtime/1.19.3"]
                and re.fullmatch(r"[0-9a-f]{64}", r["fingerprint"])
                and r["proposed_review_step"] for r in rows), "pilot finding scope changed")
    require(pilot["sbom"]["all_branch_coverage_established"] is False
            and pilot["sbom"]["alerts_verified"] is False, "unverified monitoring claim")
    return len(rows)


class ReviewPreparationTests(unittest.TestCase):
    def setUp(self):
        self.plan = json.loads((EVIDENCE / "spdy-runtime-plan.json").read_bytes())
        self.pilot = json.loads((EVIDENCE / "pr22-review-index.json").read_bytes())

    def test_original_plan_and_pilot(self):
        self.assertEqual(validate_plan(self.plan), 14)
        self.assertEqual(validate_pilot(self.pilot), 24)
        self.assertEqual(self.plan["proposal_source_sha256"],
                         self.pilot["inputs_sha256"]["spdy-observation-plan.md"])

    def test_plan_missing_or_duplicate_game(self):
        for rows in (self.plan["rows"][:-1], self.plan["rows"][:-1] + [self.plan["rows"][0]]):
            plan = dict(self.plan, rows=rows)
            with self.assertRaises(ValueError):
                validate_plan(plan)

    def test_plan_source_and_manifest_changes(self):
        for field, value in (("source_commit", "0" * 40), ("client_manifest_sha256", "0" * 64)):
            plan = copy.deepcopy(self.plan)
            plan["rows"][0][field] = value
            with self.assertRaisesRegex(ValueError, "identity differs"):
                validate_plan(plan)

    def test_plan_execution_or_server_assumption_rejected(self):
        for field, value in (("status", "captured"), ("server_bundle_identity", "same_as_client")):
            plan = copy.deepcopy(self.plan)
            plan["rows"][0]["processes"][1][field] = value
            with self.assertRaisesRegex(ValueError, "process plan changed"):
                validate_plan(plan)

    def test_pilot_missing_or_nonblocking_finding_rejected(self):
        pilot = copy.deepcopy(self.pilot)
        pilot["findings"].pop()
        with self.assertRaisesRegex(ValueError, "coverage changed"):
            validate_pilot(pilot)
        pilot = copy.deepcopy(self.pilot)
        pilot["findings"][0]["failing"] = False
        with self.assertRaisesRegex(ValueError, "finding scope changed"):
            validate_pilot(pilot)

    def test_scope_cannot_claim_acceptance_or_alert_verification(self):
        for data, check in ((self.plan, validate_plan), (self.pilot, validate_pilot)):
            with self.assertRaises(ValueError):
                check(dict(data, risk_accepted=True))
        pilot = copy.deepcopy(self.pilot)
        pilot["sbom"]["alerts_verified"] = True
        with self.assertRaisesRegex(ValueError, "monitoring claim"):
            validate_pilot(pilot)


if __name__ == "__main__":
    unittest.main()
