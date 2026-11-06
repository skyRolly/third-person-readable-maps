# Candidate-only complete aggregation exercise

This plan and compatibility file are a **candidate-only test fixture**, not the
authoritative release configuration. They combine the three integrated groups
with ten unmerged draft ports to exercise all 48 distinct game versions. They
do not establish runtime acceptance, a reviewed security disposition, or
production release authorization. Normal release workflows continue to read
`release/compatibility.json`; `--candidate-config` is rejected unless
`--candidate` is present, and candidate bundles cannot be published as
production bundles by `release_github.py`.

With one exact JAR per group in an artifact directory:

```sh
python3 scripts/release.py matrix --plan docs/legacy-dry-run-expanded/plan.json --candidate --candidate-config docs/legacy-dry-run-expanded/compatibility.json
python3 scripts/release.py verify-sources --plan docs/legacy-dry-run-expanded/plan.json --candidate --candidate-config docs/legacy-dry-run-expanded/compatibility.json
python3 scripts/release.py aggregate --plan docs/legacy-dry-run-expanded/plan.json --candidate --candidate-config docs/legacy-dry-run-expanded/compatibility.json --artifacts ARTIFACTS --output EMPTY_OUTPUT --coordinator-sha COORDINATOR_SHA
```

Source verification fails when a pinned head moves. Rebuild and review a fresh
plan for final inputs. The stored manifest, checksums, exact build provenance,
negative tests and limitations are described in [the execution record](../legacy-dry-run-expanded-2026-11-05.md).
