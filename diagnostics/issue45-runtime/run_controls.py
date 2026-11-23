#!/usr/bin/env python3
"""Run no-socket synthetic controls on exact Minecraft 1.19 and 26.2 Netty sets."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
OUT = REPO / "docs/dependency-evidence/issue45-runtime-pipeline-2026-11-23"
LOCK = json.loads((HERE / "dependencies.lock.json").read_text(encoding="utf-8"))
CACHE = Path.home() / ".cache/issue45-runtime"
EXPECTED_CONTROLS = {
    "control-lz4": "io.netty.handler.codec.compression.Lz4FrameDecoder",
    "control-zlib": "io.netty.handler.codec.compression.JdkZlibDecoder",
    "control-plain": "io.netty.channel.ChannelInboundHandlerAdapter",
}


def hash_file(path: Path, algorithm: str) -> str:
    digest = hashlib.new(algorithm)
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def fetch(url: str, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        request = urllib.request.Request(url, headers={"User-Agent": "issue45-runtime-diagnostic/1"})
        with urllib.request.urlopen(request, timeout=90) as response, path.open("wb") as target:
            shutil.copyfileobj(response, target)


def run_profile(profile: dict, work: Path, agent: Path, compiler: Path,
                lz4_helper: Path, source_sha: str) -> dict:
    wanted = set(profile["modules"])
    profile_root = work / profile["profileId"]
    dependency_root = profile_root / "dependencies"
    artifacts: list[Path] = []
    records = []
    selected = set()
    dependency_lock_sha = ""
    manifest_hash = ""
    if profile.get("artifactLockPath"):
        candidate_lock_path = (REPO / profile["artifactLockPath"]).resolve()
        dependency_lock_sha = hash_file(candidate_lock_path, "sha256")
        if dependency_lock_sha != profile["artifactLockSha256"]:
            raise SystemExit("upstream candidate artifact lock SHA-256 mismatch")
        candidate_lock = json.loads(candidate_lock_path.read_text(encoding="utf-8"))
        for item in candidate_lock["profiles"][profile["artifactLockName"]]:
            module = item["module"]
            version = profile["expectedNettyVersion"]
            relative = "io/netty/{}/{}/{}-{}.jar".format(module, version, module, version)
            path = dependency_root / relative
            url = "https://repo.maven.apache.org/maven2/" + relative
            fetch(url, path)
            if path.stat().st_size != item["size"] or hash_file(path, "sha256") != item["sha256"]:
                raise SystemExit("upstream fixed-candidate SHA-256/size mismatch: " + module)
            artifacts.append(path)
            selected.add(module)
            records.append({"coordinate": "io.netty:{}:{}".format(module, version), "path": relative,
                            "source_lock_sha256": dependency_lock_sha, "observed_sha256": hash_file(path, "sha256"),
                            "size_bytes": item["size"]})
    else:
        manifest_path = (REPO / profile["manifestPath"]).resolve()
        manifest_hash = hash_file(manifest_path, "sha256")
        if manifest_hash != profile["manifestSha256"]:
            raise SystemExit("retained manifest SHA-256 mismatch for " + profile["profileId"])
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        for library in manifest.get("libraries", []):
            parts = library.get("name", "").split(":")
            if len(parts) != 3 or parts[0] != "io.netty" or parts[1] not in wanted:
                continue
            item = library.get("downloads", {}).get("artifact")
            if not item:
                raise SystemExit("missing exact artifact metadata for " + library["name"])
            path = dependency_root / item["path"]
            fetch(item["url"], path)
            if path.stat().st_size != item["size"] or hash_file(path, "sha1") != item["sha1"]:
                raise SystemExit("manifest-pinned Netty size/SHA-1 mismatch: " + item["path"])
            artifacts.append(path)
            selected.add(parts[1])
            records.append({"coordinate": library["name"], "path": item["path"],
                            "official_sha1": item["sha1"], "size_bytes": item["size"],
                            "observed_sha256": hash_file(path, "sha256")})
    if selected != wanted:
        raise SystemExit("exact Netty module-family selection incomplete for " + profile["profileId"])

    helper = LOCK["syntheticLz4Helper"]
    fetch(helper["url"], lz4_helper)
    if hash_file(lz4_helper, "sha256") != helper["sha256"]:
        raise SystemExit("pinned test-only LZ4 helper SHA-256 mismatch")
    artifacts.append(lz4_helper)

    test_classes = profile_root / "test-classes"
    test_classes.mkdir(parents=True, exist_ok=True)
    source = HERE / "src/test/java/dev/skyrolly/issue45/ControlMain.java"
    compile_cp = os.pathsep.join(str(path) for path in artifacts)
    subprocess.run(["java", "-jar", str(compiler), "-encoding", "UTF-8", "-17",
                    "-classpath", compile_cp, "-d", str(test_classes), str(source)], check=True)

    config = profile_root / "control.properties"
    report = profile_root / "control.jsonl"
    config.write_text("\n".join([
        "output=" + report.as_posix(), "minecraftVersion=" + profile["minecraftVersion"],
        "distribution=synthetic", "launcher=local-control", "sourceSha=" + source_sha, "",
    ]), encoding="utf-8")
    run_cp = os.pathsep.join([str(test_classes)] + [str(path) for path in artifacts])
    command = ["java", "-DaccessToken=synthetic-secret-must-not-appear",
               "-Dsession:synthetic-secret-must-not-appear",
               "-Dserver=play.example.invalid:25565",
               "-Dusername=synthetic-player-identifier",
               "-javaagent:" + str(agent) + "=" + str(config), "-classpath", run_cp,
               "dev.skyrolly.issue45.ControlMain"]
    completed = subprocess.run(command, cwd=profile_root, text=True, capture_output=True, timeout=90)
    (profile_root / "control.stdout.txt").write_text(completed.stdout, encoding="utf-8")
    (profile_root / "control.stderr.txt").write_text(completed.stderr, encoding="utf-8")
    if completed.returncode != 0:
        raise SystemExit("synthetic process failed for " + profile["profileId"] + "; inspect private work-dir logs")

    raw = report.read_text(encoding="utf-8")
    private_values = ("synthetic-secret-must-not-appear", "play.example.invalid",
                      "25565", "synthetic-player-identifier")
    if any(value in raw for value in private_values):
        raise SystemExit("privacy sanitizer leaked a synthetic token, address, or account identifier")
    for sanitized in ("-DaccessToken=<redacted>", "-Dsession:<redacted>",
                      "-Dserver=<redacted>", "-Dusername=<redacted>"):
        if sanitized not in raw:
            raise SystemExit("privacy sanitizer control did not preserve the redacted argument marker")
    events = [json.loads(line) for line in raw.splitlines() if line.strip()]
    end = next((event for event in events if event.get("event") == "process_end"), None)
    if end is None or end.get("run_outcome") != "shutdown_hook_executed":
        raise SystemExit("JVM shutdown hook record missing for " + profile["profileId"])
    if not end.get("pipeline_hook_execution_confirmed"):
        raise SystemExit("Netty pipeline transformation/add callback did not execute")
    if (not end.get("channel_creation_hook_execution_confirmed")
            or not end.get("channel_active_hook_execution_confirmed")):
        raise SystemExit("channel creation or active-pipeline snapshot hook did not execute")
    if (end.get("channel_creation_event_count", 0) <= 0
            or end.get("channel_active_pipeline_snapshot_count", 0) <= 0):
        raise SystemExit("channel creation/activation events are missing")
    added = [event for event in events if event.get("event") == "handler_added"]
    removed = [event for event in events if event.get("event") == "handler_removed"]
    by_name = {event.get("handler_name"): event for event in added}
    for name, class_name in EXPECTED_CONTROLS.items():
        if name not in by_name or by_name[name].get("handler_class") != class_name:
            raise SystemExit("pipeline control mismatch for " + name + " in " + profile["profileId"])
    removed_by_name = {event.get("handler_name"): event for event in removed}
    if any(name not in removed_by_name or removed_by_name[name].get("handler_class") != class_name
           for name, class_name in EXPECTED_CONTROLS.items()):
        raise SystemExit("pipeline handler removal control mismatch in " + profile["profileId"])
    plain_identity = by_name["control-plain"].get("channel_identity")
    plain_handlers = [event.get("handler_class", "") for event in added
                      if event.get("channel_identity") == plain_identity]
    if any("Lz4FrameDecoder" in name or "ZlibDecoder" in name for name in plain_handlers):
        raise SystemExit("plain negative-control pipeline unexpectedly contains a decoder")
    if end.get("loaded_lz4_decoder_class_count") != 1:
        raise SystemExit("loaded LZ4 positive class control failed")
    if not any(profile["expectedNettyVersion"] in module.get("package_versions", [])
               for module in end.get("loaded_netty_artifacts", [])):
        raise SystemExit("loaded package version did not match " + profile["expectedNettyVersion"])

    diagnostic = next(event for event in events if event.get("event") == "diagnostic")
    raw_name = "synthetic-control-observation-" + profile["profileId"] + ".jsonl"
    raw_destination = OUT / raw_name
    raw_destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(report, raw_destination)
    return {
        "profile_id": profile["profileId"],
        "minecraft_manifest_version": profile.get("manifestPath", "").rsplit("/", 1)[-1][:-5],
        "synthetic_process_minecraft_version": profile["minecraftVersion"],
        "expected_and_loaded_netty_version": profile["expectedNettyVersion"],
        "manifest_sha256": manifest_hash,
        "dependency_lock_sha256": dependency_lock_sha,
        "dependency_source": "official_minecraft_manifest" if manifest_hash else "pinned_maven_fixed_candidate",
        "run_id": end["run_id"], "operator_process_exit_code": completed.returncode,
        "observation_file": raw_destination.name, "observation_sha256": hash_file(raw_destination, "sha256"),
        "diagnostic_event_sha256": diagnostic["diagnostic_agent_sha256"],
        "pipeline_handler_additions": len(added),
        "pipeline_handler_removals": len(removed),
        "channel_creation_and_active_hooks_executed": True,
        "loaded_lz4_decoder_classes": end["loaded_lz4_decoder_class_count"],
        "pipeline_hooks_executed": end["pipeline_hook_execution_confirmed"],
        "netty_artifacts": sorted(records, key=lambda item: item["coordinate"]),
        "test_only_lz4_helper_sha256": hash_file(lz4_helper, "sha256"),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--work-dir", required=True, type=Path)
    args = parser.parse_args()
    work = args.work_dir.resolve()
    work.mkdir(parents=True, exist_ok=True)
    CACHE.mkdir(parents=True, exist_ok=True)
    for key, filename in (("compiler", "ecj-3.39.0.jar"), ("byteBuddy", "byte-buddy-1.14.18.jar")):
        dependency = LOCK[key]
        path = CACHE / filename
        fetch(dependency["url"], path)
        if hash_file(path, "sha256") != dependency["sha256"]:
            raise SystemExit(key + " dependency SHA-256 mismatch")
    helper_path = CACHE / "lz4-java-1.8.0.jar"
    agent = work / "issue45-runtime-agent.jar"
    subprocess.run([sys.executable, str(HERE / "build_agent.py"), "--output", str(agent)], check=True)
    source_sha = subprocess.check_output(["git", "-C", str(REPO), "rev-parse", "HEAD"], text=True).strip()
    profiles = [run_profile(profile, work, agent, CACHE / "ecj-3.39.0.jar", helper_path, source_sha)
                for profile in LOCK["syntheticProfiles"]]
    result = {
        "schema": "issue45-runtime-synthetic-controls/v1", "result": "pass", "scope": "synthetic_only",
        "agent_sha256": hash_file(agent, "sha256"), "profiles": profiles,
        "controls": EXPECTED_CONTROLS,
        "instrumentation_negative_controls": ["plain pipeline has neither decoder", "missing pipeline hooks rejected"],
        "synthetic_processes_used_network_sockets": False,
        "malformed_or_large_frames_sent": False,
        "synthetic_observations_are_minecraft_runtime_evidence": False,
    }
    summary = OUT / "synthetic-control-verification.json"
    summary.parent.mkdir(parents=True, exist_ok=True)
    summary.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
