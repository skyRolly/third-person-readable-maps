# Issue 45: review applicability and historical continuity

This follow-up repairs evidence validation and CI failure propagation. It does
not clear any dependency advisory, accept risk or authorize release.

The Windows credential workflow previously ran both Python suites in one
PowerShell step. A successful second command could mask a failed first command
because the shell propagated only the last native exit status. The suites now run
in separate steps on both platforms, so GitHub Actions stops the job when either
step fails. The credential guard and existing workflow permissions are retained.

The priority exporter previously reused focused reviewer details after checking
only occurrence identity. It now requires exact, unique source and package
coverage, scope and version, fingerprint, severity, disposition, blocking state,
and the original reviewed report reference. The source-bound historical report
and the fresh live archive are independently hash-verified. Their bytes may
differ for an ordinary new scan; the reviewed advisory fields must still match.
Only a change to the `modified` timestamp alone is treated as administrative;
other changed advisory fields conservatively require a new review. A mismatch
stops the priority export. The source records and all findings remain blocked.

Mutation tests retain the previous PR #54 exporter as an explicit regression
control. The old exporter accepts internally consistent changes to scopes,
fingerprints, advisory summaries, dispositions and historical report provenance;
the corrected exporter rejects each. A count-preserving duplicate is also
rejected. An unrelated advisory update and a new report timestamp preserve the
unchanged focused review. No old audit report or disposition evidence is edited.

## Build continuity erratum

The original [build snapshot](../dependency-evidence/issue45-live-source-2026-11-22/product-builds-snapshot.json)
has SHA-256 `1c98da271fbf0bb4d6ce94e7831c7ae044e5a6bffceca36d0942e93be9820bd1`.
For `1.21.11`, `26.1-26.2` and `26.3`, commit `0928879` updated each prior
source and JAR hash to the immediately preceding record and added
`continuity: same`, but left `same_as_previous: false` from the older comparison.
The [original build producer](../version-consistency-1.0.0/hierarchy-2026-11-15/build-runner.py)
defines that boolean as equality of the JAR hashes; it was not a source identity
flag. The current continuity validator likewise defines `same` by artifact hash.

The [erratum](../dependency-evidence/issue45-review-fixes-2026-11-22/build-continuity-erratum.json)
preserves both original snapshots and records separate `source_unchanged` and
`artifact_unchanged` values. All three source commits differ, while each
current JAR matches its immediate predecessor. The validator checks the
current Linux and Windows archives and the retained previous Linux archive for
each group, including archive and contained JAR SHA-256 values. A previous
Windows archive is not claimed from these input records. The historical false
field remains in the original bytes and is identified as stale, not silently
rewritten. These artifact comparisons are not runtime or security clearance.
