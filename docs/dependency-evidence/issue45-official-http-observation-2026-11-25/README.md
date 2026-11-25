# Official HTTP artifact observation — 2026-11-25

This directory retains the **original, byte-identical** GitHub Actions ZIP from the post-merge main push at `d0b9cd96606085406124057ad1116459f61803a1`. It contains a single static JSON report, not any dependency JAR or runtime capture. See [provenance.json](provenance.json) for exact source digests and run/attempt/job/asset identities. The original workflow artifact expires on December 2, 2026; this archive does not depend on its availability.

Independent checks: the downloaded archive SHA-256 matched the GitHub API, ZIP CRC verification succeeded, and the sole JSON member SHA-256 matched the exact-head job log. The three official JAR identities, four retained occurrences and seven manifest scopes were checked. The Git blob equals the locally verified archive's Git blob.

Verify the saved bytes without extraction or external downloads from this directory:

```python
import hashlib, json, zipfile
from pathlib import Path

p = json.loads(Path("provenance.json").read_text(encoding="utf-8"))
a = p["archive"]
archive = Path(a["path"])
assert archive.stat().st_size == a["size_bytes"]
assert hashlib.sha256(archive.read_bytes()).hexdigest() == a["sha256"]
with zipfile.ZipFile(archive) as z:
    assert z.namelist() == [a["json_member"]]
    assert z.testzip() is None
    raw = z.read(a["json_member"])
assert len(raw) == a["json_size_bytes"]
assert hashlib.sha256(raw).hexdigest() == a["json_sha256"]
report = json.loads(raw)
assert len(report["occurrences"]) == 4
assert sum(len(x["manifest_sha256_by_game"]) for x in report["occurrences"]) == 7
assert len(report["artifacts"]) == 3
for key in ("scope", "runtime_reachability", "risk_accepted", "release_blocking"):
    assert report[key] == p[key]
```

**Limitations:** this is static artifact identity and class-inventory evidence only. It neither establishes live SPDY reachability/non-reachability nor changes the four blocking advisory occurrences, risk disposition, runtime acceptance, historical audit counts or release authorization. The separate diagnostic CI failure on the same main commit is tracked by PR #86; this archive is not evidence that all post-merge CI passed. No historical archive is replaced.
