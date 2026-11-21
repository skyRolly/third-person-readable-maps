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
The owner-policy refresh in `rehearsal-2026-11-21-owner-policy/` retains exact
hosted Linux and Windows archives for all 13 selected sources, their raw CI
logs for the three integrated branches, and fresh API-verifier output. It
checks each archive digest and confirms that both platform archives contain
the same expected JAR bytes. The fresh non-publishing rehearsal uses those
archives and the updated coordinator code; the mutable evidence selection
points to its index, manifest, checksums, and negative controls.

The three integrated maintenance records now point to the current tips of
`mc/1.21.11` (`ec61f4c`), `mc/26.1-26.2` (`b7620ef`), and `mc/26.3`
(`38bac1c`). Their Linux and Windows CI, wrapper preflight, packaged API
verification, and clean builds passed on those exact commits. Current-source
security inventory and runtime evidence remain pending for these branches;
earlier source-bound scans and runtime reports keep their original identities
in the preserved snapshot and historical records.

The Gradle 9.9.2 update changes the distribution and the JAR manifest version
field. Fresh source-bound dependency resolutions and advisory scans are being
collected. Earlier OSV reports and runtime observations retain their original
source and artifact identities; neither a previous scan nor a previous JAR is
relabelled as a fresh result. See the [late-review worklog](../../worklogs/late-review-2026-11-16.md)
for the targeted 1.14 diagnostic, upstream Gradle advisories and outstanding gates.
