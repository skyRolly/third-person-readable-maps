#!/usr/bin/env python3
"""Derive Netty version-family compatibility gates from retained source-bound records."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / "docs/dependency-evidence/issue45-netty-lz4-high-2026-11-23"
OUT = ROOT / "docs/dependency-evidence/issue45-runtime-pipeline-2026-11-23"
REGISTER = BASE / "priority-register-v6.json"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def version_key(value: str) -> tuple[int, ...]:
    match = re.match(r"^(\d+)\.(\d+)\.(\d+)", value)
    if not match:
        return (0, 0, 0)
    return tuple(int(part) for part in match.groups())


def fixed_boundaries(register: dict) -> list[dict]:
    result = []
    seen = set()
    for advisory in register.get("advisories", []):
        if advisory.get("advisory_id") in seen:
            raise ValueError("duplicate advisory identity in compatibility register")
        seen.add(advisory.get("advisory_id"))
        boundaries = {"4.1": set(), "4.2": set()}
        for purl, groups in advisory.get("affected_ranges", {}).items():
            if not purl.startswith("pkg:maven/io.netty/"):
                continue
            for range_group in groups:
                for item in range_group:
                    for event in item.get("events", []):
                        fixed = event.get("fixed", "")
                        if fixed.startswith("4.1."):
                            boundaries["4.1"].add(fixed)
                        elif fixed.startswith("4.2."):
                            boundaries["4.2"].add(fixed)
        if boundaries["4.1"] or boundaries["4.2"]:
            result.append({"advisory_id": advisory["advisory_id"],
                           "aliases": advisory.get("aliases", []),
                           "focused_evidence": advisory.get("focused_evidence") is not None,
                           "fixed_4_1": sorted(boundaries["4.1"], key=version_key),
                           "fixed_4_2": sorted(boundaries["4.2"], key=version_key)})
    return result


def maximum_fixed_boundaries(rows: list[dict]) -> dict[str, str]:
    result = {}
    for family, field in (("4.1", "fixed_4_1"), ("4.2", "fixed_4_2")):
        versions = [version for row in rows for version in row[field]]
        if not versions:
            raise ValueError("missing Netty " + family + " fixed boundaries")
        result[family] = max(versions, key=version_key)
    return result


def validate_compatibility_erratum(report: dict, register: dict) -> list[str]:
    """Compare all advisory IDs, focus classifications, and maxima to pinned inputs."""
    errors: list[str] = []
    try:
        indexed = fixed_boundaries(register)
    except ValueError as error:
        return [str(error)]
    focused = [row for row in indexed if row["focused_evidence"]]
    unfocused = [row for row in indexed if not row["focused_evidence"]]
    expected = {
        "indexed_netty_advisories": indexed, "focused_netty_advisories": focused,
        "unfocused_netty_advisories": unfocused,
        "indexed_netty_advisory_count": len(indexed),
        "focused_netty_advisory_count": len(focused),
        "unfocused_netty_advisory_count": len(unfocused),
        "minimum_versions_covering_all_indexed_netty_advisories": maximum_fixed_boundaries(indexed),
        "minimum_versions_covering_focused_netty_advisories": maximum_fixed_boundaries(focused),
    }
    if report.get("schema") != "issue45-netty-remediation-compatibility/v2":
        errors.append("corrected Netty compatibility schema mismatch")
    for key, value in expected.items():
        if report.get(key) != value:
            errors.append("Netty compatibility focus or fixed-boundary mismatch: " + key)
    if report.get("source_register") != {
            "path": str(REGISTER.relative_to(ROOT)), "sha256": digest(REGISTER)}:
        errors.append("corrected Netty report is not bound to the retained source register")
    historic = OUT / "remediation-compatibility.json"
    if report.get("historical_v1_report") != {
            "path": str(historic.relative_to(ROOT)), "sha256": digest(historic),
            "status": "preserved_with_classification_erratum"}:
        errors.append("Netty v1 historical report is missing or has changed")
    for row in report.get("environments", []):
        version, family = row.get("manifest_or_bundle_netty_version", ""), row.get("expected_dependency_family")
        if family not in ("4.1", "4.2"):
            errors.append("invalid Netty environment family in corrected compatibility")
            continue
        if row.get("all_indexed_netty_boundaries_met") != (
                version_key(version) >= version_key(expected[
                    "minimum_versions_covering_all_indexed_netty_advisories"][family])):
            errors.append("incorrect indexed-Netty boundary environment classification")
        if row.get("focused_netty_boundaries_met") != (
                version_key(version) >= version_key(expected[
                    "minimum_versions_covering_focused_netty_advisories"][family])):
            errors.append("incorrect focused-Netty boundary environment classification")
        if (row.get("runtime_loader_selection_verified") is not False
                or row.get("minecraft_fabric_abi_verified") is not False
                or row.get("no_dependency_override_performed") is not True):
            errors.append("corrected compatibility report overstates runtime or remediation")
    return errors


def versions_from_manifest(path: Path) -> dict:
    manifest = json.loads(path.read_text(encoding="utf-8"))
    modules = [item["name"] for item in manifest.get("libraries", [])
               if item.get("name", "").startswith("io.netty:")]
    versions = sorted(set(name.split(":")[2] for name in modules))
    if len(versions) != 1:
        raise SystemExit("retained manifest has inconsistent Netty module versions: " + str(path))
    return {"minecraft_version": manifest["id"], "manifest_path": str(path.relative_to(ROOT)),
            "manifest_sha256": digest(path), "netty_versions": versions,
            "netty_coordinates": sorted(modules), "module_family_consistent": True,
            "java_major_required": manifest.get("javaVersion", {}).get("majorVersion")}


def main() -> int:
    register = json.loads(REGISTER.read_text(encoding="utf-8"))
    boundaries = fixed_boundaries(register)
    focused = [item for item in boundaries if item["focused_evidence"]]
    unfocused = [item for item in boundaries if not item["focused_evidence"]]
    if (len(boundaries), len(focused), len(unfocused)) != (15, 7, 8):
        raise SystemExit("retained Netty indexed/focused/unfocused advisory sets changed; review required")
    max_41 = max((v for item in boundaries for v in item["fixed_4_1"]), key=version_key)
    max_42 = max((v for item in boundaries for v in item["fixed_4_2"]), key=version_key)
    focused_max_41 = max((v for item in focused for v in item["fixed_4_1"]), key=version_key)
    focused_max_42 = max((v for item in focused for v in item["fixed_4_2"]), key=version_key)
    if (max_41, max_42, focused_max_41, focused_max_42) != (
            "4.1.137.Final", "4.2.17.Final", "4.1.137.Final", "4.2.17.Final"):
        raise SystemExit("Netty indexed or focused fixed boundaries changed; review required")
    lz4 = next(item for item in boundaries if item["advisory_id"] == "GHSA-mj4r-2hfc-f8p6")
    lz4_min = {"4.1": "4.1.133.Final", "4.2": "4.2.13.Final"}

    versions = {v: versions_from_manifest(BASE / "minecraft-version-manifests" / (v + ".json"))
                for v in ("1.19", "1.21.11", "26.1.2", "26.2")}
    server = json.loads((BASE / "dedicated-server-scan.json").read_text(encoding="utf-8"))
    server_119 = next(item for item in server["servers"] if item["minecraft_version"] == "1.19")
    server_netty = [item for item in server_119["nested_jars"]
                    if item["path"].startswith("META-INF/libraries/io/netty/")]
    server_versions = sorted(set(item["path"].split("/")[5] for item in server_netty))
    if server_versions != ["4.1.76.Final"]:
        raise SystemExit("retained 1.19 server Netty module family unexpectedly differs")
    server_2612 = next(item for item in server["servers"] if item["minecraft_version"] == "26.1.2")
    server_2612_netty = [item for item in server_2612["nested_jars"]
                         if item["path"].startswith("META-INF/libraries/io/netty/")]
    server_2612_versions = sorted(set(item["path"].split("/")[5] for item in server_2612_netty))
    if server_2612_versions != ["4.2.7.Final"]:
        raise SystemExit("retained 26.1.2 server Netty module family unexpectedly differs")

    rows = []
    matrix = json.loads((OUT / "environment-matrix.json").read_text(encoding="utf-8"))
    for environment in matrix["environments"]:
        version = environment.get("expected_netty_codec") or environment.get("expected_bundled_netty_codec")
        if not version and environment["minecraft_version"] != "1.19":
            version = versions[environment["minecraft_version"]]["netty_versions"][0]
        version = version or "4.1.76.Final"
        family = "4.1" if version.startswith("4.1.") else "4.2"
        lz4_fixed = version_key(version) >= version_key(lz4_min[family])
        all_indexed_fixed = version_key(version) >= version_key(max_41 if family == "4.1" else max_42)
        focused_fixed = version_key(version) >= version_key(
            focused_max_41 if family == "4.1" else focused_max_42)
        row = {
            "environment_id": environment["environment_id"],
            "minecraft_version": environment["minecraft_version"],
            "distribution": environment["distribution"],
            "expected_dependency_family": family,
            "manifest_or_bundle_netty_version": version,
            ("module_family_consistent_at_source_bundle" if environment["distribution"] == "server"
             else "module_family_consistent_at_source_manifest"): True,
            "lz4_advisory_fixed_boundary_met_by_selected_artifact_version": lz4_fixed,
            "all_indexed_netty_boundaries_met": all_indexed_fixed,
            "focused_netty_boundaries_met": focused_fixed,
            "runtime_loader_selection_verified": False,
            "minecraft_fabric_abi_verified": False,
            "supported_jvm_execution_verified": False,
            "outcome": "minecraft-managed dependency blocker",
            "reason": ("The official artifact version is below the maximum fixed boundary for 15 indexed Netty advisories; "
                       "no substitution is supported by game/Fabric ABI validation."),
            "no_dependency_override_performed": True
        }
        if environment["minecraft_version"] == "26.2":
            row["reason"] = ("4.2.15.Final meets this LZ4 advisory's 4.2.13.Final boundary, but remains below 4.2.17.Final, "
                             "the maximum fixed boundary across 15 indexed Netty advisories (7 focused). Runtime selection and ABI remain unverified.")
        rows.append(row)

    historical = OUT / "remediation-compatibility.json"
    if not historical.is_file():
        raise SystemExit("immutable historical compatibility report is missing")
    data = {
        "schema": "issue45-netty-remediation-compatibility/v2",
        "observed_at_utc": datetime.now(timezone.utc).isoformat(),
        "historical_v1_report": {
            "path": str(historical.relative_to(ROOT)), "sha256": digest(historical),
            "status": "preserved_with_classification_erratum"},
        "source_register": {"path": str(REGISTER.relative_to(ROOT)), "sha256": digest(REGISTER)},
        "scope": "source-bound classification erratum; fixed boundaries do not prove focused investigation or runtime compatibility",
        "indexed_netty_advisory_count": len(boundaries),
        "indexed_netty_advisories": boundaries,
        "focused_netty_advisory_count": len(focused),
        "focused_netty_advisories": focused,
        "unfocused_netty_advisory_count": len(unfocused),
        "unfocused_netty_advisories": unfocused,
        "minimum_versions_for_lz4_advisory_only": lz4_min,
        "minimum_versions_covering_all_indexed_netty_advisories": {"4.1": max_41, "4.2": max_42},
        "minimum_versions_covering_focused_netty_advisories": {
            "4.1": focused_max_41, "4.2": focused_max_42},
        "maximum_boundary_advisory": "GHSA-c4c3-7fpv-j4q5",
        "manifest_module_families": versions,
        "minecraft_1_19_server_bundle": {
            "server_bundle_sha256": server_119["server_sha256"],
            "netty_jar_count": len(server_netty), "netty_module_versions": server_versions,
            "netty_codec_artifact": next(item for item in server_netty
                                          if item["path"].endswith("/netty-codec-4.1.76.Final.jar")),
            "module_family_consistent": True, "live_selection_verified": False
        },
        "minecraft_26_1_2_server_bundle": {
            "server_bundle_sha256": server_2612["server_sha256"],
            "netty_jar_count": len(server_2612_netty), "netty_module_versions": server_2612_versions,
            "lz4_module_artifact": next(item for item in server_2612_netty
                                         if item["path"].endswith("/netty-codec-compression-4.2.7.Final.jar")),
            "module_family_consistent": True, "live_selection_verified": False
        },
        "environments": rows,
        "fixed_candidate_synthetic_controls": {
            "netty_4_1_137": "recorder and synthetic EmbeddedChannel channel-creation, active-snapshot, add/remove hooks passed on Java 21",
            "netty_4_2_17": "recorder and synthetic EmbeddedChannel channel-creation, active-snapshot, add/remove hooks passed on Java 21",
            "scope_limit": "No Minecraft/Fabric classes or networking ABI were exercised; these are component/diagnostic compatibility controls only."
        },
        "jvm_compatibility": {
            "tested_java_runtime": "21.0.12.1",
            "java_17_supported_game_line_compatibility": "not tested by a Minecraft launch",
            "java_21_fabric_client_compatibility": "not tested by a Minecraft launch",
            "java_25_minecraft_26_compatibility": "not tested; synthetic tests on Java 21 do not establish Java 25 runtime behavior",
            "class_file_level_alone_sufficient": False
        },
        "decision": "No upstream substitution is verified compatible for a supported Minecraft/Fabric environment. 4.2.15.Final clears only the LZ4 fixed boundary, not all focused Netty issues. Keep Minecraft-managed dependency blockers open and test an officially selected update in its exact game/loader runtime."
    }
    destination = OUT / "remediation-compatibility-v2.json"
    destination.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"result": "pass", "indexed_netty_advisories": len(boundaries), "focused_netty_advisories": len(focused), "unfocused_netty_advisories": len(unfocused),
                      "minimum_4_1": max_41, "minimum_4_2": max_42,
                      "environments": len(rows), "runtime_compatibility_verified": False}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
