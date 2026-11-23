#!/usr/bin/env python3
"""Revalidate only the official 1.19 manifest, client Netty codec, and bundled server codec."""

from __future__ import annotations

import hashlib
import json
import urllib.request
import zipfile
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
STATIC = ROOT / "docs/dependency-evidence/issue45-netty-lz4-high-2026-11-23"
OUT = ROOT / "docs/dependency-evidence/issue45-runtime-pipeline-2026-11-23"


def fetch(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": "issue45-runtime-revalidation/1"})
    with urllib.request.urlopen(request, timeout=90) as response:
        return response.read()


def hashes(data: bytes) -> dict[str, object]:
    return {"size_bytes": len(data), "sha1": hashlib.sha1(data).hexdigest(),
            "sha256": hashlib.sha256(data).hexdigest()}


def main() -> int:
    static_review = json.loads((STATIC / "source-bound-review.json").read_text(encoding="utf-8"))
    retained_manifest = STATIC / static_review["minecraft_manifest_identities"]["1.19"]["path"].split("/", 4)[-1]
    # Resolve from the repository because the evidence path is source-bound in the retained review.
    retained_manifest = ROOT / static_review["minecraft_manifest_identities"]["1.19"]["path"]
    manifest_expected = static_review["minecraft_manifest_identities"]["1.19"]
    retained_bytes = retained_manifest.read_bytes()
    if hashlib.sha1(retained_bytes).hexdigest() != manifest_expected["sha1"]:
        raise SystemExit("retained 1.19 manifest SHA-1 does not match the source-bound review")
    if hashlib.sha256(retained_bytes).hexdigest() != manifest_expected["sha256"]:
        raise SystemExit("retained 1.19 manifest SHA-256 does not match the source-bound review")

    version_index_url = "https://piston-meta.mojang.com/mc/game/version_manifest_v2.json"
    version_index_bytes = fetch(version_index_url)
    version_index = json.loads(version_index_bytes)
    entries = [item for item in version_index["versions"] if item["id"] == "1.19"]
    if len(entries) != 1:
        raise SystemExit("official Mojang index did not identify exactly one Minecraft 1.19 entry")
    version_entry = entries[0]
    official_manifest_bytes = fetch(version_entry["url"])
    official_manifest_hashes = hashes(official_manifest_bytes)
    if official_manifest_hashes["sha1"] != version_entry["sha1"]:
        raise SystemExit("official 1.19 manifest failed the Mojang index SHA-1")
    if official_manifest_bytes != retained_bytes:
        raise SystemExit("retained 1.19 manifest differs from exact official manifest bytes")
    manifest = json.loads(official_manifest_bytes)
    client_artifact = next(item for item in manifest["libraries"]
                           if item["name"] == "io.netty:netty-codec:4.1.77.Final")["downloads"]["artifact"]
    client_bytes = fetch(client_artifact["url"])
    client_hashes = hashes(client_bytes)
    if client_hashes["sha1"] != client_artifact["sha1"] or client_hashes["size_bytes"] != client_artifact["size"]:
        raise SystemExit("official 1.19 client netty-codec artifact failed Mojang artifact metadata")

    server_info = static_review["server_occurrence_difference"]
    server_url = "https://piston-data.mojang.com/v1/objects/" + server_info["server_sha1"] + "/server.jar"
    server_bytes = fetch(server_url)
    server_hashes = hashes(server_bytes)
    if server_hashes["sha1"] != server_info["server_sha1"] or server_hashes["sha256"] != server_info["server_sha256"]:
        raise SystemExit("official Minecraft 1.19 server bundle digest mismatch")
    nested_path = server_info["netty_codec_artifact"]["path"]
    import io
    with zipfile.ZipFile(io.BytesIO(server_bytes)) as bundle:
        nested_bytes = bundle.read(nested_path)
    nested_hashes = hashes(nested_bytes)
    if nested_hashes["sha1"] != server_info["netty_codec_artifact"]["sha1"]:
        raise SystemExit("nested server netty-codec SHA-1 mismatch")
    if nested_hashes["sha256"] != server_info["netty_codec_artifact"]["sha256"]:
        raise SystemExit("nested server netty-codec SHA-256 mismatch")

    result = {
        "schema": "issue45-mc119-artifact-revalidation/v1",
        "observed_at_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "targeted_official_artifact_revalidation_only_no_class_scan_or_process_launch",
        "official_version_index": {"url": version_index_url, "sha256": hashlib.sha256(version_index_bytes).hexdigest()},
        "version_manifest": {"minecraft_version": "1.19", "url": version_entry["url"],
                             "official_index_sha1": version_entry["sha1"],
                             "official_bytes": official_manifest_hashes,
                             "retained_source_bound_sha1": manifest_expected["sha1"],
                             "retained_source_bound_sha256": manifest_expected["sha256"],
                             "exact_byte_match": True},
        "client_netty_codec": {"coordinate": client_artifact["path"], "url": client_artifact["url"],
                               "official_manifest_sha1": client_artifact["sha1"],
                               "official_manifest_size": client_artifact["size"], "observed": client_hashes,
                               "package_version": "4.1.77.Final"},
        "server_bundle": {"url": server_url, "observed": server_hashes,
                          "retained_server_sha1": server_info["server_sha1"],
                          "retained_server_sha256": server_info["server_sha256"]},
        "server_nested_netty_codec": {"path": nested_path, "observed": nested_hashes,
                                       "retained_sha1": server_info["netty_codec_artifact"]["sha1"],
                                       "retained_sha256": server_info["netty_codec_artifact"]["sha256"],
                                       "package_version": "4.1.76.Final"},
        "classification": {
            "official_artifact_dependency_divergence": "confirmed_at_official_client_manifest_and_server_bundle_level",
            "historical_audit_scope": "confirmed_outside_exact_12_occurrence_index; do_not_merge_counts",
            "server_process_runtime_selection": "unresolved_without_a_launched_official_server_process",
            "input_pipeline_reachability": "unresolved_without_live_pipeline_observation"
        },
        "limitations": ["No Minecraft process was launched.",
                        "The official bundled library is not proof that the launched JVM selected it.",
                        "No running class loader or channel pipeline was observed."]
    }
    OUT.mkdir(parents=True, exist_ok=True)
    target = OUT / "minecraft-1.19-official-artifact-revalidation.json"
    target.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"result": "pass", "report": str(target.relative_to(ROOT)),
                      "client_codec_sha256": client_hashes["sha256"],
                      "server_codec_sha256": nested_hashes["sha256"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
