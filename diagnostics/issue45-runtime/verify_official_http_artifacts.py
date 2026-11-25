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
from urllib.request import HTTPRedirectHandler, Request, build_opener

import verify_http_artifacts as http


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def catalog(manifests):
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
        http.require(response.geturl() == item["url"], "unexpected official HTTP artifact origin")
        raw = response.read(item["size_bytes"] + 1)
    return raw


def prepare(manifests, libraries, fetch=download):
    # Validate every manifest and reconcile shared identities before any download.
    for item in catalog(manifests):
        raw = fetch(item)
        http.require(len(raw) == item["size_bytes"] and hashlib.sha1(raw).hexdigest() == item["sha1"],
                     "downloaded HTTP artifact size or SHA-1 mismatch")
        path = libraries / item["path"]
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("xb") as stream:
            stream.write(raw)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        http.require(not args.output.exists(), "refusing to replace an existing report")
        checkout = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=http.ROOT, text=True).strip()
        with tempfile.TemporaryDirectory(prefix="issue45-http-") as temporary:
            libraries = Path(temporary)
            prepare(http.MANIFESTS, libraries)
            subprocess.run([sys.executable, str(Path(http.__file__).resolve()), "--libraries-root", str(libraries),
                            "--output", str(args.output)], check=True)
        raw = args.output.read_bytes()
        report = json.loads(raw)
        http.require(len(report["occurrences"]) == 4 and len(report["artifacts"]) == 3 and
                     report["runtime_reachability"] == "not_established" and report["release_blocking"] is True and
                     report["risk_accepted"] is False, "unexpected HTTP verification report scope")
        print(json.dumps({"checkout": checkout, "report_sha256": http.sha256(raw), "occurrences": 4,
                          "artifacts": {name: {"sha256": item["observed_sha256"],
                                                "spdy_class_count": len(item["spdy_class_sha256"])}
                                        for name, item in report["artifacts"].items()},
                          "scope": report["scope"], "result": "pass"}, sort_keys=True))
    except http.VerificationError as error:
        parser.exit(1, "Official HTTP verification failed: " + str(error) + "\n")
    except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError):
        parser.exit(1, "Official HTTP verification failed: acquisition, CLI or report unavailable\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
