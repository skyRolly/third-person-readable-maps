# Non-publishing 1.0.0 candidate rehearsal — 2026-11-13

The later [November 14 rehearsal](legacy-dry-run-1.0.0-2026-11-14/) retains
its own coordinator identity, plan, checksums and negative controls.

This rehearsal uses the advanced product PR heads identified in the
[source transition](source-head-transition-2026-11-13.md). Candidate monitoring
and full runtime evidence remain separate, unfinished gates.

The local rehearsal used [13-group candidate compatibility](legacy-dry-run-1.0.0/candidate-compatibility.json)
and a [plan](legacy-dry-run-1.0.0/candidate-plan.json) pinning ten legacy
candidate heads and three separate 1.0.0 maintenance PR heads. The generated
[matrix](legacy-dry-run-1.0.0/candidate-matrix.json) has 13 groups and 48
unique explicit game versions. `git ls-remote` verified each exact branch
and commit.

The aggregator inspected one locally built 1.0.0 JAR per group for identity,
metadata, Java bytecode, namespace, Mixin configuration, license and
classifier. It produced the candidate-only [provenance manifest](legacy-dry-run-1.0.0/release-manifest.json)
and [SHA256SUMS](legacy-dry-run-1.0.0/SHA256SUMS); all 13 JAR checksums and
the manifest checksum passed locally. The [execution log](legacy-dry-run-1.0.0/rehearsal.log)
records the source checks and negative controls. The JARs themselves are not committed to
this coordination repository. Product PR CI retains its own distributable
artifacts; verify their identity separately before using them as evidence.

[Negative controls](legacy-dry-run-1.0.0/negative-controls.json) rejected a
missing group, duplicate artifact, wrong version, mixed 0.0.2 and 1.0.0 JARs,
wrong classifier, incorrect game metadata, duplicate and overlapping game
versions, wrong namespace, modified artifact after checksumming, wrong candidate
branch, mismatched remote source SHA, missing strict runtime evidence, a
candidate-only configuration in strict CLI mode, and use of the candidate
manifest for publication. Existing unit tests cover further authorization,
evidence and configuration failures. The [local harness](legacy-dry-run-1.0.0/rehearse.py)
records these controls and expects the product worktrees and historical 0.0.2
negative fixture. This run supplied the advanced candidate evidence and
clean-build artifact directories through `TPRM_REHEARSAL_EVIDENCE` and
`TPRM_REHEARSAL_ARTIFACTS`. No release-write mode, tag, draft or public release
was used.

The manifest records coordinator commit
`61ce5c52ea37b21a57f97e21bf0906fe9c240bfd`, the exact committed
release-validation code used in this rehearsal. The later evidence commit
containing this record does not retroactively change the coordinator identity.
The [earlier November 13 rehearsal](historical-1.0.0-rehearsal-2026-11-13-a30dff/)
retains its original manifest and checksums separately.
The [immediately preceding source-head snapshot](historical-verifier-followup-2026-11-13/)
also retains its manifest and checksums.
The [2026-11-12 rehearsal](historical-1.0.0-rehearsal-2026-11-12/report.md)
and its original manifest and checksums remain historical. This was local
candidate aggregation with proposed unmerged sources, not production
authorization, a hosted release rehearsal, or proof of complete runtime or
security acceptance. Rebuild and rerun on reviewed, integrated exact heads
before any release.
