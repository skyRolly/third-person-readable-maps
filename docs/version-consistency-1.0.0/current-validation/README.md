# Current candidate validation

The [current selection](../current-evidence.json) and [source pins](../current-heads.json) are the mutable entry points. The files in this directory record the selected observations: 13 clean builds, packaged metadata, the bounded 48-version static sweep, nine adjacent-version negative controls and their log hashes. Each clean JAR matched the preceding hierarchy-review build. Earlier runtime observations remain attached to their original sources and hashes; same-artifact continuity does not make them fresh or approved merged-source tests.

The [hosted check index](hosted-checks.json) identifies proposal head, base head, synthetic PR merge commit, tested tree, job attempt and archive separately. All 26 final Linux and Windows jobs passed; their checked-out merge trees match the proposal trees, and downloaded archive and JAR hashes match the clean builds. On #22, the failed Linux dependency download was rerun; GitHub reports both successful jobs in attempt 2 while the retained Windows archive and its job start predate the rerun. Both refer to the same verified proposal and merge tree. These are proposed-head checks, not checks of a future merged maintenance source.

The [current candidate rehearsal](rehearsal/) aggregated all 13 final proposal artifacts and checked their checksums. Its manifest records coordinator code commit `ef0934f76034bda684895bc148a82b68cbca4973`; the [index](rehearsal/index.json) hashes the unchanged release scripts and version file used by the run. The candidate plan and product sources are exact. The 18 negative controls comprise 15 existing aggregation or authorization checks and three rehearsal-harness checks; the latter are not claims about the production aggregator. The reusable runner and its deterministic input-path substitutions are identified in the index.

The rehearsal reused the byte-identical dated compatibility configuration;
its current matrix can be regenerated from that configuration and the current
plan. Their identities are checked without retaining duplicate copies.

The security reports selected in the current evidence file are retained scans of their recorded earlier sources. The changes since those snapshots affect only linkage-verifier scripts, fixtures and the verification contract; they do not constitute a fresh Gradle resolution, new security scan, remediation or accepted risk. Current-source security resolution and strict release evidence remain pending.
