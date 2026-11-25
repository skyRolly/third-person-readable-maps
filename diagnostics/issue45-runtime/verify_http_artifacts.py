#!/usr/bin/env python3
"""Verify retained manifest-bound HTTP codec JARs without loading or executing classes."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MANIFESTS = ROOT / "docs/dependency-evidence/issue45-netty-lz4-high-2026-11-23/minecraft-version-manifests"
# Seven official manifests, four retained advisory occurrences, three distinct JARs.
# Source identities are the selected product heads, not the coordinator checkout.
GROUPS = (
    ("1.21.9-1.21.10", "5dd5d433fd785bf51f13827babf51a76d09f7cdb", "4.1.118.Final", ("1.21.9", "1.21.10")),
    ("1.21.11", "ec61f4cf3c6d72558c35e919bf865fa9b51bf0d1", "4.2.7.Final", ("1.21.11",)),
    ("26.1-26.2", "b7620ef8174180698cc36d273981aeadd3447941", "4.2.7.Final", ("26.1", "26.1.1", "26.1.2")),
    ("26.1-26.2", "b7620ef8174180698cc36d273981aeadd3447941", "4.2.15.Final", ("26.2",)),
)
MANIFEST_SHA256 = {
    "1.21.9": "f0ae1c9a783936a4ef74b9ed67331a02968ece56474d19ef688e70d0b79d1b9b",
    "1.21.10": "3eba1197d417ce4ec5c7a0e3cb326b47ea291f2351161333878ec512ce1ca651",
    "1.21.11": "81beb15f8d4d8e0f2ccad98d26c5aeedb833900272c65e7af10865dc96c508ad",
    "26.1": "9ee99d30a7efca85e33866231625474be36456dfbafc0bbc010db9ec08a4ca96",
    "26.1.1": "95527a36610fc96ddc0bfb542f9e2a0daf60d8e42373873627fadc7e9dea0938",
    "26.1.2": "dc1ed85ddf2d778d745d960f7176f692c2ba8deb13a1b333d170ffa06aaabae7",
    "26.2": "d70731076a9cf064b7b9f154acc1a4b584a85c46f2e5acdd3eb475f75b90537a",
}
PREFIX = "io/netty/handler/codec/spdy/"


class VerificationError(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise VerificationError(message)


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def manifest_artifact(raw, game, netty):
    require(sha256(raw) == MANIFEST_SHA256[game], "retained manifest digest mismatch")
    manifest = json.loads(raw)
    require(manifest["id"] == game, "manifest game identity mismatch")
    entries = [item for item in manifest["libraries"]
               if item["name"].startswith("io.netty:netty-codec-http:")]
    coordinate = "io.netty:netty-codec-http:" + netty
    require(len(entries) == 1 and entries[0]["name"] == coordinate and not entries[0].get("rules"),
            "unexpected HTTP codec selection")
    item = entries[0]["downloads"]["artifact"]
    relative = f"io/netty/netty-codec-http/{netty}/netty-codec-http-{netty}.jar"
    require(item["path"] == relative and item["url"] == "https://libraries.minecraft.net/" + relative,
            "unexpected HTTP artifact path or origin")
    require(re.fullmatch(r"[0-9a-f]{40}", item["sha1"]) and type(item["size"]) is int
            and 0 < item["size"] <= 2 * 1024 * 1024, "invalid HTTP artifact identity")
    return {"coordinate": coordinate, "path": relative, "url": item["url"],
            "sha1": item["sha1"], "size_bytes": item["size"]}


def inspect_jar(raw, expected):
    require(len(raw) == expected["size_bytes"] and hashlib.sha1(raw).hexdigest() == expected["sha1"],
            "HTTP artifact size or SHA-1 mismatch")
    import io
    with zipfile.ZipFile(io.BytesIO(raw)) as jar:
        names = jar.namelist()
        require(len(names) == len(set(names)), "duplicate JAR member")
        classes = sorted(name for name in names if name.startswith(PREFIX) and name.endswith(".class"))
        require(PREFIX + "SpdyFrameCodec.class" in classes, "SPDY class inventory incomplete")
        require(len(classes) <= 512 and sum(jar.getinfo(name).file_size for name in classes) <= 16 * 1024 * 1024,
                "SPDY class inventory exceeds bounds")
        inventory = {}
        for name in classes:
            require(re.fullmatch(r"[A-Za-z0-9_$/]+\.class", name), "unexpected SPDY class member name")
            data = jar.read(name)
            require(data.startswith(b"\xca\xfe\xba\xbe"), "invalid class header")
            inventory[name] = sha256(data)
    return dict(expected, observed_sha256=sha256(raw), spdy_class_sha256=inventory)


def verify(manifests, libraries):
    artifacts, occurrences = {}, []
    for group, source, netty, games in GROUPS:
        for game in games:
            expected = manifest_artifact((manifests / (game + ".json")).read_bytes(), game, netty)
            coordinate = expected["coordinate"]
            if coordinate not in artifacts:
                with (libraries / expected["path"]).open("rb") as stream:
                    raw = stream.read(expected["size_bytes"] + 1)
                artifacts[coordinate] = inspect_jar(raw, expected)
            else:
                require(all(artifacts[coordinate][key] == value for key, value in expected.items()),
                        "conflicting artifact identities across manifests")
        occurrences.append({"group": group, "source_commit": source, "coordinate": coordinate,
                            "manifest_sha256_by_game": {game: MANIFEST_SHA256[game] for game in games}})
    return {"schema": "issue45-http-artifact-observation/v1", "advisory": "GHSA-6jqx-86gh-f27w",
            "scope": "static_artifact_identity_and_class_inventory_only", "occurrences": occurrences,
            "artifacts": artifacts, "runtime_reachability": "not_established",
            "risk_accepted": False, "release_blocking": True}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--libraries-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        report = verify(MANIFESTS, args.libraries_root)
        with args.output.open("x", encoding="utf-8") as stream:
            json.dump(report, stream, indent=2, sort_keys=True)
            stream.write("\n")
    except VerificationError as error:
        parser.exit(1, "HTTP artifact verification failed: " + str(error) + "\n")
    except (OSError, ValueError, KeyError, TypeError, zipfile.BadZipFile, RuntimeError):
        parser.exit(1, "HTTP artifact verification failed: invalid or unavailable input/output\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
