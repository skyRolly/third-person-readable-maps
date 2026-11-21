# Source-bound OSV rescan — 2026-11-13 UTC

All 13 groups were scanned against OSV again with the unchanged, exact source
identities in the [index](index.json). These runs reused the complete
source-bound Gradle snapshots retained from 2026-11-12; they did **not** resolve
Gradle dependencies again. Candidate reports remain candidate evidence and the
three maintenance reports still refer to the currently integrated 0.0.2
branches, not the unmerged 1.0.0 maintenance proposals.

All 13 scans completed and each audit exited 1 because its findings remain
failing. The 385 candidate and 105 maintenance matches have the same
package/version/advisory fingerprints, states and failing flags as the
previous reports. Three candidate matches remain changed relative to the
older baseline; no disappearance was accepted as resolved. No security risk
was accepted. Re-resolve dependencies and rescan after any source, branch or
dependency change, especially after independent review and integration.
