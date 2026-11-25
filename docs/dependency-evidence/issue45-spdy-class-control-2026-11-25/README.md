# Isolated SPDY class-definition observation — 2026-11-25

The original single-JSON Actions archive is retained byte-for-byte from the
successful PR #88 probe at the exact checkout recorded in
[provenance.json](provenance.json). The archive is a separate synthetic
observation, not a live Minecraft capture. The temporary Actions artifact
expires on December 2, 2026.

Independent verification checked the downloaded ZIP digest against the
GitHub API, CRC and sole JSON member digest against the actual CI log,
checkout and both source hashes against the locally tested source files,
and all three HTTP code-source and class-resource digests against the
prior static archive. All three positive and negative controls passed;
23 library digest records are present. Companion-library SHA-256 values
are observations, not previously pinned SHA-256 identities.

Verify the archived bytes using the reviewed provenance (not a signature
or independently authenticated trust root). Run from this directory:

```python
import hashlib, io, json, zipfile
from pathlib import Path

def require(condition, message):
    if not condition:
        raise SystemExit(message)

p = json.loads(Path("provenance.json").read_bytes())
a = p["archive"]
raw = Path(a["path"]).read_bytes()
require(len(raw) == a["size_bytes"], "archive size mismatch")
require(hashlib.sha256(raw).hexdigest() == a["sha256"], "archive digest mismatch")
with zipfile.ZipFile(io.BytesIO(raw)) as z:
    require(z.namelist() == [a["json_member"]], "unexpected members")
    require(z.testzip() is None, "CRC mismatch")
    report_bytes = z.read(a["json_member"])
require(len(report_bytes) == a["json_size_bytes"], "JSON size mismatch")
require(hashlib.sha256(report_bytes).hexdigest() == a["json_sha256"], "JSON digest mismatch")
r = json.loads(report_bytes)
for key in ("checkout", "source_sha256", "scope", "pipeline_observed",
            "runtime_reachability", "risk_accepted", "release_blocking"):
    require(r[key] == p[key], "report mismatch: " + key)
require(len(r["observations"]) == p["observations"] == 3, "observation count mismatch")
require(sum(len(o["library_sha256"]) for o in r["observations"]) == p["library_count"] == 23,
        "library count mismatch")
for o in r["observations"]:
    require(o["positive"] == "defined_by_isolated_url_loader", "positive control mismatch")
    require(o["negative"] == "class_not_found", "negative control mismatch")
```

No raw JARs, game sessions, class initialization, network frames or
pipeline observations were retained. All four advisory occurrences remain
blocking. This record does not change the historical runtime evidence
schema or authorize a risk disposition, product integration, or release.
