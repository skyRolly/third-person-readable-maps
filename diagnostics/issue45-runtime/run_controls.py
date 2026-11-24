#!/usr/bin/env python3
"""Run no-socket synthetic controls on exact Minecraft 1.19 and 26.2 Netty sets."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import uuid
import shutil
import stat
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
import zipfile
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
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


def fetch(url: str, path: Path, expected_hash: str, algorithm: str = "sha256",
          expected_size: int | None = None) -> None:
    """Reuse only hash-verified cache entries; atomically publish complete files."""
    path.parent.mkdir(parents=True, exist_ok=True)
    def valid(candidate: Path) -> bool:
        return (candidate.is_file() and (expected_size is None or candidate.stat().st_size == expected_size)
                and hash_file(candidate, algorithm) == expected_hash)
    if valid(path):
        return
    if path.exists() and not path.is_file():
        raise SystemExit("control cache target is not a file: " + str(path))
    temporary = path.with_name(path.name + "." + uuid.uuid4().hex + ".part")
    try:
        request = urllib.request.Request(url, headers={"User-Agent": "issue45-runtime-diagnostic/1"})
        for attempt in range(3):
            try:
                with urllib.request.urlopen(request, timeout=90) as response, temporary.open("xb") as target:
                    shutil.copyfileobj(response, target)
            except urllib.error.HTTPError as error:
                temporary.unlink(missing_ok=True)
                # Respect upstream rate limits without masking permanent
                # failures or retrying any integrity mismatch.
                if error.code != 429 or attempt == 2:
                    raise
                retry_after = error.headers.get("Retry-After") if error.headers else None
                delay = 2 ** (attempt + 1)
                if retry_after:
                    try:
                        delay = max(delay, int(retry_after))
                    except ValueError:
                        try:
                            when = parsedate_to_datetime(retry_after)
                            if when.tzinfo is None:
                                when = when.replace(tzinfo=timezone.utc)
                            delay = max(delay, (when - datetime.now(timezone.utc)).total_seconds())
                        except (ValueError, TypeError, OverflowError):
                            pass
                if delay > 60:
                    raise  # Do not retry earlier than the server permits.
                error.close()
                time.sleep(delay)
                continue
            if not valid(temporary):
                raise SystemExit("downloaded control dependency hash or size differs: " + path.name)
            os.replace(temporary, path)
            return
    finally:
        temporary.unlink(missing_ok=True)


def validate_control_privacy(raw: str) -> list[dict]:
    """Check synthetic canaries without mistaking digest digits for an address."""
    private_values = ("synthetic-secret-must-not-appear", "synthetic-unrecognized-api-key-must-not-appear",
                      "play.example.invalid", "synthetic-player-identifier", "-DapiKey")
    message = "privacy sanitizer leaked a synthetic token, address, or account identifier"
    if any(value in raw for value in private_values):
        raise SystemExit(message)
    events = [json.loads(line) for line in raw.splitlines() if line.strip()]

    def contains_canary(value, field=""):
        if isinstance(value, dict):
            return any(contains_canary(key) or contains_canary(item, key)
                       for key, item in value.items())
        if isinstance(value, list):
            return any(contains_canary(item, field) for item in value)
        if isinstance(value, str):
            # Full unique canaries remain forbidden anywhere, even when JSON
            # escapes their characters. Match the short decimal port as a
            # standalone token in text, never as a substring of a digest.
            return (any(marker in value for marker in private_values)
                    or re.search(r"(?<![A-Za-z0-9])25565(?![A-Za-z0-9])", value) is not None)
        return (type(value) is int and value == 25565
                and field.lower().replace("_", "").replace("-", "") in
                {"port", "serverport", "remoteport", "localport", "peerport", "destinationport", "sourceport"})

    if contains_canary(events):
        raise SystemExit(message)
    starts = [event for event in events if event.get("event") == "process_start"]
    args = starts[0].get("jvm_arguments_sanitized") if len(starts) == 1 else None
    required = ("-DaccessToken=<redacted>", "-Dsession:<redacted>",
                "-Dserver=<redacted>", "-Dusername=<redacted>")
    if not isinstance(args, list) or any(marker not in args for marker in required):
        raise SystemExit("privacy sanitizer control did not preserve the redacted argument marker")
    return events


def windows_system_icacls() -> str:
    """Never search the game directory or PATH for the Windows ACL tool."""
    root = os.environ.get("SystemRoot")
    if not root:
        raise SystemExit("Windows SystemRoot is missing")
    folder = Path(root)
    tool = folder / "System32" / "icacls.exe"
    if not folder.is_absolute() or not tool.is_file() or tool.is_symlink():
        raise SystemExit("trusted Windows icacls.exe is unavailable")
    return str(tool)


def compile_control_jar(profile_root: Path, compiler: Path, source: Path,
                        compile_cp: str, destination: Path) -> None:
    """Compile in an isolated fresh directory, never a reused class-output tree."""
    with tempfile.TemporaryDirectory(prefix="test-classes-", dir=profile_root) as temporary:
        classes = Path(temporary)
        subprocess.run(["java", "-jar", str(compiler), "-encoding", "UTF-8", "-17",
                        "-classpath", compile_cp, "-d", str(classes), str(source)], check=True)
        package_control_classes(classes, destination)


def package_control_classes(classes: Path, destination: Path) -> None:
    """Atomically refresh a deterministic control JAR on every harness invocation."""
    temporary = destination.with_name(destination.name + "." + uuid.uuid4().hex + ".part")
    try:
        with zipfile.ZipFile(temporary, "x", compression=zipfile.ZIP_STORED) as archive:
            entries = [(file.relative_to(classes).as_posix(), file)
                       for file in classes.rglob("*.class")]
            # Windows Path comparison is case-insensitive. Sort on the POSIX
            # member names' UTF-8 bytes to preserve *identical* ordering.
            entries.sort(key=lambda item: item[0].encode("utf-8"))
            folded = [name.casefold() for name, _ in entries]
            if len(folded) != len(set(folded)):
                raise ValueError("ambiguous case-insensitive control class names")
            for name, class_file in entries:
                # ZipFile.write includes host timestamps and platform metadata.
                # Serialize a canonical member header and its exact class bytes.
                entry = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
                entry.compress_type = zipfile.ZIP_STORED
                entry.create_system = 3
                entry.external_attr = 0o100644 << 16
                archive.writestr(entry, class_file.read_bytes())
        os.replace(temporary, destination)
    finally:
        temporary.unlink(missing_ok=True)


def run_profile(profile: dict, work: Path, agent: Path, compiler: Path,
                lz4_helper: Path, source_sha: str, evidence_dir: Path = OUT) -> dict:
    wanted = set(profile["modules"])
    profile_root = work / profile["profileId"]
    profile_root.mkdir(parents=True, exist_ok=True)
    if os.name == "nt":
        # Give Users an inheritable read grant on a disposable parent to prove
        # captures do not inherit it. Never use a real game/evidence folder.
        subprocess.run([windows_system_icacls(), str(profile_root), "/grant",
                        "*S-1-5-32-545:(OI)(CI)R"], check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
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
            fetch(url, path, item["sha256"], expected_size=item["size"])
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
            fetch(item["url"], path, item["sha1"], algorithm="sha1", expected_size=item["size"])
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
    fetch(helper["url"], lz4_helper, helper["sha256"])
    if hash_file(lz4_helper, "sha256") != helper["sha256"]:
        raise SystemExit("pinned test-only LZ4 helper SHA-256 mismatch")
    artifacts.append(lz4_helper)

    source = HERE / "src/test/java/dev/skyrolly/issue45/ControlMain.java"
    compile_cp = os.pathsep.join(str(path) for path in artifacts)
    control_jar = profile_root / "issue45-synthetic-control.jar"
    compile_control_jar(profile_root, compiler, source, compile_cp, control_jar)

    config = profile_root / "control.properties"
    report = profile_root / ("control-" + uuid.uuid4().hex + ".jsonl")
    config.write_text("\n".join([
        "output=" + report.as_posix(), "minecraftVersion=" + profile["minecraftVersion"],
        "distribution=synthetic", "launcher=local-control", "sourceSha=" + source_sha, "",
    ]), encoding="utf-8")
    # The initializer produces callbacks from the fresh, hash-verifiable JAR.
    # Old compiler output is neither reused nor included in this classpath.
    if os.name == "nt":
        # A fake executable in the untrusted working directory must never be
        # used by the real agent; its presence detects unsafe executable lookup.
        fake = profile_root / "icacls.exe"
        java_launcher = shutil.which("java")
        if java_launcher is None:
            raise SystemExit("Java launcher is missing for Windows executable-path test")
        shutil.copyfile(java_launcher, fake)
    run_cp = os.pathsep.join([str(control_jar)] + [str(path) for path in artifacts])
    command = ["java", "-DaccessToken=synthetic-secret-must-not-appear",
               "-Dsession:synthetic-secret-must-not-appear",
               "-Dserver=play.example.invalid:25565",
               "-Dusername=synthetic-player-identifier",
               "-DapiKey=synthetic-unrecognized-api-key-must-not-appear",
               "-javaagent:" + str(agent) + "=" + str(config), "-classpath", run_cp,
               "dev.skyrolly.issue45.ControlMain"]
    completed = subprocess.run(command, cwd=profile_root, text=True, capture_output=True, timeout=90)
    (profile_root / "control.stdout.txt").write_text(completed.stdout, encoding="utf-8")
    (profile_root / "control.stderr.txt").write_text(completed.stderr, encoding="utf-8")
    if completed.returncode != 0:
        raise SystemExit("synthetic process failed for " + profile["profileId"] + "; inspect private work-dir logs")

    raw_bytes = report.read_bytes()
    if b"\r\n" in raw_bytes:
        raise SystemExit("diagnostic JSONL must use LF on every platform")
    if os.name == "posix" and stat.S_IMODE(report.stat().st_mode) & 0o077:
        raise SystemExit("diagnostic JSONL is accessible to non-owner users")
    if os.name == "nt":
        # icacls emits the host OEM encoding, not necessarily UTF-8. The ACL
        # markers being checked are ASCII bytes on every Windows locale.
        acl = subprocess.run([windows_system_icacls(), str(report)], check=True,
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if (b"(I)" in acl.stdout or b"BUILTIN\\Users" in acl.stdout
                or b"S-1-5-32-545" in acl.stdout):
            raise SystemExit("diagnostic JSONL inherited a non-owner Windows read grant")
    events = validate_control_privacy(raw_bytes.decode("utf-8"))
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
    snapshots = {event.get("channel_fingerprint"): event for event in events
                 if event.get("event") == "channel_active_pipeline_snapshot"}
    by_name = {event.get("handler_name"): event for event in added}
    for name, class_name in EXPECTED_CONTROLS.items():
        if name not in by_name or by_name[name].get("handler_class") != class_name:
            raise SystemExit("pipeline control mismatch for " + name + " in " + profile["profileId"])
    # The positive and negative decoder controls must exist in activation
    # snapshots, not just in post-activation handler callbacks.
    for name, class_name in EXPECTED_CONTROLS.items():
        channel = by_name[name].get("channel_fingerprint")
        snapshot = snapshots.get(channel)
        if not snapshot or not any(handler.get("handler_name") == name
                                   and handler.get("handler_class") == class_name
                                   for handler in snapshot.get("pipeline_handlers", [])):
            raise SystemExit("pre-activation pipeline snapshot control missing: " + name)
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
    raw_destination = evidence_dir / raw_name
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


def prepare_fresh_evidence_dir(source: Path, destination: Path) -> Path:
    """Copy retained non-synthetic evidence, never reuse a prior capture."""
    source = source.resolve()
    destination = destination.resolve()
    if destination.is_relative_to(source):
        raise ValueError("fresh evidence directory must be outside the retained archive")
    # copytree refuses an existing destination. Do not overwrite a historical
    # archive or allow old synthetic observations to satisfy a fresh run.
    shutil.copytree(source, destination, ignore=shutil.ignore_patterns(
        "synthetic-control-verification.json", "synthetic-control-observation-*.jsonl"))
    return destination


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--work-dir", required=True, type=Path)
    parser.add_argument("--fresh-evidence-dir", type=Path,
                        help="Create a new archive copy without old synthetic results and write fresh controls there")
    args = parser.parse_args()
    evidence_dir = (prepare_fresh_evidence_dir(OUT, args.fresh_evidence_dir.resolve())
                    if args.fresh_evidence_dir is not None else OUT)
    work = args.work_dir.resolve()
    work.mkdir(parents=True, exist_ok=True)
    CACHE.mkdir(parents=True, exist_ok=True)
    for key in ("compiler", "byteBuddy"):
        dependency = LOCK[key]
        filename = dependency["url"].rsplit("/", 1)[-1]
        path = CACHE / filename
        fetch(dependency["url"], path, dependency["sha256"])
        if hash_file(path, "sha256") != dependency["sha256"]:
            raise SystemExit(key + " dependency SHA-256 mismatch")
    helper_path = CACHE / "lz4-java-1.8.0.jar"
    agent = work / "issue45-runtime-agent.jar"
    subprocess.run([sys.executable, str(HERE / "build_agent.py"), "--output", str(agent)], check=True)
    source_sha = subprocess.check_output(["git", "-C", str(REPO), "rev-parse", "HEAD"], text=True).strip()
    profiles = [run_profile(profile, work, agent, CACHE / "ecj-3.39.0.jar", helper_path, source_sha, evidence_dir)
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
    summary = evidence_dir / "synthetic-control-verification.json"
    summary.parent.mkdir(parents=True, exist_ok=True)
    summary.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
