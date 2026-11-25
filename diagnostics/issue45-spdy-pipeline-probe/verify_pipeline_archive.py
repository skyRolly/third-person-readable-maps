#!/usr/bin/env python3
"""Verify the original retained synthetic pipeline report, not current HEAD."""
import hashlib
import io
import json
from pathlib import Path
import sys
import zipfile

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "issue45-spdy-class-probe"))
import verify_archive as historical

ARCHIVE = HERE.parents[1] / "docs/dependency-evidence/issue45-spdy-pipeline-control-2026-11-25"
ZIP_NAME = "issue45-spdy-pipeline-control-45674664714-1.zip"
PROVENANCE_BLOB = "b6be7a4203774678d7a889a91ae51194e42706e3"
ZIP_SHA256 = "f8953a814f1ec8f57c252387ef7dbfa9a4ab599fabb28ec72138bd55ffafb344"
CHECKOUT = "f21a88af720cf4d43890158a0f098ac3ffb1f691"


def verify(directory=ARCHIVE):
    require = historical.require
    raw_provenance = (directory / "provenance.json").read_bytes()
    require(historical.git_blob(raw_provenance) == PROVENANCE_BLOB, "pipeline provenance blob mismatch")
    p = json.loads(raw_provenance)
    a = p["archive"]
    require(a["path"] == ZIP_NAME and a["sha256"] == ZIP_SHA256, "pipeline archive pin mismatch")
    raw = (directory / ZIP_NAME).read_bytes()
    require(len(raw) == a["size_bytes"], "pipeline archive size mismatch")
    require(hashlib.sha256(raw).hexdigest() == ZIP_SHA256, "pipeline archive digest mismatch")
    require(historical.git_blob(raw) == a["git_blob"], "pipeline archive blob mismatch")
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        require(archive.namelist() == [a["json_member"]], "unexpected pipeline archive members")
        require(archive.getinfo(a["json_member"]).file_size == a["json_size_bytes"], "pipeline JSON size mismatch")
        require(archive.testzip() is None, "pipeline CRC mismatch")
        report_bytes = archive.read(a["json_member"])
    require(len(report_bytes) == a["json_size_bytes"], "pipeline JSON size mismatch")
    require(hashlib.sha256(report_bytes).hexdigest() == a["json_sha256"], "pipeline JSON digest mismatch")
    report = json.loads(report_bytes)
    require(report["schema"] == "issue45-spdy-pipeline-control/v1", "pipeline schema mismatch")
    require(report["checkout"] == CHECKOUT, "pipeline historical checkout mismatch")
    for key in ("checkout", "source_sha256", "scope", "synthetic_pipeline_observed",
                "minecraft_pipeline_observed", "frames_sent", "runtime_reachability",
                "risk_accepted", "release_blocking"):
        require(report[key] == p[key], "pipeline report mismatch: " + key)
    require(report["synthetic_pipeline_observed"] is True and report["minecraft_pipeline_observed"] is False
            and report["frames_sent"] is False and report["risk_accepted"] is False
            and report["release_blocking"] is True and report["runtime_reachability"] == "not_established"
            and report["scope"] == "synthetic_embedded_channel_handler_identity_only", "pipeline scope mismatch")
    old = historical.verify()["observations"]
    observations = report["observations"]
    require(len(observations) == len(old) == p["observations"] == 3, "pipeline observation count mismatch")
    require(sum(len(o["library_sha256"]) for o in observations) == p["library_count"] == 23,
            "pipeline library count mismatch")
    for current, original in zip(observations, old):
        for key in ("representative_manifest", "netty", "manifest_sha256", "library_sha256", "negative"):
            require(current[key] == original[key], "historical observation mismatch: " + key)
        require(current["handler_code_source_sha256"] == original["code_source_sha256"], "handler code source mismatch")
        require(current["handler_class_resource_sha256"] == original["class_resource_sha256"], "handler resource mismatch")
        require(current["pipeline_code_source_sha256"] == current["library_sha256"]["netty-transport"],
                "pipeline code source mismatch")
        require(current["handler"] == "io.netty.handler.codec.spdy.SpdyFrameCodec"
                and current["channel"] == "io.netty.channel.embedded.EmbeddedChannel"
                and current["pipeline"] == "io.netty.channel.embedded.EmbeddedChannel$EmbeddedChannelPipeline"
                and current["registration"] == "identity_matched_and_removed"
                and current["cleanup"] == "no_queued_messages", "pipeline lifecycle mismatch")
    return report


if __name__ == "__main__":
    print("Verified original retained SPDY pipeline archive at historical checkout " + verify()["checkout"])
