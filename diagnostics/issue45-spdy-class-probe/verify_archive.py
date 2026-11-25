#!/usr/bin/env python3
"""Verify the original retained SPDY report, not a report of current HEAD."""
import hashlib
import io
import json
from pathlib import Path
import zipfile

ARCHIVE = (Path(__file__).resolve().parents[2] /
           "docs/dependency-evidence/issue45-spdy-class-control-2026-11-25")
ZIP_NAME = "issue45-spdy-class-control-45652816177-1.zip"
# Reviewed original provenance blob and independently observed ZIP SHA-256.
# These pins distinguish historical evidence from a mutually edited ZIP/JSON.
PROVENANCE_BLOB = "d75b0620a97d3c719f96b533f12433e6b095869e"
ZIP_SHA256 = "a5d678a7a1aba6f2c9a6b92f1ae8354871d5c35f4b52730f9d34a186303dd13e"
CHECKOUT = "ddb6354c9ac9a68d7ec8ce4dd367c8ca7df1697f"


def require(condition, message):
    if not condition:
        raise ValueError(message)


def git_blob(raw):
    return hashlib.sha1(f"blob {len(raw)}\0".encode("ascii") + raw).hexdigest()


def verify(directory=ARCHIVE):
    provenance_bytes = (directory / "provenance.json").read_bytes()
    require(git_blob(provenance_bytes) == PROVENANCE_BLOB, "historical provenance blob mismatch")
    p = json.loads(provenance_bytes)
    a = p["archive"]
    require(a["path"] == ZIP_NAME and a["sha256"] == ZIP_SHA256, "historical archive pin mismatch")
    raw = (directory / ZIP_NAME).read_bytes()
    require(len(raw) == a["size_bytes"], "archive size mismatch")
    require(hashlib.sha256(raw).hexdigest() == ZIP_SHA256, "archive digest mismatch")
    require(git_blob(raw) == a["git_blob"], "archive Git blob mismatch")
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        require(archive.namelist() == [a["json_member"]], "unexpected members")
        require(archive.getinfo(a["json_member"]).file_size == a["json_size_bytes"], "JSON size mismatch")
        require(archive.testzip() is None, "CRC mismatch")
        report_bytes = archive.read(a["json_member"])
    require(len(report_bytes) == a["json_size_bytes"], "JSON size mismatch")
    require(hashlib.sha256(report_bytes).hexdigest() == a["json_sha256"], "JSON digest mismatch")
    report = json.loads(report_bytes)
    require(report["schema"] == "issue45-spdy-class-control/v1", "report schema mismatch")
    require(report["checkout"] == CHECKOUT, "historical checkout mismatch")
    for key in ("checkout", "source_sha256", "scope", "pipeline_observed",
                "runtime_reachability", "risk_accepted", "release_blocking"):
        require(report[key] == p[key], "report mismatch: " + key)
    require(report["pipeline_observed"] is False and report["risk_accepted"] is False
            and report["release_blocking"] is True
            and report["runtime_reachability"] == "not_established"
            and report["scope"] == "synthetic_noninitializing_class_definition_only",
            "historical evidence scope mismatch")
    observations = report["observations"]
    require(len(observations) == p["observations"] == 3, "observation count mismatch")
    require(sum(len(o["library_sha256"]) for o in observations) == p["library_count"] == 23,
            "library count mismatch")
    for observation in observations:
        require(observation["positive"] == "defined_by_isolated_url_loader", "positive control mismatch")
        require(observation["negative"] == "class_not_found", "negative control mismatch")
        require(observation["library_sha256"]["netty-codec-http"] == observation["code_source_sha256"],
                "HTTP code-source digest mismatch")
    return report


if __name__ == "__main__":
    report = verify()
    print("Verified original retained SPDY archive at historical checkout " + report["checkout"])
