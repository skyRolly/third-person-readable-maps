# Official HTTP artifact observation — 2026-11-25

This directory retains the **original, byte-identical** GitHub Actions ZIP from the post-merge main push at `d0b9cd96606085406124057ad1116459f61803a1`. It contains a single static JSON report, not any dependency JAR or runtime capture. See [provenance.json](provenance.json) for exact source digests and run/attempt/job/asset identities. The original workflow artifact expires on December 2, 2026; this archive does not depend on its availability.

Independent checks: the downloaded archive SHA-256 matched the GitHub API, ZIP CRC verification succeeded, and the sole JSON member SHA-256 matched the exact-head job log. The three official JAR identities, four retained occurrences and seven manifest scopes were checked. The Git blob equals the locally verified archive's Git blob.

Verify the saved bytes without extraction or external downloads from this directory. The checks remain active under `python -O` or `PYTHONOPTIMIZE`; the reviewed provenance is the expected identity, not an independently authenticated signature:

```python
import hashlib, io, json, zipfile
from pathlib import Path


def require(condition, message):
    if not condition:
        raise SystemExit(message)


p = json.loads(Path("provenance.json").read_text(encoding="utf-8"))
a = p["archive"]
archive_bytes = Path(a["path"]).read_bytes()
require(len(archive_bytes) == a["size_bytes"], "archive size mismatch")
require(hashlib.sha256(archive_bytes).hexdigest() == a["sha256"], "archive SHA-256 mismatch")
with zipfile.ZipFile(io.BytesIO(archive_bytes)) as z:
    require(z.namelist() == [a["json_member"]], "unexpected archive members")
    require(z.testzip() is None, "archive CRC mismatch")
    raw = z.read(a["json_member"])
require(len(raw) == a["json_size_bytes"], "JSON size mismatch")
require(hashlib.sha256(raw).hexdigest() == a["json_sha256"], "JSON SHA-256 mismatch")
report = json.loads(raw)
require(report["advisory"] == p["advisory"], "report advisory mismatch")
require(len(report["occurrences"]) == p["occurrence_count"] == 4, "occurrence count mismatch")
require(sum(len(x["manifest_sha256_by_game"]) for x in report["occurrences"])
        == p["manifest_scope_count"] == 7, "manifest scope count mismatch")
require(len(report["artifacts"]) == p["artifact_count"] == 3, "artifact count mismatch")
for key in ("scope", "runtime_reachability", "risk_accepted", "release_blocking"):
    require(report[key] == p[key], "report " + key + " mismatch")
```

**Limitations:** this is static artifact identity and class-inventory evidence only. It neither establishes live SPDY reachability/non-reachability nor changes the four blocking advisory occurrences, risk disposition, runtime acceptance, historical audit counts or release authorization. The separate diagnostic CI failure on the same main commit is tracked by PR #86; this archive is not evidence that all post-merge CI passed. No historical archive is replaced.
