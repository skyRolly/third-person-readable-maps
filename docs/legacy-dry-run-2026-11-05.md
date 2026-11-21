# Local non-publishing five-group dry run — 2026-11-05

**PASS for the exercised candidate aggregation; not a hosted release workflow
or production release approval.** The run used coordinator code commit
`9bb556cf0699f2e0850beb240511f924fd26751d` and the checked-in
[candidate-only plan and configuration](legacy-dry-run/). It validated all
five explicit, disjoint groups and checked each pinned source branch head with
`git ls-remote`. It used one exact JAR per group, checked JAR metadata,
namespace, Java bytecode, all expected Mixins, filenames and ZIP integrity,
then wrote and verified a provenance manifest and SHA-256 checksums.

| Group | Actual source SHA | Artifact SHA-256 | Build provenance |
|---|---|---|---|
| 1.21.11 | `177f5708727ae4c152091d185536aaa734063280` | `18e3a8dbd461b4bad2711cfe14282b96797f13bebabc8a2b644b6f482a27f930` | Linux artifact from merged-head [CI 41878123381](https://github.com/skyRolly/third-person-readable-maps/actions/runs/41878123381) |
| 1.21.4–1.21.8 | `29eb883a55992a623b7ba34e349bdcb6fee7c4c2` | `26a28fb550132d07af415c41ccb82982937906ab991ad810406d2937b5e4e776` | Local clean build at this source SHA; identical to installed smoke-test JAR |
| 1.21.9–1.21.10 | `9c96b661713ac83fa09c0b8fc26c1bf3a62f8053` | `03c760850ef7b1501fb5b6d23af61ce855e746ab8d5a2f2a1deed9a4480e26ac` | Local clean build of implementation commit `ee07f9599f3868909c1d198802783422f6d83e72`; the pinned head adds only smoke evidence and the JAR hash was identical |
| 26.1–26.2 | `453cf35695cf07be4072f77895cdbafbed617870` | `75c244ef6440ff2622d8617a5c60288b956d1a1d80956a233e13bac1ced9c554` | Linux artifact from merged-head [CI 41878099343](https://github.com/skyRolly/third-person-readable-maps/actions/runs/41878099343) |
| 26.3 | `226b1de7dd4e7c2a75ec35eef1697434462e4f54` | `9f3bc6a3ee4477a3e7cc0f0ebb4c2ff25785ac3f608761f2dc502765f23e2e69` | Linux artifact from merged-head [CI 41878066239](https://github.com/skyRolly/third-person-readable-maps/actions/runs/41878066239) |

Each candidate JAR also passed its branch's cross-version API verifier and
hosted Linux and Windows CI at the then-current PR head. The integrated shared
26.1–26.2 verifier ran in its merged-head CI. Existing JARs were downloaded
from those successful CI runs and inspected locally, not rebuilt in this
aggregation. The two new JARs were built locally; their separate CI runs are
not a substitute for this local aggregation.

An empty artifact input was rejected. A strict plan without per-version runtime
reports was rejected, and the CLI rejects `--candidate-config` unless
`--candidate` is set. The bundle is explicitly marked candidate; no tag,
Draft Release, public Release, approval, or publication API was invoked.

This was a staged local exercise of matrix construction, source pinning,
inspection, incomplete-input failure and aggregation. It did not execute a
hosted five-group workflow; it did not complete all graphical tests, human
reviews, security dispositions or administrative release gates. Any source
head change invalidates the checked-in plan and requires a fresh run.
