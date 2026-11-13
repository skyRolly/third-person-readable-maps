# Non-publishing 1.0.0 candidate rehearsal — 2026-11-12

**Historical:** This is the 2026-11-12 rehearsal and its original provenance. See the current rehearsal for later evidence.

The local rehearsal used [13-group candidate compatibility](evidence/candidate-compatibility.json) and a [plan](evidence/candidate-plan.json) pinning ten legacy candidate heads and three separate 1.0.0 maintenance PR heads. The generated [matrix](evidence/candidate-matrix.json) has 13 groups and 48 unique explicit game versions. `git ls-remote` verified each exact branch and commit.

The aggregator inspected one locally built 1.0.0 JAR per group for identity, metadata, Java bytecode, namespace, Mixin configuration, license and classifier. It produced the candidate-only [provenance manifest](evidence/release-manifest.json) and [SHA256SUMS](evidence/SHA256SUMS); all 13 JAR checksums and the manifest checksum passed locally. The JARs themselves are not committed to this coordination repository. Product PR CI retains its own distributable artifacts; verify their identity separately before using them as evidence.

[Negative controls](evidence/negative-controls.json) rejected a missing group, duplicate artifact, wrong version, a mixed 0.0.2 JAR, wrong classifier, wrong game declaration, wrong namespace, modified artifact after checksumming, wrong candidate group/branch, a mismatched remote source SHA, missing strict runtime evidence and use of the candidate manifest for publication. Existing unit tests cover further authorization, evidence and configuration failures. No release-write mode, tag, draft or public release was used.

The manifest records coordinator commit `559ca7cd0896f382618bb1356fad034bdf382103`, the exact committed release-validation code used in the rehearsal. A later documentation/evidence commit may contain this record; it does not retroactively change the coordinator identity in the manifest. This was local candidate aggregation with proposed unmerged sources, not production authorization, a hosted release rehearsal, or proof of complete runtime/security acceptance. Rebuild and rerun on reviewed, integrated exact heads before any release.
