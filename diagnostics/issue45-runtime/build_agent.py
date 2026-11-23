#!/usr/bin/env python3
"""Build the opt-in Issue 45 javaagent from pinned source and Byte Buddy."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
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


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--cache-dir", type=Path, default=Path.home() / ".cache/issue45-runtime")
    args = parser.parse_args()
    lock = json.loads(LOCK.read_text(encoding="utf-8"))
    dependency = lock["byteBuddy"]
    cache = args.cache_dir.expanduser().resolve()
    cache.mkdir(parents=True, exist_ok=True)
    byte_buddy = cache / "byte-buddy-1.14.18.jar"
    if not byte_buddy.exists():
        request = urllib.request.Request(dependency["url"], headers={"User-Agent": "issue45-runtime-diagnostic/1"})
        with urllib.request.urlopen(request, timeout=60) as response, byte_buddy.open("wb") as target:
            shutil.copyfileobj(response, target)
    if digest(byte_buddy) != dependency["sha256"]:
        raise SystemExit("Byte Buddy SHA-256 does not match dependencies.lock.json")
    compiler_dep = lock["compiler"]
    ecj = cache / "ecj-3.39.0.jar"
    if not ecj.exists():
        request = urllib.request.Request(compiler_dep["url"], headers={"User-Agent": "issue45-runtime-diagnostic/1"})
        with urllib.request.urlopen(request, timeout=60) as response, ecj.open("wb") as target:
            shutil.copyfileobj(response, target)
    if digest(ecj) != compiler_dep["sha256"]:
        raise SystemExit("ECJ SHA-256 does not match dependencies.lock.json")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="issue45-agent-build-") as temp:
        work = Path(temp)
        classes = work / "classes"
        classes.mkdir()
        sources = sorted((HERE / "src/main/java").rglob("*.java"))
        cmd = ["java", "-jar", str(ecj), "-encoding", "UTF-8", "-17",
               "-classpath", str(byte_buddy), "-d", str(classes)] + [str(x) for x in sources]
        subprocess.run(cmd, check=True)
        manifest = "Manifest-Version: 1.0\nPremain-Class: dev.skyrolly.issue45.Issue45Agent\nCan-Redefine-Classes: true\nCan-Retransform-Classes: true\n\n"
        def stable_write(target: zipfile.ZipFile, name: str, data: bytes) -> None:
            info = zipfile.ZipInfo(name, date_time=(2020, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            target.writestr(info, data, compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)

        with zipfile.ZipFile(args.output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as target:
            stable_write(target, "META-INF/MANIFEST.MF", manifest.encode("utf-8"))
            names = set(["META-INF/MANIFEST.MF"])
            for entry in sorted(classes.rglob("*")):
                if entry.is_file():
                    name = entry.relative_to(classes).as_posix()
                    stable_write(target, name, entry.read_bytes())
                    names.add(name)
            with zipfile.ZipFile(byte_buddy) as source:
                for item in source.infolist():
                    name = item.filename
                    if item.is_dir() or name == "META-INF/MANIFEST.MF": continue
                    if name.upper().endswith((".SF", ".RSA", ".DSA")): continue
                    if name in names: continue
                    stable_write(target, name, source.read(name))
                    names.add(name)
    print(json.dumps({"agent": str(args.output.resolve()), "sha256": digest(args.output),
                      "byte_buddy_sha256": digest(byte_buddy), "compiler_sha256": digest(ecj),
                      "compiled_sources": len(sources)}, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except subprocess.CalledProcessError as error:
        raise SystemExit(error.returncode)
