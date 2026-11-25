#!/usr/bin/env python3
"""Benign synthetic SPDY class-definition observation, not Minecraft runtime evidence."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
from urllib.request import HTTPRedirectHandler, Request, build_opener
import zipfile

HERE = Path(__file__).resolve().parent
MANIFESTS = HERE.parents[1] / "docs/dependency-evidence/issue45-netty-lz4-high-2026-11-23/minecraft-version-manifests"
BASE = "https://libraries.minecraft.net/"
# Exact retained manifest and previously verified HTTP JAR / class-resource digests.
PROFILES = (
    ("1.21.9", "4.1.118.Final", "f0ae1c9a783936a4ef74b9ed67331a02968ece56474d19ef688e70d0b79d1b9b",
     "09822d785e9a794838031ddd5346cf419b30c036a981c2e277a062bea884174b",
     "81553438a8910a59987303dbeb7cd3ffd937f67047156be4b9d9a75bb38bccd2"),
    ("1.21.11", "4.2.7.Final", "81beb15f8d4d8e0f2ccad98d26c5aeedb833900272c65e7af10865dc96c508ad",
     "2984dd38420a61c4dd68fcacc51ffc528eb46f73f7795cdafdb3a4d6fcb76862",
     "7ac11efef74909703dcaee3b4850ec409aea79ffa248a7239b97b32f7e27c789"),
    ("26.2", "4.2.15.Final", "d70731076a9cf064b7b9f154acc1a4b584a85c46f2e5acdd3eb475f75b90537a",
     "76ae57e87af37b3c4107140f50b9244b1456163a6a225510838f7c5a4458ec22",
     "05fec9bb4b25f5ebd60e169538383abe8f92310bd09d554e6585df4a2fb4920b"),
)
HTTP = "netty-codec-http"


class ProbeError(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise ProbeError(message)


def sha256(raw):
    return hashlib.sha256(raw).hexdigest()


def modules(version):
    common = (HTTP, "netty-common", "netty-buffer", "netty-transport", "netty-resolver", "netty-handler")
    return common + (("netty-codec",) if version.startswith("4.1.") else
                     ("netty-codec-base", "netty-codec-compression"))


def catalog(raw, profile):
    game, version, pin, _, _ = profile
    require(sha256(raw) == pin, "retained manifest digest mismatch")
    manifest = json.loads(raw)
    require(manifest["id"] == game, "manifest game mismatch")
    items = {}
    for name in modules(version):
        coordinate = f"io.netty:{name}:{version}"
        matches = [item for item in manifest["libraries"] if item["name"] == coordinate]
        require(len(matches) == 1 and matches[0].get("rules") is None, "ambiguous or conditional library")
        item = matches[0]["downloads"]["artifact"]
        path = f"io/netty/{name}/{version}/{name}-{version}.jar"
        require(item["path"] == path and item["url"] == BASE + path, "unexpected library location")
        size, sha1 = item["size"], item["sha1"]
        require(type(size) is int and 0 < size <= 2 * 1024 * 1024, "unexpected library size")
        require(isinstance(sha1, str) and len(sha1) == 40 and all(c in "0123456789abcdef" for c in sha1),
                "invalid library digest")
        items[name] = item
    return items


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def download(item):
    request = Request(item["url"], headers={"User-Agent": "issue45-spdy-class-probe/1"})
    with build_opener(NoRedirect()).open(request, timeout=45) as response:
        require(response.geturl() == item["url"], "unexpected library origin")
        return response.read(item["size"] + 1)


def acquire(items, directory, expected_http, fetch=download):
    paths, hashes = {}, {}
    for name, item in items.items():
        raw = fetch(item)
        require(len(raw) == item["size"] and hashlib.sha1(raw).hexdigest() == item["sha1"],
                "library size or SHA-1 mismatch")
        hashes[name] = sha256(raw)
        if name == HTTP:
            require(hashes[name] == expected_http, "HTTP JAR differs from retained SHA-256")
        path = directory / (name + ".jar")
        with path.open("xb") as stream:
            stream.write(raw)
        with zipfile.ZipFile(path) as jar:
            names = jar.namelist()
            require(len(names) == len(set(names)), "duplicate library ZIP members")
            if "META-INF/MANIFEST.MF" in names:
                info = jar.getinfo("META-INF/MANIFEST.MF")
                require(info.file_size <= 65536, "library manifest too large")
                require(not any(line.lower().startswith(b"class-path:") for line in jar.read(info).splitlines()),
                        "library manifest extends the isolated classpath")
        paths[name] = path
    return paths, hashes


def java_environment():
    env = dict(os.environ)
    for name in ("JAVA_TOOL_OPTIONS", "JDK_JAVA_OPTIONS", "_JAVA_OPTIONS", "CLASSPATH"):
        env.pop(name, None)
    return env


def observe(java, paths, jar_hash, class_hash, directory):
    args = [str(java), str(HERE / "SpdyClassProbe.java"), str(paths[HTTP]), jar_hash, class_hash]
    args += [str(path) for name, path in paths.items() if name != HTTP]
    result = subprocess.run(args, cwd=directory, env=java_environment(), capture_output=True,
                            text=True, check=True, timeout=60)
    expected = {"negative": "class_not_found", "positive": "defined_by_isolated_url_loader",
                "code_source_sha256": jar_hash, "class_resource_sha256": class_hash}
    require(result.stdout.splitlines() == [f"{k}={v}" for k, v in expected.items()],
            "unexpected JVM observation output")
    return expected


def source_identity():
    root = HERE.parents[1]
    checkout = subprocess.check_output(["git", "rev-parse", "--verify", "HEAD"], cwd=root,
                                       stderr=subprocess.DEVNULL, text=True).strip()
    hashes = {}
    for name in ("probe.py", "SpdyClassProbe.java"):
        path = HERE / name
        require(path.resolve() == path, "unexpected probe source location")
        relative = path.relative_to(root).as_posix()
        raw = path.read_bytes()
        committed = subprocess.check_output(["git", "cat-file", "blob", checkout + ":" + relative],
                                            cwd=root, stderr=subprocess.DEVNULL)
        require(raw == committed, "probe source differs from HEAD: " + relative)
        hashes[relative] = sha256(raw)
    return checkout, hashes


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--java", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        require(args.java.is_absolute() and args.java.is_file(), "absolute Java executable required")
        require(not args.output.exists(), "refusing to overwrite report")
        identity = source_identity()
        # Validate all three manifests before network acquisition.
        catalogs = [(profile, catalog((MANIFESTS / (profile[0] + ".json")).read_bytes(), profile))
                    for profile in PROFILES]
        version = subprocess.run([str(args.java), "-version"], env=java_environment(), capture_output=True,
                                 text=True, check=True, timeout=15).stderr.strip()
        require(bool(version), "missing Java version")
        observations = []
        with tempfile.TemporaryDirectory(prefix="issue45-spdy-class-") as temporary:
            for profile, items in catalogs:
                game, netty, pin, jar_hash, class_hash = profile
                directory = Path(temporary) / game
                directory.mkdir()
                paths, hashes = acquire(items, directory, jar_hash)
                require(source_identity() == identity, "probe sources changed during acquisition")
                result = observe(args.java, paths, jar_hash, class_hash, directory)
                observations.append({"representative_manifest": game, "manifest_sha256": pin, "netty": netty,
                                     "library_sha256": hashes, **result})
        require(source_identity() == identity, "probe sources changed during observation")
        report = {"checkout": identity[0], "source_sha256": identity[1], "schema": "issue45-spdy-class-control/v1", "scope": "synthetic_noninitializing_class_definition_only",
                  "java_version": version, "observations": observations, "pipeline_observed": False,
                  "runtime_reachability": "not_established", "risk_accepted": False, "release_blocking": True}
        raw = (json.dumps(report, indent=2, sort_keys=True) + "\n").encode("utf-8")
        with args.output.open("xb") as stream:
            stream.write(raw)
        print(json.dumps({"report_sha256": sha256(raw), "observations": observations, "result": "pass"}, sort_keys=True))
    except ProbeError as error:
        parser.exit(1, "SPDY class control failed: " + str(error) + "\n")
    except (OSError, ValueError, KeyError, TypeError, zipfile.BadZipFile, subprocess.SubprocessError):
        parser.exit(1, "SPDY class control failed: input, acquisition or JVM unavailable\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
