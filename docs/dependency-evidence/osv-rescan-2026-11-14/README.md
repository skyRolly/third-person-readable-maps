# OSV re-query — 2026-11-14

The [index](index.json) records complete OSV queries for the ten advanced
legacy candidate heads and the three actually integrated maintenance heads.
The queries reuse the exact source-bound Gradle snapshots retained on November
12 or 13; they are not a new Gradle dependency resolution. The three unmerged
1.0.0 maintenance proposals are scanned and indexed separately from the active
maintenance branches.

All 13 current-source scans completed and returned exit code 1 for **490
unresolved, failing occurrences**: 385 across candidates and 105 across the
three integrated branches. The three proposals separately returned 41, 53 and
11 failing occurrences. Every package, advisory, fingerprint, scope, state and
failing flag matched the preceding complete source-bound scan. No finding
disappeared, was accepted, or was suppressed. The individual
[November 13 disposition worklist](../current-security-worklist-2026-11-13.json)
therefore remains applicable to the unchanged sources and fingerprints; it
retains its original date and provenance. The source snapshots, previous
reports and individual investigation notes remain historical records.

The [collector](collect.py) validates source and snapshot identities and
compares full finding signatures before retaining the reports and logs. The
runner scripts and their logs are hashed in the index. These results do not
establish that the dependencies are safe or that a future merged source is
covered. Each unresolved disposition and every eventual merged-head inventory
still requires review.
