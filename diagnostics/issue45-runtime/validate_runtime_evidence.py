#!/usr/bin/env python3
"""Validate Issue 45 runtime observations without converting missing runs into passes."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

HEX40 = re.compile(r"^[0-9a-f]{40}$")
HEX64 = re.compile(r"^[0-9a-f]{64}$")
SCHEMA = "issue45-runtime-observation/v1"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def validate_environment_artifact_pin(environment: dict, source_root: Path,
                                     retained_files: dict) -> tuple[list[str], dict | None]:
    errors: list[str] = []
    version = environment.get("expected_netty_codec") or environment.get("expected_bundled_netty_codec")
    module = environment.get("expected_bundled_netty_module")
    if not module:
        module = "netty-codec" if str(version).startswith("4.1.") else "netty-codec-compression"
    if environment.get("distribution") == "server":
        record = environment.get("server_bundle_source", {})
        scan_path = record.get("source_scan_path", "")
        expected_scan_sha = retained_files.get(scan_path)
        if (not scan_path or not expected_scan_sha or record.get("source_scan_sha256") != expected_scan_sha):
            return ["dedicated-server artifact pin is not bound to the retained source scan"], None
        path = source_root / scan_path
        if not path.is_file() or sha256(path) != expected_scan_sha:
            return ["retained dedicated-server source scan is missing or changed"], None
        try:
            scan = load_json(path)
            server = next(item for item in scan["servers"]
                          if item.get("minecraft_version") == environment.get("minecraft_version"))
            artifact = record["nested_netty_artifact"]
            actual = next(item for item in server["nested_jars"] if item.get("path") == artifact.get("path"))
            if (record.get("manifest_sha1") != server.get("manifest_sha1")
                    or record.get("server_bundle_sha1") != server.get("server_sha1")
                    or record.get("server_bundle_sha256") != server.get("server_sha256")
                    or record.get("server_bundle_size_bytes") != server.get("server_size_bytes")
                    or environment.get("server_bundle_sha256") != server.get("server_sha256")):
                errors.append("dedicated-server bundle identity differs from the retained official scan")
            for key in ("sha1", "sha256", "size_bytes", "path"):
                if artifact.get(key) != actual.get(key):
                    errors.append("dedicated-server Netty artifact " + key + " differs from the retained scan")
            coordinate = "io.netty:" + module + ":" + str(version)
            if (artifact.get("coordinate") != coordinate
                    or not artifact.get("path", "").endswith("/" + module + "-" + str(version) + ".jar")):
                errors.append("dedicated-server Netty module coordinate does not match its pinned version")
            return errors, {**artifact, "coordinate": coordinate, "module": module}
        except (OSError, KeyError, StopIteration, json.JSONDecodeError) as error:
            return errors + ["dedicated-server artifact pin cannot be checked: " + str(error)], None

    manifest_name = environment.get("manifest_path")
    if not manifest_name:
        return ["client environment lacks its official Minecraft version manifest"], None
    manifest_path = source_root / manifest_name
    if not manifest_path.is_file() or sha256(manifest_path) != environment.get("manifest_sha256"):
        return ["client Netty source manifest is missing or has a digest mismatch"], None
    try:
        manifest = load_json(manifest_path)
        coordinate = "io.netty:" + module + ":" + str(version)
        library = next(item for item in manifest.get("libraries", []) if item.get("name") == coordinate)
        artifact = library["downloads"]["artifact"]
        if not HEX40.fullmatch(artifact.get("sha1", "")) or not artifact.get("size"):
            errors.append("official manifest Netty artifact lacks source checksum or size")
        return errors, {"coordinate": coordinate, "module": module,
                        "path": artifact.get("path", ""), "sha1": artifact.get("sha1", ""),
                        "size_bytes": artifact.get("size", 0)}
    except (OSError, KeyError, StopIteration, json.JSONDecodeError) as error:
        return errors + ["official manifest does not pin the expected Netty module: " + str(error)], None


def validate_runtime_artifact_identity(start: dict, end: dict, expected_artifact: dict) -> list[str]:
    basename = str(expected_artifact.get("path", "")).rsplit("/", 1)[-1]
    expected_sha1 = expected_artifact.get("sha1")
    expected_sha256 = expected_artifact.get("sha256")
    expected_size = expected_artifact.get("size_bytes")
    candidates = []
    candidates.extend(end.get("loaded_netty_artifacts", []))
    candidates.extend(end.get("loaded_code_source_groups", []))
    start_records = start.get("effective_classpath_sanitized", [])
    if isinstance(start_records, list):
        candidates.extend(start_records)
    matches = [item for item in candidates if isinstance(item, dict)
               and item.get("artifact") == basename and item.get("hash_verified") is True
               and item.get("sha1") == expected_sha1 and HEX64.fullmatch(item.get("sha256", ""))
               and (not expected_sha256 or item.get("sha256") == expected_sha256)
               and item.get("size_bytes") == expected_size]
    if not matches:
        return ["running process does not expose a classpath or loaded-code-source JAR matching the official Netty artifact pin"]
    return []


def validate_channel_assessments(end: dict, assessments: list[dict]) -> list[str]:
    errors: list[str] = []
    observed = end.get("connected_socket_channel_fingerprints", [])
    active = end.get("active_socket_channel_fingerprints", [])
    if (not isinstance(observed, list) or not observed
            or any(not isinstance(value, str) or not HEX64.fullmatch(value) for value in observed)):
        errors.append("connected socket channel fingerprints are missing or malformed")
        observed = []
    if (not isinstance(active, list)
            or any(not isinstance(value, str) or not HEX64.fullmatch(value) for value in active)
            or set(active) != set(observed)):
        errors.append("connected socket channels lack matching channel-active pipeline snapshots")
    if not isinstance(assessments, list):
        return errors + ["operator input-boundary assessments are missing"]
    if any(not isinstance(item, dict) for item in assessments):
        errors.append("operator input-boundary assessment must be an object")
        assessments = [item for item in assessments if isinstance(item, dict)]
    fingerprints = [item.get("channel_fingerprint") for item in assessments]
    valid_fingerprints = [value for value in fingerprints if isinstance(value, str)]
    if len(valid_fingerprints) != len(set(valid_fingerprints)):
        errors.append("operator input-boundary assessments contain duplicate channels")
    if set(valid_fingerprints) != set(observed):
        errors.append("operator input-boundary assessments do not cover exactly the observed socket channels")
    required_text = ("channel_role", "input_direction", "input_origin", "protocol_framing",
                     "authentication_phase", "per_channel_resource_limits",
                     "aggregate_resource_limits", "assessment_basis")
    for index, item in enumerate(assessments):
        fingerprint = item.get("channel_fingerprint")
        if not isinstance(fingerprint, str) or not HEX64.fullmatch(fingerprint):
            errors.append("operator input-boundary assessment has a malformed channel fingerprint")
        for field in required_text:
            value = item.get(field)
            if not isinstance(value, str) or not value.strip() or len(value) > 500:
                errors.append("operator input-boundary assessment lacks a concise " + field)
        if item.get("input_direction") not in ("inbound", "outbound", "bidirectional", "unknown"):
            errors.append("operator input direction must be explicit for channel assessment " + str(index))
        if item.get("input_origin") not in ("remote_peer", "local_process", "unknown"):
            errors.append("operator input origin must be explicit for channel assessment " + str(index))
        if item.get("authentication_phase") not in ("pre_authentication", "authenticated", "not_applicable", "unknown"):
            errors.append("operator authentication phase must be explicit for channel assessment " + str(index))
        if not isinstance(item.get("untrusted_remote_input"), bool):
            errors.append("operator must decide or explicitly qualify untrusted remote input for channel assessment "
                          + str(index))
        if item.get("untrusted_remote_input") is True and item.get("input_origin") != "remote_peer":
            errors.append("untrusted remote input requires remote_peer as the channel input origin")
        notes = " ".join(str(item.get(field, "")) for field in required_text)
        if re.search(r"(?i)(?:https?://|(?:\d{1,3}\.){3}\d{1,3}|@[A-Za-z0-9._-]+)", notes):
            errors.append("operator input-boundary notes must not contain addresses or account identifiers")
    return errors


def validate_run_events(events: list[dict], environment: dict, source_root: Path,
                        require_remote_pipeline: bool = True) -> list[str]:
    errors: list[str] = []
    if not events:
        return ["observation file is empty"]
    if any(not isinstance(item, dict) for item in events):
        return ["observation events must be JSON objects"]
    if any(item.get("schema") != SCHEMA for item in events):
        errors.append("observation has an unknown or missing schema")
    run_ids = {item.get("run_id") for item in events}
    if len(run_ids) != 1 or not next(iter(run_ids), None):
        errors.append("events do not belong to exactly one nonempty run identity")
    starts = [item for item in events if item.get("event") == "process_start"]
    ends = [item for item in events if item.get("event") == "process_end"]
    diagnostics = [item for item in events if item.get("event") == "diagnostic"]
    if len(starts) != 1:
        errors.append("run must have exactly one process_start")
    if len(ends) != 1:
        errors.append("run must have exactly one process_end")
    if len(diagnostics) != 1:
        errors.append("run must have exactly one diagnostic artifact identity")
    if len(starts) != 1 or len(ends) != 1 or len(diagnostics) != 1:
        return errors

    start, end, diagnostic = starts[0], ends[0], diagnostics[0]
    run_id = start.get("run_id")
    if any(item.get("run_id") != run_id for item in events):
        errors.append("an event is not associated with the process run ID")
    if start.get("minecraft_version") != environment.get("minecraft_version"):
        errors.append("Minecraft version does not match the environment identity")
    if start.get("distribution") != environment.get("distribution"):
        errors.append("client/server distribution does not match the environment identity")
    if start.get("launcher") != environment.get("launcher"):
        errors.append("launcher identity does not match the environment record")
    if start.get("fabric_loader_version", "") != (environment.get("fabric_loader_expected") or ""):
        errors.append("configured Fabric Loader version does not match the matrix")
    source_sha = start.get("source_sha", "")
    if not HEX40.fullmatch(source_sha):
        errors.append("exact product source SHA is missing or malformed")
    elif subprocess.run(["git", "-C", str(source_root), "cat-file", "-e", source_sha + "^{commit}"],
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode != 0:
        errors.append("source SHA is not an available Git commit in the bound repository")
    for key in ("java_version", "java_vendor", "java_executable", "java_executable_sha256",
                "os_name", "os_version", "architecture", "java_main_class"):
        if not start.get(key):
            errors.append("missing process identity field: " + key)
    if not HEX64.fullmatch(start.get("java_executable_sha256", "")):
        errors.append("Java executable file SHA-256 is missing or malformed")
    if start.get("environment_variables_collected") is not False:
        errors.append("environment variable collection must be disabled")
    if start.get("process_command_collected") is not False:
        errors.append("raw process command collection must be disabled")
    if "jvm_arguments" in start or "process_command" in start:
        errors.append("raw unsanitized JVM arguments or process command are forbidden")
    if not isinstance(start.get("jvm_arguments_sanitized"), list):
        errors.append("sanitized JVM arguments are missing")
    if not isinstance(start.get("effective_classpath_sanitized"), list):
        errors.append("sanitized launch classpath is missing")
    else:
        for entry in start["effective_classpath_sanitized"]:
            if not isinstance(entry, dict):
                errors.append("sanitized launch classpath contains a malformed entry")
                break
            artifact = entry.get("artifact", "").lower()
            if artifact.startswith("netty-") and artifact.endswith(".jar"):
                if (entry.get("hash_verified") is not True
                        or not HEX40.fullmatch(entry.get("sha1", ""))
                        or not HEX64.fullmatch(entry.get("sha256", ""))):
                    errors.append("Netty classpath JAR lacks verified SHA-1 and SHA-256 identities")
                    break
    if not isinstance(start.get("additional_java_agents"), list):
        errors.append("additional agent inventory is missing")
    for agent in start.get("additional_java_agents", []):
        if agent.get("hash_verified") is not True or not HEX64.fullmatch(agent.get("sha256", "")):
            errors.append("additional process agent lacks a verified JAR or native-agent SHA-256")
    if environment.get("fabric_loader_expected"):
        product_jar = start.get("product_jar", {})
        if product_jar.get("hash_verified") is not True or not HEX64.fullmatch(product_jar.get("sha256", "")):
            errors.append("Fabric process product JAR is missing a verified SHA-256")
        mods = start.get("mods_directory_jars", [])
        if not mods or any(item.get("hash_verified") is not True
                           or not HEX64.fullmatch(item.get("sha256", "")) for item in mods):
            errors.append("Fabric process mod-directory JAR inventory is missing verified hashes")

    agent_hash = diagnostic.get("diagnostic_agent_sha256", "")
    if not HEX64.fullmatch(agent_hash) or diagnostic.get("diagnostic_artifact_verified") is not True:
        errors.append("diagnostic JAR SHA-256 is missing or unverified")
    if not HEX64.fullmatch(diagnostic.get("config_sha256", "")):
        errors.append("diagnostic configuration identity is missing")
    if end.get("run_id") != run_id:
        errors.append("process_end is bound to a different run")
    if end.get("jvm_shutdown_hook_executed") is not True:
        errors.append("JVM shutdown observation is missing")
    if end.get("run_outcome") != "shutdown_hook_executed":
        errors.append("process did not finish with a complete diagnostic shutdown record")

    transformed = [item for item in events if item.get("event") == "pipeline_class_transformed"]
    callbacks = [item for item in events if item.get("event") in ("handler_added", "handler_removed")]
    snapshots = [item for item in events if item.get("event") == "channel_active_pipeline_snapshot"]
    created_channels = [item for item in events if item.get("event") == "channel_created"]
    transformed_classes = {item.get("class") for item in transformed if isinstance(item.get("class"), str)}
    if (end.get("pipeline_class_transformed_count") != len(transformed)
            or not {"io.netty.channel.DefaultChannelPipeline",
                    "io.netty.channel.DefaultChannelPipeline$HeadContext",
                    "io.netty.channel.AbstractChannel"}.issubset(transformed_classes)):
        errors.append("required Netty channel and pipeline class transformations are not confirmed")
    if end.get("pipeline_callback_count") != len(callbacks) or not callbacks:
        errors.append("Netty pipeline handler callback coverage is missing or inconsistent")
    if end.get("pipeline_hook_execution_confirmed") is not True:
        errors.append("diagnostic hook did not confirm execution")
    if any(item.get("event") in ("pipeline_transform_error", "pipeline_observation_error") for item in events):
        errors.append("one or more pipeline instrumentation errors were recorded")
    if end.get("channel_active_pipeline_snapshot_count") != len(snapshots) or not snapshots:
        errors.append("channel-active pipeline snapshot hook coverage is missing or inconsistent")
    if end.get("channel_active_hook_execution_confirmed") is not True:
        errors.append("channel-active pipeline snapshot hook did not confirm execution")
    if (end.get("channel_creation_event_count") != len(created_channels) or not created_channels
            or end.get("channel_creation_hook_execution_confirmed") is not True):
        errors.append("Netty channel-creation hook did not confirm execution")

    for item in created_channels:
        source = item.get("channel_code_source", {})
        if (not HEX64.fullmatch(item.get("channel_fingerprint", ""))
                or source.get("hash_verified") is not True or not HEX64.fullmatch(source.get("sha256", ""))
                or not source.get("artifact")
                or not isinstance(item.get("channel_creation_context"), list)
                or not item.get("channel_creation_context")):
            errors.append("Netty channel-creation observation lacks a verified channel code-source identity")
            break

    for snapshot in snapshots:
        fingerprint = snapshot.get("channel_fingerprint", "")
        if not HEX64.fullmatch(fingerprint):
            errors.append("channel-active snapshot lacks a valid privacy-preserving channel fingerprint")
        handlers = snapshot.get("pipeline_handlers")
        if not isinstance(handlers, list):
            errors.append("channel-active snapshot lacks its pipeline handler inventory")
            continue
        if (not handlers and snapshot.get("channel_peer_category") in (
                "loopback", "private_or_link_local", "non_local_inet_peer_address_present")):
            errors.append("connected socket channel-active snapshot has an empty pipeline inventory")
        if (not isinstance(snapshot.get("pipeline_mutation_context"), list)
                or not snapshot.get("pipeline_mutation_context")):
            errors.append("channel-active pipeline snapshot lacks its call-site context")
        for handler in handlers:
            source = handler.get("handler_code_source", {})
            if (source.get("hash_verified") is not True or not HEX64.fullmatch(source.get("sha256", ""))
                    or not source.get("artifact")):
                errors.append("channel-active pipeline handler lacks a verified code-source JAR identity")
                break

    observed_peer = False
    for item in callbacks:
        source = item.get("handler_code_source", {})
        if (source.get("hash_verified") is not True or not HEX64.fullmatch(source.get("sha256", ""))
                or not source.get("artifact")
                or not isinstance(item.get("pipeline_installation_context"), list)
                or not item.get("pipeline_installation_context")):
            errors.append("pipeline handler lacks a verified code-source JAR identity")
            break
        if item.get("channel_peer_category") in (
                "loopback", "private_or_link_local", "non_local_inet_peer_address_present"):
            observed_peer = True
    connected_fingerprints = end.get("connected_socket_channel_fingerprints", [])
    active_fingerprints = end.get("active_socket_channel_fingerprints", [])
    if not isinstance(connected_fingerprints, list) or any(not isinstance(value, str)
                                                            for value in connected_fingerprints):
        errors.append("connected socket channel fingerprint aggregate is malformed")
        connected_fingerprints = []
    if not isinstance(active_fingerprints, list) or any(not isinstance(value, str)
                                                        for value in active_fingerprints):
        errors.append("active socket channel fingerprint aggregate is malformed")
        active_fingerprints = []
    callback_socket_events = [item for item in callbacks if item.get("channel_peer_category") in (
        "loopback", "private_or_link_local", "non_local_inet_peer_address_present")]
    callback_socket_fingerprints = {item.get("channel_fingerprint") for item in callback_socket_events
                                    if isinstance(item.get("channel_fingerprint"), str)}
    snapshot_socket_fingerprints = {item.get("channel_fingerprint") for item in snapshots
                                    if item.get("channel_peer_category") in (
                                        "loopback", "private_or_link_local",
                                        "non_local_inet_peer_address_present")
                                    and isinstance(item.get("channel_fingerprint"), str)}
    if set(connected_fingerprints) != callback_socket_fingerprints | snapshot_socket_fingerprints:
        errors.append("connected socket channel fingerprint aggregate disagrees with per-channel events")
    if set(active_fingerprints) != snapshot_socket_fingerprints:
        errors.append("active socket channel fingerprint aggregate disagrees with pipeline snapshots")
    if end.get("connected_socket_pipeline_callback_count") != len(callback_socket_events):
        errors.append("connected socket callback count is inconsistent")
    if require_remote_pipeline and not observed_peer:
        errors.append("no connected socket pipeline callback was observed")
    if require_remote_pipeline and end.get("connected_socket_pipeline_callback_count", 0) <= 0:
        errors.append("connected socket callback count is empty")
    if require_remote_pipeline and (not connected_fingerprints or set(connected_fingerprints) != set(active_fingerprints)):
        errors.append("connected socket channels lack channel-active pipeline snapshots")

    modules = end.get("loaded_netty_artifacts", [])
    if not isinstance(modules, list) or any(not isinstance(item, dict) for item in modules):
        errors.append("loaded Netty artifact inventory is malformed")
        modules = []
    if not modules:
        errors.append("no loaded Netty artifacts were observed")
    expected_version = environment.get("expected_netty_codec") or environment.get("expected_bundled_netty_codec")
    versions: set[str] = set()
    for module in modules:
        module_hash = module.get("sha256", "")
        if (module.get("hash_verified") is not True or not HEX64.fullmatch(module_hash)
                or not HEX40.fullmatch(module.get("sha1", ""))):
            errors.append("loaded Netty module has a missing or unverified SHA-256")
            break
        versions.update(value for value in module.get("package_versions", []) if value)
    if expected_version and expected_version not in versions:
        errors.append("loaded Netty module version does not match the pinned environment expectation")
    if expected_version and any(version != expected_version for version in versions if version):
        errors.append("multiple Netty versions are present among loaded code-source artifacts")
    if not end.get("loaded_netty_classes"):
        errors.append("relevant loaded Netty class identities are missing")
    if not isinstance(end.get("loaded_code_source_groups"), list):
        errors.append("loaded class-loader code-source inventory is missing")
    expected_fabric = environment.get("fabric_loader_expected")
    if expected_fabric:
        fabric_classes = end.get("loaded_fabric_loader_classes", [])
        if not fabric_classes:
            errors.append("Fabric Loader classes were not observed in the running process")
        elif not any(item.get("code_source", {}).get("hash_verified") is True for item in fabric_classes):
            errors.append("Fabric Loader code source lacks a verified JAR digest")

    raw = json.dumps(events, sort_keys=True)
    if re.search(r"(?i)(access[-_]?token|password|passwd|session|cookie|authorization|client[-_]?secret|username|uuid|xuid)(?:=|[:\" ]+)(?!<redacted>)[A-Za-z0-9._-]{8,}", raw):
        errors.append("credential or account-like value appears in the sanitized observation")
    return errors


def validate_evidence(evidence_dir: Path, source_root: Path) -> tuple[list[str], dict]:
    errors: list[str] = []
    baseline_path = evidence_dir / "baseline-lock.json"
    matrix_path = evidence_dir / "environment-matrix.json"
    baseline = load_json(baseline_path)
    matrix = load_json(matrix_path)
    if baseline.get("schema") != "issue45-runtime-evidence-baseline/v1":
        errors.append("baseline lock schema mismatch")
    for name, expected in baseline.get("retained_files", {}).items():
        path = source_root / name
        if not path.is_file() or sha256(path) != expected:
            errors.append("retained prior evidence changed or is missing: " + name)
    if baseline.get("retained_security_inventory", {}).get("total") != 490:
        errors.append("historical security inventory total changed")

    envs = matrix.get("environments", [])
    ids = [row.get("environment_id") for row in envs]
    if len(ids) != len(set(ids)) or not ids:
        errors.append("environment matrix is empty or contains duplicate identities")
    run_ids: set[str] = set()
    captured = []
    for row in envs:
        status = row.get("status")
        if status not in ("not_executed", "not_passed", "captured"):
            errors.append("unsupported environment status for " + str(row.get("environment_id")))
            continue
        pin_errors, expected_artifact = validate_environment_artifact_pin(
            row, source_root, baseline.get("retained_files", {}))
        errors.extend(f"{row.get('environment_id')}: {item}" for item in pin_errors)
        manifest_path = row.get("manifest_path")
        if manifest_path:
            manifest_file = source_root / manifest_path
            if not manifest_file.is_file() or sha256(manifest_file) != row.get("manifest_sha256"):
                errors.append("pinned manifest identity mismatch for " + str(row.get("environment_id")))
            elif row.get("expected_netty_codec"):
                manifest = load_json(manifest_file)
                expected = row["expected_netty_codec"]
                module = "netty-codec" if expected.startswith("4.1.") else "netty-codec-compression"
                coordinate = "io.netty:" + module + ":" + expected
                if not any(item.get("name") == coordinate for item in manifest.get("libraries", [])):
                    errors.append("expected LZ4 Netty module/version is absent from retained manifest for "
                                  + str(row.get("environment_id")))
        if status == "not_executed":
            if not row.get("not_executed_reason"):
                errors.append("not_executed row lacks its actual blocker")
            if row.get("observations_file") or row.get("observations_sha256"):
                errors.append("not_executed row must not carry fabricated observations")
            continue
        obs_name = row.get("observations_file")
        obs_hash = row.get("observations_sha256", "")
        if not obs_name or not HEX64.fullmatch(obs_hash):
            errors.append("attempted row lacks exact observation path and SHA-256: "
                          + str(row.get("environment_id")))
            continue
        obs_path = (evidence_dir / obs_name).resolve()
        try:
            obs_path.relative_to(evidence_dir.resolve())
        except ValueError:
            errors.append("observation file escapes the evidence directory")
            continue
        if not obs_path.is_file() or sha256(obs_path) != obs_hash:
            errors.append("observation artifact missing or SHA-256 mismatch: " + str(obs_name))
            continue
        try:
            events = [json.loads(line) for line in obs_path.read_text(encoding="utf-8").splitlines() if line.strip()]
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            errors.append("observation file is not valid JSON Lines: " + str(error))
            continue
        if any(not isinstance(item, dict) for item in events):
            errors.append("observation file contains a non-object JSON event: " + str(obs_name))
            continue
        run_id = events[0].get("run_id") if events else None
        if run_id in run_ids:
            errors.append("duplicate process/run identity: " + str(run_id))
        elif run_id:
            run_ids.add(run_id)
        errors.extend(f"{row.get('environment_id')}: {item}" for item in validate_run_events(events, row, source_root))
        ends = [item for item in events if item.get("event") == "process_end"]
        starts = [item for item in events if item.get("event") == "process_start"]
        if expected_artifact is not None and ends and starts:
            errors.extend(f"{row.get('environment_id')}: {item}" for item in
                          validate_runtime_artifact_identity(starts[0], ends[0], expected_artifact))
        if status == "captured":
            if row.get("operator_exit_code") != 0 or row.get("operator_startup_outcome") != "started":
                errors.append("captured row lacks successful operator-observed startup/exit outcome")
            if ends:
                errors.extend(f"{row.get('environment_id')}: {item}" for item in
                              validate_channel_assessments(ends[0], row.get("input_boundary_assessments")))
            captured.append(row.get("environment_id"))
        elif not row.get("not_passed_reason"):
            errors.append("not_passed row lacks failure explanation")

    declared = matrix.get("captured_observations", [])
    if sorted(declared) != sorted(captured):
        errors.append("captured_observations index disagrees with environment statuses")

    reconciliation = evidence_dir / "minecraft-1.19-official-artifact-revalidation.json"
    try:
        report = load_json(reconciliation)
        if report.get("schema") != "issue45-mc119-artifact-revalidation/v1":
            errors.append("1.19 reconciliation schema mismatch")
        client = report["client_netty_codec"]
        server = report["server_nested_netty_codec"]
        if client.get("package_version") != "4.1.77.Final" or server.get("package_version") != "4.1.76.Final":
            errors.append("1.19 official artifact versions do not show the recorded discrepancy")
        for record in (client, server, report["server_bundle"], report["version_manifest"]):
            observed = record.get("observed", record.get("official_bytes", {}))
            if not HEX64.fullmatch(observed.get("sha256", "")):
                errors.append("1.19 artifact revalidation lacks a SHA-256")
        if report.get("classification", {}).get("server_process_runtime_selection") != "unresolved_without_a_launched_official_server_process":
            errors.append("1.19 server runtime selection is overstated")
    except (OSError, KeyError, json.JSONDecodeError) as error:
        errors.append("1.19 artifact reconciliation missing or incomplete: " + str(error))

    summary_path = evidence_dir / "synthetic-control-verification.json"
    try:
        summary = load_json(summary_path)
        if (summary.get("schema") != "issue45-runtime-synthetic-controls/v1"
                or summary.get("scope") != "synthetic_only" or summary.get("result") != "pass"
                or summary.get("synthetic_observations_are_minecraft_runtime_evidence") is not False):
            errors.append("synthetic control result is not scoped and passed")
        expected = {
            "control-lz4": "io.netty.handler.codec.compression.Lz4FrameDecoder",
            "control-zlib": "io.netty.handler.codec.compression.JdkZlibDecoder",
            "control-plain": "io.netty.channel.ChannelInboundHandlerAdapter",
        }
        if summary.get("controls") != expected:
            errors.append("synthetic positive/negative control set is incomplete")
        if not HEX64.fullmatch(summary.get("agent_sha256", "")):
            errors.append("synthetic diagnostic artifact SHA-256 is malformed")
        lock = load_json(source_root / "diagnostics/issue45-runtime/dependencies.lock.json")
        expected_profiles = {item["profileId"]: item for item in lock.get("syntheticProfiles", [])}
        actual_profiles = summary.get("profiles", [])
        profile_ids = [item.get("profile_id") for item in actual_profiles]
        if set(profile_ids) != set(expected_profiles) or len(profile_ids) != len(set(profile_ids)):
            errors.append("synthetic profiles do not exactly match pinned Netty-family controls")
        for record in actual_profiles:
            profile_id = record.get("profile_id")
            pinned = expected_profiles.get(profile_id)
            if not pinned:
                continue
            if pinned.get("manifestPath"):
                if record.get("manifest_sha256") != pinned.get("manifestSha256"):
                    errors.append("synthetic profile manifest identity does not match its source lock: " + str(profile_id))
                if record.get("dependency_source") != "official_minecraft_manifest":
                    errors.append("Minecraft profile source type is incorrect: " + str(profile_id))
            else:
                candidate_lock = source_root / pinned.get("artifactLockPath", "")
                if (not candidate_lock.is_file() or sha256(candidate_lock) != pinned.get("artifactLockSha256")
                        or record.get("dependency_lock_sha256") != pinned.get("artifactLockSha256")
                        or record.get("dependency_source") != "pinned_maven_fixed_candidate"):
                    errors.append("upstream candidate dependency lock identity mismatch: " + str(profile_id))
            if record.get("expected_and_loaded_netty_version") != pinned.get("expectedNettyVersion"):
                errors.append("synthetic profile module family does not match its version lock: " + str(profile_id))
            synthetic_file = (evidence_dir / record.get("observation_file", "")).resolve()
            try:
                synthetic_file.relative_to(evidence_dir.resolve())
            except ValueError:
                errors.append("synthetic control observation escapes the evidence directory")
                synthetic_file = Path("/")
            if not synthetic_file.is_file() or sha256(synthetic_file) != record.get("observation_sha256"):
                errors.append("source-bound synthetic observation missing or digest mismatch: " + str(profile_id))
                continue
            synthetic_events = [json.loads(line) for line in synthetic_file.read_text(encoding="utf-8").splitlines()
                                if line.strip()]
            synthetic_env = {"minecraft_version": pinned["minecraftVersion"], "distribution": "synthetic",
                             "launcher": "local-control", "fabric_loader_expected": None,
                             "expected_netty_codec": pinned["expectedNettyVersion"]}
            errors.extend(f"synthetic {profile_id}: {item}" for item in validate_run_events(
                synthetic_events, synthetic_env, source_root, require_remote_pipeline=False))
            if not synthetic_events or synthetic_events[0].get("run_id") != record.get("run_id"):
                errors.append("synthetic summary/process run IDs differ: " + str(profile_id))
            if record.get("operator_process_exit_code") != 0:
                errors.append("synthetic JVM did not report exit code 0: " + str(profile_id))
            ends = [item for item in synthetic_events if item.get("event") == "process_end"]
            diagnostics = [item for item in synthetic_events if item.get("event") == "diagnostic"]
            if not ends or ends[0].get("loaded_lz4_decoder_class_count") != 1:
                errors.append("loaded-LZ4 positive control missing: " + str(profile_id))
            if (not ends or ends[0].get("channel_creation_hook_execution_confirmed") is not True
                    or ends[0].get("channel_active_hook_execution_confirmed") is not True
                    or record.get("channel_creation_and_active_hooks_executed") is not True):
                errors.append("synthetic channel creation/active hooks did not run: " + str(profile_id))
            if (not diagnostics or diagnostics[0].get("diagnostic_agent_sha256") != summary.get("agent_sha256")
                    or record.get("diagnostic_event_sha256") != summary.get("agent_sha256")):
                errors.append("synthetic agent digest is not process-bound: " + str(profile_id))
            handler_events = [item for item in synthetic_events if item.get("event") == "handler_added"]
            removed_events = [item for item in synthetic_events if item.get("event") == "handler_removed"]
            by_name = {item.get("handler_name"): item for item in handler_events}
            if any(name not in by_name or by_name[name].get("handler_class") != class_name
                   for name, class_name in expected.items()):
                errors.append("raw synthetic pipeline events do not distinguish all controls: " + str(profile_id))
            removed_by_name = {item.get("handler_name"): item for item in removed_events}
            if any(name not in removed_by_name or removed_by_name[name].get("handler_class") != class_name
                   for name, class_name in expected.items()):
                errors.append("raw synthetic pipeline events do not verify handler removals: " + str(profile_id))
            if record.get("pipeline_handler_additions") != len(handler_events) or record.get(
                    "pipeline_handler_removals") != len(removed_events):
                errors.append("synthetic pipeline add/remove counts are not source-bound: " + str(profile_id))
            plain_identity = by_name.get("control-plain", {}).get("channel_identity")
            plain_handlers = [item.get("handler_class", "") for item in handler_events
                              if item.get("channel_identity") == plain_identity]
            if any("Lz4FrameDecoder" in name or "ZlibDecoder" in name for name in plain_handlers):
                errors.append("plain synthetic pipeline contains a compression decoder: " + str(profile_id))
            actual_artifacts = {}
            if ends:
                actual_artifacts = {item.get("artifact", ""): item.get("sha256")
                                    for item in ends[0].get("loaded_netty_artifacts", [])}
            for artifact in record.get("netty_artifacts", []):
                filename = artifact.get("path", "").rsplit("/", 1)[-1]
                if (not HEX64.fullmatch(artifact.get("observed_sha256", ""))
                        or artifact.get("source_lock_sha256", pinned.get("manifestSha256")) not in
                        (pinned.get("manifestSha256", ""), pinned.get("artifactLockSha256", ""), "")):
                    errors.append("synthetic downloaded JAR is not bound to a known source lock: "
                                  + str(profile_id) + ":" + filename)
                if filename in actual_artifacts and actual_artifacts[filename] != artifact.get("observed_sha256"):
                    errors.append("loaded synthetic Netty JAR digest differs from downloaded artifact: " + filename)
    except (OSError, json.JSONDecodeError) as error:
        errors.append("synthetic control result missing or invalid: " + str(error))

    compatibility_path = evidence_dir / "remediation-compatibility.json"
    try:
        compatibility = load_json(compatibility_path)
        if compatibility.get("schema") != "issue45-netty-remediation-compatibility/v1":
            errors.append("upstream compatibility record schema mismatch")
        locked_priority = baseline.get("retained_files", {}).get(
            "docs/dependency-evidence/issue45-netty-lz4-high-2026-11-23/priority-register-v6.json")
        if (compatibility.get("source_register", {}).get("sha256") != locked_priority
                or compatibility.get("focused_netty_advisory_count") != 15):
            errors.append("compatibility analysis is not bound to the retained focused Netty register")
        if compatibility.get("minimum_versions_for_lz4_advisory_only") != {
                "4.1": "4.1.133.Final", "4.2": "4.2.13.Final"}:
            errors.append("LZ4 fixed boundaries differ from retained upstream advisory evidence")
        if compatibility.get("minimum_versions_covering_all_15_focused_netty_advisories") != {
                "4.1": "4.1.137.Final", "4.2": "4.2.17.Final"}:
            errors.append("minimum versions for focused Netty set are incomplete")
        compatibility_rows = compatibility.get("environments", [])
        if {item.get("environment_id") for item in compatibility_rows} != set(ids):
            errors.append("compatibility matrix does not cover every representative environment")
        if any(item.get("runtime_loader_selection_verified") is not False
               or item.get("minecraft_fabric_abi_verified") is not False
               or item.get("outcome") != "minecraft-managed dependency blocker"
               for item in compatibility_rows):
            errors.append("compatibility record overstates a Minecraft/Fabric remediation")
        mc262 = [item for item in compatibility_rows if item.get("minecraft_version") == "26.2"]
        if (not mc262 or any(item.get("lz4_advisory_fixed_boundary_met_by_selected_artifact_version") is not True
                             or item.get("all_15_focused_netty_advisory_boundaries_met") is not False
                             for item in mc262)):
            errors.append("26.2 LZ4-only and full-Netty remediation boundary distinction is missing")
    except (OSError, json.JSONDecodeError) as error:
        errors.append("upstream remediation compatibility record missing or invalid: " + str(error))

    input_path = evidence_dir / "input-boundary-assessment.json"
    try:
        boundary = load_json(input_path)
        levels = boundary.get("reachability_levels", [])
        if boundary.get("schema") != "issue45-lz4-input-boundary-assessment/v1" or [
                item.get("level") for item in levels] != list(range(1, 10)):
            errors.append("input-boundary assessment does not preserve all nine evidence levels")
        if any(boundary.get("reachability_levels", [])[index].get("status") not in
               ("not_observed", "not_established", "not_verified") for index in range(2, 9)):
            errors.append("input-boundary assessment overstates an unobserved runtime level")
        if boundary.get("synthetic_control_pipeline_handlers", {}).get("socket_or_remote_input") is not False:
            errors.append("synthetic channel evidence is presented as remote input")
        if "No supported configuration can be classified" not in boundary.get("conclusion", ""):
            errors.append("input-boundary conclusion overstates reachability")
    except (OSError, json.JSONDecodeError) as error:
        errors.append("input-boundary assessment missing or invalid: " + str(error))

    next_target_path = evidence_dir / "next-security-target.json"
    try:
        target = load_json(next_target_path)
        if target.get("source_priority_register_sha256") != baseline.get("retained_files", {}).get(
                "docs/dependency-evidence/issue45-netty-lz4-high-2026-11-23/priority-register-v6.json"):
            errors.append("next target is not source-bound to the current priority register")
        register = load_json(source_root / "docs/dependency-evidence/issue45-netty-lz4-high-2026-11-23/priority-register-v6.json")
        advisory = next(item for item in register["advisories"] if item["advisory_id"] == target.get("advisory_id"))
        if (advisory.get("focused_evidence") is not None
                or len(advisory.get("occurrences", [])) != target.get("unfocused_high_occurrences")
                or target.get("severity", "").lower() != advisory.get("severity", "").lower()):
            errors.append("next target is not an unfocused High with the stated occurrence count")
        fixed = target.get("upstream_fixed_boundaries_from_retained_register", {})
        ranges = advisory.get("affected_ranges", {}).get("pkg:maven/io.netty/netty-codec-http", [])
        observed_fixed = set()
        for range_group in ranges:
            for item in range_group:
                for event in item.get("events", []):
                    if event.get("fixed"):
                        observed_fixed.add(event["fixed"])
        if not set(fixed.values()).issubset(observed_fixed):
            errors.append("next target fixed boundaries differ from the priority register")
    except (OSError, KeyError, StopIteration, json.JSONDecodeError) as error:
        errors.append("next security target missing or not linked to a register record: " + str(error))

    result = {"expected_environment_count": len(envs), "captured_runtime_environment_count": len(captured),
              "not_executed_environment_count": sum(row.get("status") == "not_executed" for row in envs),
              "captured_environments": captured,
              "runtime_acceptance": "not_established" if not captured else "partial_matrix_only",
              "synthetic_controls_are_game_evidence": False}
    return errors, result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence-dir", required=True, type=Path)
    parser.add_argument("--source-root", type=Path, default=Path(__file__).resolve().parents[2])
    args = parser.parse_args()
    errors, result = validate_evidence(args.evidence_dir.resolve(), args.source_root.resolve())
    output = {"result": "valid_archive" if not errors else "invalid_archive", **result,
              "errors": errors}
    print(json.dumps(output, sort_keys=True))
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
