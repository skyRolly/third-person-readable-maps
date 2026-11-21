# Current candidate validation

The [current selection](../current-evidence.json) and [source pins](../current-heads.json)
are the authoritative mutable entry points. Files in this directory contain
observations for the source and artifact identities recorded inside them; until
the selection marks a result observed, an older file does not certify a newer
head. The [November 16 index](../late-review-2026-11-16.json) preserves the
preceding build, static and hosted-check identities.

Build, packaged metadata, static coverage, adjacent-version controls, hosted
checkout/artifact records, and the non-publishing rehearsal are reconciled by
`scripts/validate_current_evidence.py`. Its pending states remain visible and
never authorize release. The rehearsal's harness controls are distinct from
production aggregator controls.

The prior rehearsal index and its November 21 inputs are retained unchanged.
The owner-policy refresh in `rehearsal-2026-11-21-owner-policy/` separately
retains the exact hosted Linux archives, verifies their source and artifact
digests, and records a fresh non-publishing aggregation against the updated
coordinator code. The mutable evidence selection points to that refresh; the
archived rehearsal remains historical provenance.

The Gradle 9.9.2 update changes the distribution and the JAR manifest version
field. Fresh source-bound dependency resolutions and advisory scans are being
collected. Earlier OSV reports and runtime observations retain their original
source and artifact identities; neither a previous scan nor a previous JAR is
relabelled as a fresh result. See the [late-review worklog](../../worklogs/late-review-2026-11-16.md)
for the targeted 1.14 diagnostic, upstream Gradle advisories and outstanding gates.
