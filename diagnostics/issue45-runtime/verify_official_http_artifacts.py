#!/usr/bin/env python3
"""Acquire the three pinned official HTTP JARs and run the offline verifier CLI."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from types import ModuleType
from urllib.request import HTTPRedirectHandler, Request, build_opener


class VerificationError(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise VerificationError(message)


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def catalog(http, manifests):
    artifacts = {}
    for _, _, netty, games in http.GROUPS:
        for game in games:
            item = http.manifest_artifact((manifests / (game + ".json")).read_bytes(), game, netty)
            coordinate = item["coordinate"]
            http.require(coordinate not in artifacts or artifacts[coordinate] == item,
                         "conflicting artifact identities across manifests")
            artifacts[coordinate] = item
    http.require(len(artifacts) == 3, "unexpected official HTTP artifact count")
    return list(artifacts.values())


def download(item):
    # URLs and bounds have already been independently checked by manifest_artifact.
    request = Request(item["url"], headers={"User-Agent": "issue45-http-artifact-verifier/1"})
    with build_opener(NoRedirect()).open(request, timeout=45) as response:
        require(response.geturl() == item["url"], "unexpected official HTTP artifact origin")
        raw = response.read(item["size_bytes"] + 1)
    return raw


def prepare(http, manifests, libraries, fetch=download):
    # Validate every manifest and reconcile shared identities before any download.
    for item in catalog(http, manifests):
        raw = fetch(item)
        http.require(len(raw) == item["size_bytes"] and hashlib.sha1(raw).hexdigest() == item["sha1"],
                     "downloaded HTTP artifact size or SHA-1 mismatch")
        path = libraries / item["path"]
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("xb") as stream:
            stream.write(raw)


def source_identity():
    """Bind the two executed scripts to exact committed bytes, not index status."""
    root = Path(__file__).resolve().parents[2]
    directory = "diagnostics/issue45-runtime/"
    paths = (directory + "verify_official_http_artifacts.py",
             directory + "verify_http_artifacts.py")
    if (Path(__file__).resolve() != root / paths[0]
            or (root / paths[1]).resolve() != root / paths[1]):
        raise VerificationError("unexpected verifier source location")
    checkout = subprocess.check_output(["git", "rev-parse", "--verify", "HEAD"],
                                       cwd=root, stderr=subprocess.DEVNULL, text=True).strip()
    hashes = {}
    sources = {}
    for path in paths:
        committed = subprocess.check_output(["git", "cat-file", "blob", checkout + ":" + path],
                                            cwd=root, stderr=subprocess.DEVNULL)
        actual = (root / path).read_bytes()
        if actual != committed:
            raise VerificationError("verifier source differs from HEAD: " + path)
        hashes[path] = hashlib.sha256(actual).hexdigest()
        sources[path] = actual
    return checkout, hashes, sources[paths[1]]


def load_verified_source(source):
    """Execute checked source without consulting import caches or sys.modules."""
    path = Path(__file__).resolve().with_name("verify_http_artifacts.py")
    module = ModuleType("verify_http_artifacts")
    module.__file__ = str(path)
    exec(compile(source, str(path), "exec", dont_inherit=True), module.__dict__)
    return module


def require_same_source(identity):
    if source_identity() != identity:
        raise VerificationError("verifier checkout changed during verification")


def run_verifier(libraries, output):
    path = Path(__file__).resolve().with_name("verify_http_artifacts.py")
    subprocess.run([sys.executable, str(path), "--libraries-root", str(libraries),
                    "--output", str(output)], check=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        require(not args.output.exists(), "refusing to replace an existing report")
        identity = source_identity()
        checkout, source_sha256, verifier_source = identity
        http = load_verified_source(verifier_source)
        with tempfile.TemporaryDirectory(prefix="issue45-http-") as temporary:
            libraries = Path(temporary) / "libraries"
            report_path = Path(temporary) / "observation.json"
            prepare(http, http.MANIFESTS, libraries)
            require_same_source(identity)
            run_verifier(libraries, report_path)
            raw = report_path.read_bytes()
        report = json.loads(raw)
        http.require(len(report["occurrences"]) == 4 and len(report["artifacts"]) == 3 and
                     report["runtime_reachability"] == "not_established" and report["release_blocking"] is True and
                     report["risk_accepted"] is False, "unexpected HTTP verification report scope")
        require_same_source(identity)
        # Publish only after verification and provenance checks succeed.
        with args.output.open("xb") as stream:
            stream.write(raw)
        print(json.dumps({"checkout": checkout, "source_sha256": source_sha256,
                          "report_sha256": http.sha256(raw), "occurrences": 4,
                          "artifacts": {name: {"sha256": item["observed_sha256"],
                                                "spdy_class_count": len(item["spdy_class_sha256"])}
                                        for name, item in report["artifacts"].items()},
                          "scope": report["scope"], "result": "pass"}, sort_keys=True))
    except VerificationError as error:
        parser.exit(1, "Official HTTP verification failed: " + str(error) + "\n")
    except (OSError, ValueError, KeyError, TypeError, SyntaxError, subprocess.SubprocessError):
        parser.exit(1, "Official HTTP verification failed: acquisition, CLI or report unavailable\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
