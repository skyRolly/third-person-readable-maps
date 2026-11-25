#!/usr/bin/env python3
"""Collect and compare fresh compiled diagnostic build identities, not runtime captures."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import zipfile
from pathlib import Path

SCHEMA = "issue45-compiled-build-identity/v1"
SYSTEMS = {"ubuntu-latest": "Linux", "windows-latest": "Windows"}
MAJORS = (21, 25)
PROFILE_IDS = ("mc-1.19-netty-4.1.77", "mc-26.2-netty-4.2.15",
               "upstream-netty-4.1.137", "upstream-netty-4.2.17")
HEX = re.compile(r"[0-9a-f]{64}\Z")


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def canonical_digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=True,
                                     separators=(",", ":")).encode("ascii")).hexdigest()


def archive_identity(path, agent=False):
    with zipfile.ZipFile(path) as archive:
        entries = archive.infolist()
        require(bool(entries), "empty compiled archive")
        require(len({e.filename for e in entries}) == len(entries), "duplicate archive member")
        members = [{"name": e.filename, "size": e.file_size,
                    "sha256": hashlib.sha256(archive.read(e)).hexdigest()} for e in entries]
    compiled = [m for m in members if m["name"].endswith(".class") and
                (not agent or m["name"].startswith("dev/skyrolly/issue45/"))]
    require(bool(compiled), "missing compiled class members")
    require(agent or len(compiled) == len(members), "unexpected non-class control member")
    return {"jar_sha256": digest(path), "member_count": len(members),
            "ordered_inventory_sha256": canonical_digest(members),
            "compiled_count": len(compiled), "compiled_sha256": canonical_digest(compiled)}


def context():
    checkout, run, attempt = (os.environ[k] for k in
                             ("GITHUB_SHA", "GITHUB_RUN_ID", "GITHUB_RUN_ATTEMPT"))
    require(re.fullmatch(r"[0-9a-f]{40}", checkout), "invalid workflow checkout")
    require(all(re.fullmatch(r"[1-9][0-9]*", v) for v in (run, attempt)), "invalid run identity")
    actual = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    require(actual == checkout, "checkout does not match workflow SHA")
    return checkout, run, attempt


def classpath_identity(profile, root, controls):
    lock, repo, cache = controls.LOCK, controls.REPO, controls.CACHE
    wanted = set(profile["modules"])
    selected, hashes = set(), []
    if profile.get("artifactLockPath"):
        source = repo / profile["artifactLockPath"]
        require(digest(source) == profile["artifactLockSha256"], "candidate lock mismatch")
        items = json.loads(source.read_text(encoding="utf-8"))["profiles"][profile["artifactLockName"]]
        for item in items:
            module, version = item["module"], profile["expectedNettyVersion"]
            path = root / f"io/netty/{module}/{version}/{module}-{version}.jar"
            require(path.stat().st_size == item["size"] and digest(path) == item["sha256"],
                    "candidate classpath identity mismatch")
            require(module not in selected, "duplicate classpath module")
            selected.add(module)
            hashes.append(digest(path))
    else:
        source = repo / profile["manifestPath"]
        require(digest(source) == profile["manifestSha256"], "manifest mismatch")
        for library in json.loads(source.read_text(encoding="utf-8"))["libraries"]:
            parts = library.get("name", "").split(":")
            if len(parts) != 3 or parts[0] != "io.netty" or parts[1] not in wanted:
                continue
            item = library["downloads"]["artifact"]
            path = root / item["path"]
            require(path.stat().st_size == item["size"] and
                    controls.hash_file(path, "sha1") == item["sha1"], "official classpath identity mismatch")
            require(parts[1] not in selected, "duplicate classpath module")
            selected.add(parts[1])
            hashes.append(digest(path))
    require(selected == wanted, "incomplete classpath")
    helper = cache / "lz4-java-1.8.0.jar"
    require(digest(helper) == lock["syntheticLz4Helper"]["sha256"], "helper mismatch")
    return hashes + [digest(helper)]


def collect(work, major, system):
    import run_controls as controls
    checkout, run, attempt = context()
    require(os.environ.get("RUNNER_OS") == SYSTEMS[system], "runner OS mismatch")
    process = subprocess.run(["java", "-XshowSettings:properties", "-version"],
                             capture_output=True, text=True, check=True)
    match = re.search(r"^\s*java\.runtime\.version = ([^\s]+)$", process.stderr, re.M)
    require(match and match[1].split(".", 1)[0] == str(major), "runtime Java major mismatch")
    lock, cache, here = controls.LOCK, controls.CACHE, controls.HERE
    inputs = {}
    for key in ("compiler", "byteBuddy"):
        pin = lock[key]
        path = cache / pin["url"].rsplit("/", 1)[-1]
        require(digest(path) == pin["sha256"], "pinned build dependency mismatch")
        inputs[key] = digest(path)
    source_root = here / "src/main/java"
    sources = {p.relative_to(source_root).as_posix(): digest(p) for p in source_root.rglob("*.java")}
    require(bool(sources), "missing agent source files")
    inputs["agent_sources"] = canonical_digest(sources)
    inputs["control_source"] = digest(here / "src/test/java/dev/skyrolly/issue45/ControlMain.java")
    inputs["lock"] = digest(here / "dependencies.lock.json")
    require(tuple(p["profileId"] for p in lock["syntheticProfiles"]) == PROFILE_IDS,
            "unexpected profile matrix")
    profiles = {}
    for profile in lock["syntheticProfiles"]:
        name = profile["profileId"]
        root = work / name
        profiles[name] = {"archive": archive_identity(root / "issue45-synthetic-control.jar"),
                          "classpath": classpath_identity(profile, root / "dependencies", controls)}
    return {"schema": SCHEMA, "checkout": checkout, "run": run, "attempt": attempt,
            "os": system, "java_major": major, "java_runtime": match[1],
            "python_version": sys.version.split()[0], "inputs": inputs,
            "agent": archive_identity(work / "issue45-runtime-agent.jar", agent=True),
            "profiles": profiles}


def strict_json(path):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            require(key not in result, "duplicate JSON key")
            result[key] = value
        return result
    return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=unique)


def valid_hash(value):
    return isinstance(value, str) and HEX.fullmatch(value) is not None


def validate_archive(value):
    require(isinstance(value, dict) and set(value) == {"jar_sha256", "member_count",
            "ordered_inventory_sha256", "compiled_count", "compiled_sha256"}, "invalid archive fields")
    require(all(valid_hash(value[k]) for k in ("jar_sha256", "ordered_inventory_sha256", "compiled_sha256")),
            "invalid archive digest")
    require(all(type(value[k]) is int and value[k] > 0 for k in ("member_count", "compiled_count")) and
            value["compiled_count"] <= value["member_count"], "invalid archive counts")


def compare(root, checkout, run, attempt):
    expected_dirs = {f"issue45-build-{run}-{attempt}-{system}" for system in SYSTEMS}
    require({p.name for p in root.iterdir()} == expected_dirs, "missing or unexpected OS reports")
    reports = {}
    for system in SYSTEMS:
        folder = root / f"issue45-build-{run}-{attempt}-{system}"
        require({p.name for p in folder.iterdir()} == {f"identity-j{m}.json" for m in MAJORS},
                "missing or unexpected Java reports")
        for major in MAJORS:
            value = strict_json(folder / f"identity-j{major}.json")
            require(isinstance(value, dict) and set(value) == {"schema", "checkout", "run", "attempt",
                    "os", "java_major", "java_runtime", "python_version", "inputs", "agent", "profiles"},
                    "invalid report fields")
            require((value["schema"], value["checkout"], value["run"], value["attempt"],
                     value["os"], value["java_major"]) == (SCHEMA, checkout, run, attempt, system, major)
                    and type(value["java_major"]) is int, "report context mismatch")
            require(isinstance(value["java_runtime"], str) and
                    re.fullmatch(rf"{major}\.[A-Za-z0-9.+-]+", value["java_runtime"]), "invalid Java runtime identity")
            require(isinstance(value["python_version"], str) and
                    re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", value["python_version"]), "invalid Python identity")
            inputs = value["inputs"]
            require(isinstance(inputs, dict) and set(inputs) == {"compiler", "byteBuddy", "agent_sources",
                    "control_source", "lock"} and all(valid_hash(v) for v in inputs.values()), "invalid input identities")
            validate_archive(value["agent"])
            profiles = value["profiles"]
            require(isinstance(profiles, dict) and set(profiles) == set(PROFILE_IDS), "incomplete profile matrix")
            for name, profile in profiles.items():
                require(isinstance(profile, dict) and set(profile) == {"archive", "classpath"}, "invalid profile fields")
                validate_archive(profile["archive"])
                require(profile["archive"]["compiled_count"] == profile["archive"]["member_count"],
                        "invalid control member counts")
                cp = profile["classpath"]
                require(isinstance(cp, list) and len(cp) == (8 if name in (PROFILE_IDS[1], PROFILE_IDS[3]) else 7)
                        and all(valid_hash(v) for v in cp), "invalid classpath identities")
            reports[system, major] = value
    baseline = reports["ubuntu-latest", 21]
    for (system, major), value in reports.items():
        require(value["java_runtime"] == reports["ubuntu-latest", major]["java_runtime"], "Java runtime mismatch")
        for field in ("python_version", "inputs", "agent", "profiles"):
            require(value[field] == baseline[field], f"compiled build mismatch: {system} Java {major} {field}")
    return baseline["agent"]["jar_sha256"], {name: value["archive"]["jar_sha256"]
                                             for name, value in baseline["profiles"].items()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    take = commands.add_parser("collect")
    take.add_argument("--work-dir", type=Path, required=True)
    take.add_argument("--java-major", type=int, choices=MAJORS, required=True)
    take.add_argument("--os", choices=SYSTEMS, required=True)
    take.add_argument("--output", type=Path, required=True)
    check = commands.add_parser("compare")
    check.add_argument("--reports", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "collect":
        report = collect(args.work_dir, args.java_major, args.os)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("x", encoding="utf-8") as stream:
            json.dump(report, stream, sort_keys=True)
            stream.write("\n")
    else:
        agent, profiles = compare(args.reports, *context())
        print(json.dumps({"result": "pass", "agent_builds": 4, "control_builds": 16,
                          "agent_sha256": agent, "control_sha256_by_profile": profiles}, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, OSError, KeyError, TypeError, zipfile.BadZipFile, subprocess.CalledProcessError):
        # Do not echo untrusted report strings, local paths or JVM output.
        raise SystemExit("compiled build identity collection or comparison failed")
