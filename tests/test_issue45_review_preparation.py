"""Planning-only evidence checks; never a runtime or risk-disposition validator."""
import copy
import hashlib
import importlib.util
import json
from collections import Counter
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "docs/dependency-evidence/issue45-review-preparation-2026-11-25"
FINDING_INDEX = ROOT / "docs/dependency-evidence/issue45-exact-source-2026-11-21-v2/finding-index.json"
FINDING_INDEX_BLOB = "250afd924f72fad2371ca251aec62fde8da0b559"
PILOT_SOURCE = "a9cd58a4efdb5e9505006bb62914a89e19df0d71"
# Historical proposal metadata pins, not a substitute for original external bytes.
# Sources: issue #45 checkpoint / coding-agent comment 7171830911 and
# November 24 hosted audit artifacts 14940902537 and 14941537266.
PILOT_PROVENANCE = {
    "coordinator_checkout": "b7dd973ac76649c8aba25975933ea1aa1c50e980",
    "base_sha": "177f5708727ae4c152091d185536aaa734063280",
    "inputs_sha256": {
        "pr22-local-osv.json": "71d52d77e9102bc4a6142fff9c9a53d39dc7a4f6a99f0ef095ddc251bddb5d6d",
        "pr22-github-graph.json": "0179848d0e9a80eddfa5d8b9e41d08c76a8ccb2aba1dba62fa57038eb7ea5660",
        "pr22-review.md": "e7703d65b3b2afba318edbd1e4391be21209faef6fd6498a5aa3393878fe28da",
        "repository-sbom.json": "86b2fba803d6c6974d05229c90a0bdf960a789fc0e9b496197a4422db140cc07",
        "spdy-observation-plan.md": "e82f1e5c407ed970414ea572b679fa50fd4c144f5b603474b9acefb2ac2b535d"
    },
    "local_scan": {
        "date": "2026-11-25",
        "retained_snapshot_date": "2026-11-21",
        "retained_snapshot_sha256": "d2ddae35341d3b7a9a0dbaada3a50c2eedd1a1004d97e370a149901ae6e5f965",
        "new_gradle_resolution": False
    },
    "hosted_scan": {
        "date": "2026-11-24",
        "run_id": 45436980000,
        "job_id": 138597456039,
        "artifact_id": 14940902537,
        "zip_sha256": "5befb6681dbb59e9cbb64c01564162ce3e2ab17b0b43518f49c9fa482e080841",
        "report_sha256": "23d9934e4402606697545857c2af7ac3eb09154bd470d8423b4c33c9bfdb6a01",
        "snapshot_artifact_id": 14941537266,
        "snapshot_zip_sha256": "b241dff47529939ba67653e003f0e08fe1f2821ffe8db388b198e96a5e1e281c",
        "snapshot_json_sha256": "06bc3dfd8ad68e40fa2b397e104002ceafed6e96aaba3ee9e94c29889537f291"
    },
    "comparison": {
        "normalized_tuples_equal": True,
        "hosted_local_inventories_equal": True,
        "hosted_local_advisory_fingerprints_equal": True,
        "disappeared_matches": 0
    },
    "sbom": {
        "created_utc": "2026-11-25T19:02:18Z",
        "packages": 93,
        "maven_packages": 85,
        "minecraft_entry": "1.21.11",
        "all_branch_coverage_established": False,
        "alerts_verified": False
    }
}
PLAN_PROVENANCE = {
    "coordinator_checkout": "b7dd973ac76649c8aba25975933ea1aa1c50e980",
    "proposal_date": "2026-11-25",
    "proposal_source_sha256": "e82f1e5c407ed970414ea572b679fa50fd4c144f5b603474b9acefb2ac2b535d"
}
SPEC = importlib.util.spec_from_file_location(
    "retained_http_verifier", ROOT / "diagnostics/issue45-runtime/verify_http_artifacts.py")
HTTP = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(HTTP)


def require(condition, message):
    if not condition:
        raise ValueError(message)


def validate_provenance(record, expected, label):
    # JSON comparison also distinguishes booleans from integers (True != 1 here).
    for field, value in expected.items():
        require(json.dumps(record.get(field), sort_keys=True) == json.dumps(value, sort_keys=True),
                label + " provenance differs: " + field)


def validate_plan(plan):
    validate_provenance(plan, PLAN_PROVENANCE, "plan")
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


def finding_identity(row):
    return (row["purl"], row["advisory"], row["severity"], row["fingerprint"],
            tuple(row["scopes"]), row["review_status"], row["failing"])


def retained_pilot_identities(raw):
    # Verify historical bytes offline without fetching Git history or invoking Git.
    blob = hashlib.sha1(b"blob " + str(len(raw)).encode("ascii") + b"\0" + raw).hexdigest()
    require(blob == FINDING_INDEX_BLOB, "retained finding index blob mismatch")
    index = json.loads(raw)
    report = index["reports"]["candidate|1.19.3"]
    require(index["schema"] == 1 and index["risk_acceptance"] is False
            and report["source_sha"] == PILOT_SOURCE and report["failing"] is True
            and report["resolved_needing_review"] == [], "retained pilot report scope changed")
    rows = [row for row in index["records"]
            if row["source_kind"] == "candidate" and row["group"] == "1.19.3"]
    require(len(rows) == len({(row["purl"], row["advisory"]) for row in rows}) == 24
            and all(row["source_sha"] == PILOT_SOURCE and row["report"] == report["report"]
                    and row["report_sha256_uncompressed"] == report["sha256_uncompressed"]
                    for row in rows), "retained pilot source or coverage changed")
    return {finding_identity(row) for row in rows}


def validate_pilot(pilot):
    require(pilot["schema"] == "issue45-pr22-review-preparation/v1"
            and pilot["scope"] == "unreviewed_comparison_only"
            and pilot["pr"] == 22 and pilot["runtime"] == "1.19.3"
            and pilot["source_sha"] == PILOT_SOURCE
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
    require({finding_identity(row) for row in rows} ==
            retained_pilot_identities(FINDING_INDEX.read_bytes()),
            "pilot advisory identities differ from retained index")
    require(pilot["sbom"]["all_branch_coverage_established"] is False
            and pilot["sbom"]["alerts_verified"] is False, "unverified monitoring claim")
    validate_provenance(pilot, PILOT_PROVENANCE, "pilot")
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

    def test_pilot_substituted_identity_or_fingerprint_rejected(self):
        for field, value in (("advisory", "GHSA-0000-0000-0000"),
                             ("purl", "pkg:maven/com.google.guava/guava@31.0-jre"),
                             ("fingerprint", "0" * 64)):
            with self.subTest(field=field):
                pilot = copy.deepcopy(self.pilot)
                pilot["findings"][0][field] = value
                with self.assertRaisesRegex(ValueError, "advisory identities differ"):
                    validate_pilot(pilot)

    def test_pilot_swapped_severity_or_fingerprint_rejected(self):
        for order in ("original", "reversed", "high_first"):
            for field in ("severity", "fingerprint"):
                with self.subTest(order=order, field=field):
                    pilot = copy.deepcopy(self.pilot)
                    rows = pilot["findings"]
                    if order == "reversed":
                        rows.reverse()
                    elif order == "high_first":
                        rows.sort(key=lambda row: row["severity"] != "HIGH")
                        # Reproduce the old test's no-op severity swap.
                        self.assertEqual([row["severity"] for row in rows[:2]], ["HIGH", "HIGH"])
                    self.assertEqual(validate_pilot(pilot), 24)
                    a = rows[0]
                    b = next((row for row in rows[1:] if row[field] != a[field]), None)
                    self.assertIsNotNone(b, "mutation requires two distinct field values")
                    before = Counter(row[field] for row in rows)
                    a[field], b[field] = b[field], a[field]
                    self.assertEqual(Counter(row[field] for row in rows), before)
                    with self.assertRaisesRegex(ValueError, "advisory identities differ"):
                        validate_pilot(pilot)

    def test_pilot_reordered_findings_pass(self):
        pilot = copy.deepcopy(self.pilot)
        pilot["findings"].reverse()
        self.assertEqual(validate_pilot(pilot), 24)

    def test_retained_index_changed_bytes_rejected(self):
        raw = FINDING_INDEX.read_bytes()
        with self.assertRaisesRegex(ValueError, "retained finding index blob mismatch"):
            retained_pilot_identities(raw + b" ")

    def test_pilot_provenance_mutations_rejected(self):
        cases = [
            (("base_sha",), "malformed"),
            (("base_sha",), "0" * 40),
            (("coordinator_checkout",), "0" * 40),
            (("local_scan", "retained_snapshot_sha256"), "0" * 64),
            (("local_scan", "date"), "2026-11-26"),
            (("hosted_scan", "run_id"), 1),
            (("hosted_scan", "artifact_id"), True),
            (("hosted_scan", "job_id"), 0),
            (("hosted_scan", "snapshot_artifact_id"), 1),
            (("comparison", "disappeared_matches"), 1),
            (("comparison", "disappeared_matches"), False),
            (("comparison", "normalized_tuples_equal"), 1),
            (("comparison", "hosted_local_inventories_equal"), False),
            (("comparison", "hosted_local_advisory_fingerprints_equal"), False),
            (("sbom", "packages"), 94),
        ]
        for field in ("zip_sha256", "report_sha256", "snapshot_zip_sha256", "snapshot_json_sha256"):
            cases.extend((("hosted_scan", field), value) for value in ("bad", "0" * 64))
        for field in PILOT_PROVENANCE["inputs_sha256"]:
            cases.extend((("inputs_sha256", field), value) for value in ("bad", "0" * 64))
        for path, value in cases:
            with self.subTest(path=path, value=value):
                pilot = copy.deepcopy(self.pilot)
                target = pilot
                for key in path[:-1]:
                    target = target[key]
                target[path[-1]] = value
                with self.assertRaisesRegex(ValueError, "pilot provenance differs"):
                    validate_pilot(pilot)

    def test_plan_and_pilot_matching_bad_digest_rejected(self):
        for digest in ("bad", "0" * 64):
            with self.subTest(digest=digest):
                plan, pilot = copy.deepcopy(self.plan), copy.deepcopy(self.pilot)
                plan["proposal_source_sha256"] = digest
                pilot["inputs_sha256"]["spdy-observation-plan.md"] = digest
                with self.assertRaisesRegex(ValueError, "plan provenance differs"):
                    validate_plan(plan)
                with self.assertRaisesRegex(ValueError, "pilot provenance differs"):
                    validate_pilot(pilot)

    def test_plan_metadata_mutations_rejected(self):
        for field, value in (("coordinator_checkout", "0" * 40),
                             ("proposal_date", "2026-11-26")):
            with self.subTest(field=field):
                plan = dict(self.plan, **{field: value})
                with self.assertRaisesRegex(ValueError, "plan provenance differs"):
                    validate_plan(plan)

    def test_provenance_missing_or_extra_fields_rejected(self):
        for field in ("inputs_sha256", "hosted_scan", "comparison"):
            with self.subTest(field=field):
                pilot = copy.deepcopy(self.pilot)
                pilot[field].pop(next(iter(pilot[field])))
                with self.assertRaisesRegex(ValueError, "pilot provenance differs"):
                    validate_pilot(pilot)
                pilot = copy.deepcopy(self.pilot)
                pilot[field]["unexpected"] = True
                with self.assertRaisesRegex(ValueError, "pilot provenance differs"):
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
