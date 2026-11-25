#!/usr/bin/env python3
"""Synthetic in-memory SPDY handler registration, never actual Minecraft reachability."""
import argparse
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import zipfile

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "issue45-spdy-class-probe"))
import probe as common


def source_identity():
    checkout, hashes = common.source_identity()
    root = HERE.parents[1]
    for name in ("pipeline_probe.py", "SpdyPipelineProbe.java"):
        path = HERE / name
        common.require(path.resolve() == path, "unexpected source location")
        relative = path.relative_to(root).as_posix()
        raw = path.read_bytes()
        committed = subprocess.check_output(["git", "cat-file", "blob", checkout + ":" + relative],
                                            cwd=root, stderr=subprocess.DEVNULL)
        common.require(raw == committed, "pipeline source differs from HEAD: " + relative)
        hashes[relative] = common.sha256(raw)
    return checkout, hashes


def parse_output(result, http_hash, resource_hash, transport_hash):
    lines = result.stdout.splitlines()
    pipeline_name = lines[3].removeprefix("pipeline=") if len(lines) == 9 else ""
    expected = {
        "negative": "class_not_found",
        "handler": "io.netty.handler.codec.spdy.SpdyFrameCodec",
        "channel": "io.netty.channel.embedded.EmbeddedChannel",
        "pipeline": pipeline_name,
        "registration": "identity_matched_and_removed",
        "handler_code_source_sha256": http_hash,
        "handler_class_resource_sha256": resource_hash,
        "pipeline_code_source_sha256": transport_hash,
        "cleanup": "no_queued_messages",
    }
    if (not re.fullmatch(r"io\.netty\.channel\.[A-Za-z0-9_.$]+", pipeline_name)
            or lines != [f"{k}={v}" for k, v in expected.items()]):
        raise common.ProbeError(f"unexpected pipeline observation output (exit {result.returncode}): "
                                f"{common.jvm_diagnostics(result)}")
    return expected


def observe(java, paths, hashes, class_hash, directory):
    http_hash = hashes[common.HTTP]
    transport_hash = hashes["netty-transport"]
    args = [str(java), str(HERE / "SpdyPipelineProbe.java"), str(paths[common.HTTP]),
            http_hash, class_hash, str(paths["netty-transport"]), transport_hash]
    args += [str(path) for name, path in paths.items() if name not in (common.HTTP, "netty-transport")]
    result = subprocess.run(args, cwd=directory, env=common.java_environment(), capture_output=True,
                            text=True, check=True, timeout=60)
    return parse_output(result, http_hash, class_hash, transport_hash)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--java", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        common.require(args.java.is_absolute() and args.java.is_file(), "absolute Java executable required")
        common.require(not args.output.exists(), "refusing to overwrite report")
        identity = source_identity()
        catalogs = [(p, common.catalog((common.MANIFESTS / (p[0] + ".json")).read_bytes(), p))
                    for p in common.PROFILES]
        version = subprocess.run([str(args.java), "-version"], env=common.java_environment(),
                                 capture_output=True, text=True, check=True, timeout=15).stderr.strip()
        common.require(bool(version), "missing Java version")
        observations = []
        with tempfile.TemporaryDirectory(prefix="issue45-spdy-pipeline-") as temporary:
            for profile, items in catalogs:
                game, netty, pin, jar_hash, class_hash = profile
                directory = Path(temporary) / game
                directory.mkdir()
                paths, hashes = common.acquire(items, directory, jar_hash)
                common.require(source_identity() == identity, "sources changed during acquisition")
                try:
                    result = observe(args.java, paths, hashes, class_hash, directory)
                except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as error:
                    raise common.ProbeError(f"pipeline JVM failed for {game} / {netty}: "
                                            f"{common.jvm_diagnostics(error)}") from error
                except common.ProbeError as error:
                    raise common.ProbeError(f"pipeline observation failed for {game} / {netty}: {error}") from error
                observations.append({"representative_manifest": game, "netty": netty,
                                     "manifest_sha256": pin, "library_sha256": hashes, **result})
        common.require(source_identity() == identity, "sources changed during observation")
        report = {"schema": "issue45-spdy-pipeline-control/v1", "checkout": identity[0],
                  "source_sha256": identity[1], "java_version": version,
                  "scope": "synthetic_embedded_channel_handler_identity_only",
                  "observations": observations, "synthetic_pipeline_observed": True,
                  "minecraft_pipeline_observed": False, "frames_sent": False,
                  "runtime_reachability": "not_established", "risk_accepted": False, "release_blocking": True}
        raw = (json.dumps(report, indent=2, sort_keys=True) + "\n").encode("utf-8")
        with args.output.open("xb") as stream:
            stream.write(raw)
        print(json.dumps({"result": "pass", "report_sha256": common.sha256(raw),
                          "observations": observations}, sort_keys=True))
    except common.ProbeError as error:
        parser.exit(1, "SPDY pipeline control failed: " + str(error) + "\n")
    except (OSError, ValueError, KeyError, TypeError, zipfile.BadZipFile, subprocess.SubprocessError):
        parser.exit(1, "SPDY pipeline control failed: input, acquisition or JVM unavailable\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
