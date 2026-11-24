#!/usr/bin/env python3
"""Build the opt-in Issue 45 javaagent from pinned source and Byte Buddy."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import uuid
import urllib.request
import zipfile
from pathlib import Path


HERE = Path(__file__).resolve().parent
LOCK = HERE / "dependencies.lock.json"


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def download_pinned(dependency: dict, target: Path) -> None:
    """Reuse only hash-verified cache entries; atomically publish verified downloads."""
    if target.is_file() and digest(target) == dependency["sha256"]:
        return
    if target.exists() and not target.is_file():
        raise SystemExit("dependency cache target is not a file: " + str(target))
    temporary = target.with_name(target.name + "." + uuid.uuid4().hex + ".part")
    try:
        request = urllib.request.Request(dependency["url"], headers={"User-Agent": "issue45-runtime-diagnostic/1"})
        with urllib.request.urlopen(request, timeout=60) as response, temporary.open("xb") as stream:
            shutil.copyfileobj(response, stream)
        if digest(temporary) != dependency["sha256"]:
            raise SystemExit("downloaded dependency SHA-256 does not match dependencies.lock.json")
        os.replace(temporary, target)
    finally:
        temporary.unlink(missing_ok=True)


AGENT_MANIFEST = (
    "Manifest-Version: 1.0\n"
    "Premain-Class: dev.skyrolly.issue45.Issue45Agent\n"
    "Can-Redefine-Classes: true\n"
    "Can-Retransform-Classes: true\n\n"
).encode("utf-8")


def ordered_files(root: Path, pattern: str) -> list[Path]:
    return sorted((path for path in root.rglob(pattern) if path.is_file()),
                  key=lambda path: path.relative_to(root).as_posix().encode("utf-8"))


def package_agent(classes: Path, byte_buddy: Path, destination: Path) -> dict:
    """Write canonical uncompressed JAR entries, independent of host zlib and Path ordering."""
    temporary = destination.with_name(destination.name + "." + uuid.uuid4().hex + ".part")
    compiled = {}
    members = []
    names = set()

    def stable_write(target, name, data):
        info = zipfile.ZipInfo(name, date_time=(2020, 1, 1, 0, 0, 0))
        info.compress_type = zipfile.ZIP_STORED
        info.create_system = 3
        info.external_attr = 0o100644 << 16
        target.writestr(info, data)
        names.add(name)
        members.append({"name": name, "size": len(data),
                        "sha256": hashlib.sha256(data).hexdigest()})

    try:
        with zipfile.ZipFile(temporary, "x", compression=zipfile.ZIP_STORED) as target:
            stable_write(target, "META-INF/MANIFEST.MF", AGENT_MANIFEST)
            for entry in ordered_files(classes, "*"):
                name = entry.relative_to(classes).as_posix()
                if name in names:
                    raise ValueError("compiled agent member collides with manifest")
                data = entry.read_bytes()
                stable_write(target, name, data)
                compiled[name] = hashlib.sha256(data).hexdigest()
            with zipfile.ZipFile(byte_buddy) as source:
                # The pinned dependency's member order is already byte-bound;
                # explicitly canonicalize it too. Preserve compiled-class
                # precedence and the original signature exclusion policy.
                for item in sorted(source.infolist(), key=lambda i: i.filename.encode("utf-8")):
                    name = item.filename
                    if item.is_dir() or name == "META-INF/MANIFEST.MF":
                        continue
                    if name.upper().endswith((".SF", ".RSA", ".DSA")):
                        continue
                    if name in names:
                        continue
                    stable_write(target, name, source.read(item))
        os.replace(temporary, destination)
    finally:
        temporary.unlink(missing_ok=True)
    return {
        "compiled_member_sha256": compiled,
        "archive_member_count": len(members),
        "ordered_member_inventory_sha256": hashlib.sha256(
            json.dumps(members, ensure_ascii=True, sort_keys=True,
                       separators=(",", ":")).encode("ascii")).hexdigest(),
        "compression": "stored",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--cache-dir", type=Path, default=Path.home() / ".cache/issue45-runtime")
    args = parser.parse_args()
    lock = json.loads(LOCK.read_text(encoding="utf-8"))
    dependency = lock["byteBuddy"]
    cache = args.cache_dir.expanduser().resolve()
    cache.mkdir(parents=True, exist_ok=True)
    byte_buddy = cache / dependency["url"].rsplit("/", 1)[-1]
    download_pinned(dependency, byte_buddy)
    if digest(byte_buddy) != dependency["sha256"]:
        raise SystemExit("Byte Buddy SHA-256 does not match dependencies.lock.json")
    compiler_dep = lock["compiler"]
    ecj = cache / "ecj-3.39.0.jar"
    download_pinned(compiler_dep, ecj)
    if digest(ecj) != compiler_dep["sha256"]:
        raise SystemExit("ECJ SHA-256 does not match dependencies.lock.json")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="issue45-agent-build-") as temp:
        work = Path(temp)
        classes = work / "classes"
        classes.mkdir()
        source_root = HERE / "src/main/java"
        sources = ordered_files(source_root, "*.java")
        cmd = ["java", "-jar", str(ecj), "-encoding", "UTF-8", "-17",
               "-classpath", str(byte_buddy), "-d", str(classes)] + [str(x) for x in sources]
        source_digests = {x.relative_to(source_root).as_posix(): digest(x) for x in sources}
        subprocess.run(cmd, check=True)
        inventory = package_agent(classes, byte_buddy, args.output)
    print(json.dumps({"agent": str(args.output.resolve()), "sha256": digest(args.output),
                      "byte_buddy_sha256": digest(byte_buddy), "compiler_sha256": digest(ecj),
                      "compiled_sources": len(sources), "source_sha256": source_digests,
                      "python_version": sys.version.split()[0],
                      "compiler_flags": ["-encoding", "UTF-8", "-17"],
                      "build_inventory": inventory}, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except subprocess.CalledProcessError as error:
        raise SystemExit(error.returncode)
