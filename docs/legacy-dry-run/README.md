# Non-publishing five-group candidate dry run

This candidate-only configuration combines the three integrated groups with
PR #13 and PR #14 for an aggregation exercise. It is **not** the authoritative
release configuration and does not establish release support. The normal
release workflow still reads `release/compatibility.json` and requires strict
per-version evidence, approval, protected sources and reviewed security status.
`--candidate-config` is rejected unless `--candidate` is present; candidate
bundles cannot be submitted by `release_github.py` as production bundles.

Given an artifact directory containing one exact JAR per configured group:

```sh
python3 scripts/release.py matrix --plan docs/legacy-dry-run/plan.json --candidate --candidate-config docs/legacy-dry-run/compatibility.json
python3 scripts/release.py verify-sources --plan docs/legacy-dry-run/plan.json --candidate --candidate-config docs/legacy-dry-run/compatibility.json
python3 scripts/release.py aggregate --plan docs/legacy-dry-run/plan.json --candidate --candidate-config docs/legacy-dry-run/compatibility.json --artifacts ARTIFACTS --output EMPTY_OUTPUT --coordinator-sha COORDINATOR_SHA
```

Source pinning deliberately fails if a candidate branch advances. Rebuild and
review a new plan rather than using stale heads. Do not pass this candidate
configuration to publication tooling. The local execution record, hashes, CI
artifact provenance, and limitations are in [the dry-run report](../legacy-dry-run-2026-11-05.md).
