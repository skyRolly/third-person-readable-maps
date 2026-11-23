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
# Independent source-code trust anchor: never derive this from the mutable v1
# file or a regenerated v2 report.
HISTORICAL_V1_SHA256 = "8312b41b86992cb3dc6aff10f8d01184248abe9cadaf58b754967f157962ee09"


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


def validate_compatibility_erratum(
        report: dict, register: dict, matrix: dict | None = None,
        pinned_versions: dict[str, str] | None = None,
        archive_v1_path: Path | None = None) -> list[str]:
    """Bind the derived v2 report to actual archive v1 bytes and the pinned game matrix.

    The physical archive's v1 path is separate from its canonical repository
    provenance path. In the normal archive validator, pinned_versions comes from
    individually source-verified client manifests or server bundles.
    """
    errors: list[str] = []
    try:
        indexed = fixed_boundaries(register)
    except ValueError as error:
        return [str(error)]
    focused = [row for row in indexed if row["focused_evidence"]]
    unfocused = [row for row in indexed if not row["focused_evidence"]]
    indexed_maxima = maximum_fixed_boundaries(indexed)
    focused_maxima = maximum_fixed_boundaries(focused)
    expected = {
        "indexed_netty_advisories": indexed, "focused_netty_advisories": focused,
        "unfocused_netty_advisories": unfocused,
        "indexed_netty_advisory_count": len(indexed),
        "focused_netty_advisory_count": len(focused),
        "unfocused_netty_advisory_count": len(unfocused),
        "minimum_versions_covering_all_indexed_netty_advisories": indexed_maxima,
        "minimum_versions_covering_focused_netty_advisories": focused_maxima,
    }
    if report.get("schema") != "issue45-netty-remediation-compatibility/v2":
        errors.append("corrected Netty compatibility schema mismatch")
    for key, value in expected.items():
        if report.get(key) != value:
            errors.append("Netty compatibility focus or fixed-boundary mismatch: " + key)
    if report.get("source_register") != {
            "path": REGISTER.relative_to(ROOT).as_posix(), "sha256": digest(REGISTER)}:
        errors.append("corrected Netty report is not bound to the retained source register")

    lz4 = [row for row in indexed if row["advisory_id"] == "GHSA-mj4r-2hfc-f8p6"]
    if len(lz4) != 1:
        errors.append("source register lacks the exact LZ4 advisory")
        return errors
    lz4_min = maximum_fixed_boundaries(lz4)
    if report.get("minimum_versions_for_lz4_advisory_only") != lz4_min:
        errors.append("LZ4 fixed boundaries do not match the source register")

    historical = OUT / "remediation-compatibility.json"
    physical_v1 = archive_v1_path if archive_v1_path is not None else historical
    expected_v1_sha = HISTORICAL_V1_SHA256
    if not historical.is_file() or digest(historical) != expected_v1_sha:
        errors.append("source-controlled historical Netty v1 digest mismatch")
    if report.get("historical_v1_report") != {
            "path": historical.relative_to(ROOT).as_posix(), "sha256": expected_v1_sha,
            "status": "preserved_with_classification_erratum"}:
        errors.append("Netty v1 historical report source provenance mismatch")
    if not physical_v1.is_file() or digest(physical_v1) != expected_v1_sha:
        errors.append("archived Netty v1 historical report SHA-256 differs from the retained report")

    if matrix is None:
        matrix = json.loads((OUT / "environment-matrix.json").read_text(encoding="utf-8"))
    matrix_rows = matrix.get("environments")
    report_rows = report.get("environments")
    if not isinstance(matrix_rows, list) or not matrix_rows or not all(
            isinstance(row, dict) for row in matrix_rows):
        errors.append("Netty source matrix is missing valid environment rows")
        return errors
    if not isinstance(report_rows, list) or not report_rows or not all(
            isinstance(row, dict) for row in report_rows):
        errors.append("corrected Netty report lacks its complete environment matrix")
        return errors
    matrix_ids = [row.get("environment_id") for row in matrix_rows]
    report_ids = [row.get("environment_id") for row in report_rows]
    if (any(not isinstance(identity, str) or not identity.strip()
            for identity in matrix_ids + report_ids)
            or len(matrix_ids) != len(set(identity for identity in matrix_ids
                                          if isinstance(identity, str)))
            or len(report_ids) != len(set(identity for identity in report_ids
                                          if isinstance(identity, str)))
            or set(identity for identity in matrix_ids if isinstance(identity, str))
            != set(identity for identity in report_ids if isinstance(identity, str))):
        errors.append("corrected Netty environment identities are missing, duplicated or unexpected")
        return errors

    matrix_by_id = {row["environment_id"]: row for row in matrix_rows}
    if pinned_versions is None:
        # Direct unit validation uses the retained source-bound environment
        # matrix; full archive validation *must* pass verified artifact pins.
        pinned_versions = {
            row["environment_id"]: row.get("expected_netty_codec")
            or row.get("expected_bundled_netty_codec") for row in matrix_rows}
    if set(pinned_versions) != set(matrix_ids):
        errors.append("verified Netty artifact pins do not cover every environment")
        return errors

    for row in report_rows:
        identity = row["environment_id"]
        source = matrix_by_id[identity]
        selected = pinned_versions.get(identity)
        expected_version = (source.get("expected_netty_codec")
                            or source.get("expected_bundled_netty_codec"))
        if not isinstance(selected, str) or not selected or selected != expected_version:
            errors.append("source matrix Netty version differs from the independently verified artifact pin: "
                          + identity)
            continue
        family = "4.1" if selected.startswith("4.1.") else "4.2" if selected.startswith("4.2.") else None
        if family is None:
            errors.append("unsupported pinned Netty version family: " + identity)
            continue
        for field, value in (("minecraft_version", source.get("minecraft_version")),
                             ("distribution", source.get("distribution")),
                             ("manifest_or_bundle_netty_version", selected),
                             ("expected_dependency_family", family)):
            if row.get(field) != value:
                errors.append("corrected Netty environment does not match pinned matrix: "
                              + identity + ":" + field)
        expected_flags = {
            "lz4_advisory_fixed_boundary_met_by_selected_artifact_version":
                version_key(selected) >= version_key(lz4_min[family]),
            "all_indexed_netty_boundaries_met":
                version_key(selected) >= version_key(indexed_maxima[family]),
            "focused_netty_boundaries_met":
                version_key(selected) >= version_key(focused_maxima[family]),
        }
        for field, value in expected_flags.items():
            if row.get(field) is not value:
                errors.append("incorrect " + field + " for pinned Netty environment: " + identity)
        source_kind = ("module_family_consistent_at_source_bundle" if source["distribution"] == "server"
                       else "module_family_consistent_at_source_manifest")
        if row.get(source_kind) is not True:
            errors.append("corrected Netty environment module family is not source-consistent: " + identity)
        if (row.get("runtime_loader_selection_verified") is not False
                or row.get("minecraft_fabric_abi_verified") is not False
                or row.get("supported_jvm_execution_verified") is not False
                or row.get("no_dependency_override_performed") is not True
                or row.get("outcome") != "minecraft-managed dependency blocker"):
            errors.append("corrected Netty environment overstates runtime or remediation: " + identity)
    # The separately rendered server summaries are assertions too: a "live
    # selection verified" claim must not bypass the checked environment rows.
    for identity, summary_key, artifact_key in (
            ("minecraft-1.19-dedicated-server", "minecraft_1_19_server_bundle", "netty_codec_artifact"),
            ("minecraft-26.1.2-dedicated-server", "minecraft_26_1_2_server_bundle", "lz4_module_artifact")):
        source = matrix_by_id.get(identity, {})
        summary = report.get(summary_key)
        pinned = pinned_versions.get(identity)
        if not isinstance(summary, dict):
            errors.append("Netty source-bound server summary is absent: " + identity)
            continue
        official_artifact = source.get("server_bundle_source", {}).get("nested_netty_artifact", {})
        if (summary.get("live_selection_verified") is not False
                or summary.get("module_family_consistent") is not True
                or summary.get("server_bundle_sha256") != source.get("server_bundle_sha256")
                or summary.get("netty_module_versions") != [pinned]
                or not isinstance(summary.get(artifact_key), dict)
                or any(summary[artifact_key].get(field) != official_artifact.get(field)
                       for field in ("path", "sha1", "sha256", "size_bytes"))):
            errors.append("Netty server bundle summary contradicts verified source and runtime rows: " + identity)

    return errors


def versions_from_manifest(path: Path) -> dict:
    manifest = json.loads(path.read_text(encoding="utf-8"))
    modules = [item["name"] for item in manifest.get("libraries", [])
               if item.get("name", "").startswith("io.netty:")]
    versions = sorted(set(name.split(":")[2] for name in modules))
    if len(versions) != 1:
        raise SystemExit("retained manifest has inconsistent Netty module versions: " + str(path))
    return {"minecraft_version": manifest["id"], "manifest_path": path.relative_to(ROOT).as_posix(),
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
    if not historical.is_file() or digest(historical) != HISTORICAL_V1_SHA256:
        raise SystemExit("immutable historical compatibility report SHA-256 mismatch; refusing regeneration")
    data = {
        "schema": "issue45-netty-remediation-compatibility/v2",
        "observed_at_utc": datetime.now(timezone.utc).isoformat(),
        "historical_v1_report": {
            "path": historical.relative_to(ROOT).as_posix(), "sha256": digest(historical),
            "status": "preserved_with_classification_erratum"},
        "source_register": {"path": REGISTER.relative_to(ROOT).as_posix(), "sha256": digest(REGISTER)},
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
