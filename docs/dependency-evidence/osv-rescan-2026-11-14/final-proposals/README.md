# Final-source dependency scans — 2026-11-14

The [index](index.json) binds the ten candidate scans to fresh hosted CI Gradle dependency-graph snapshots and the three **unmerged** maintenance-proposal scans to separately re-resolved local Gradle snapshots. All 13 recorded snapshot source identities match their exact proposal heads. Hosted pull-request jobs checked out synthetic merge trees that were independently verified equal to the proposal trees; see the [merge-tree evidence](../../../version-consistency-1.0.0/stabilization-2026-11-14/hosted-pr-merge-trees.json). The hosted snapshot for each maintenance proposal is also retained independently. The 10 candidate scans completed with exit 1: **385 failing occurrences** (382 known and three changed against the retained baseline). The three changed Jackson records were already present with the same fingerprint and scopes in the previous November 14 scan. No candidate match disappeared.

The three actual integrated 0.0.2 branches were queried against OSV again using their retained, hash-checked source-bound Gradle snapshots: 41, 53 and 11 unresolved occurrences respectively. These are not newly resolved Gradle inventories. The unmerged maintenance proposals separately returned 41, 53 and 11 failing occurrences after fresh Gradle resolution; they are not added to the 105 integrated occurrences. No security gate is green and no risk is accepted. Raw source-bound reports, logs and hashes remain in the index.

## Prioritized individual review

The [candidate worklist](candidate-worklist.json) retains every scanner occurrence, aliases, source, package, scope, severity and failing state. The following **investigator recommendations** advance the remediation path for critical issues; they do not change the candidate scanner disposition, declare reachability, approve risk, or certify an upstream fix as compatible. The exact original advisory responses and affected ranges are in the source-bound reports.

* [GHSA-jfh8-c2jp-5v3q / CVE-2021-44228](https://osv.dev/vulnerability/GHSA-jfh8-c2jp-5v3q) is the Log4j message-lookup RCE issue. The scanner identifies 2.8.1 and 2.14.1. The advisory lists the 2.12.2 and 2.15.0 fixed endpoints for their respective lines and recommends later security updates.
* [GHSA-7rjr-3q55-vv33 / CVE-2021-45046](https://osv.dev/vulnerability/GHSA-7rjr-3q55-vv33) concerns the incomplete Log4j 2.15.0 fix in certain non-default context-lookup configurations; its affected-line endpoints include 2.12.2 and 2.16.0.
* [GHSA-fxph-q3j8-mv87 / CVE-2017-5645](https://osv.dev/vulnerability/GHSA-fxph-q3j8-mv87) concerns Log4j socket-server deserialization and lists 2.8.2 as the fixed endpoint for the scanned 2.8.1 line.
* [GHSA-c4c3-7fpv-j4q5 / CVE-2026-75595](https://osv.dev/vulnerability/GHSA-c4c3-7fpv-j4q5) concerns fragmented TLS ClientHello handling that can bypass per-SNI mTLS under the advisory's specified server configuration. Its fixed endpoints are 4.1.137.Final and 4.2.17.Final.

The reported Log4j and Netty coordinates are present in Minecraft runtime inventories, and some also occur in the development Gradle graph. They are game-managed rather than bundled Mod libraries. An upstream-compatible correction and effective launcher/game configuration need independent assessment; a version-level match alone neither proves exploitation nor justifies a Mod-imposed library override.

| Advisory | Candidate group | Package version | Scopes | Proposed remediation classification |
|---|---|---|---|---|
| GHSA-7rjr-3q55-vv33 | 1.14-1.14.4 | `2.8.1` | gradle, runtime/1.14, runtime/1.14.1, runtime/1.14.2, runtime/1.14.3, runtime/1.14.4 | Upstream-dependent remediation; reachability unproven |
| GHSA-7rjr-3q55-vv33 | 1.15-1.16.5 | `2.8.1` | gradle, runtime/1.15, runtime/1.15.1, runtime/1.15.2, runtime/1.16, runtime/1.16.1, runtime/1.16.2, runtime/1.16.3, runtime/1.16.4, runtime/1.16.5 | Upstream-dependent remediation; reachability unproven |
| GHSA-7rjr-3q55-vv33 | 1.17-1.19.2 | `2.14.1` | gradle, runtime/1.17, runtime/1.17.1, runtime/1.18, runtime/1.18.1 | Upstream-dependent remediation; reachability unproven |
| GHSA-c4c3-7fpv-j4q5 | 1.17-1.19.2 | `4.1.77.Final` | runtime/1.19, runtime/1.19.1, runtime/1.19.2 | Upstream-dependent remediation; reachability unproven |
| GHSA-c4c3-7fpv-j4q5 | 1.19.3 | `4.1.82.Final` | gradle, runtime/1.19.3 | Upstream-dependent remediation; reachability unproven |
| GHSA-c4c3-7fpv-j4q5 | 1.19.4-1.20.4 | `4.1.82.Final` | gradle, runtime/1.19.4, runtime/1.20, runtime/1.20.1 | Upstream-dependent remediation; reachability unproven |
| GHSA-c4c3-7fpv-j4q5 | 1.19.4-1.20.4 | `4.1.97.Final` | runtime/1.20.2, runtime/1.20.3, runtime/1.20.4 | Upstream-dependent remediation; reachability unproven |
| GHSA-c4c3-7fpv-j4q5 | 1.20.5-1.20.6 | `4.1.97.Final` | gradle, runtime/1.20.5, runtime/1.20.6 | Upstream-dependent remediation; reachability unproven |
| GHSA-c4c3-7fpv-j4q5 | 1.21-1.21.1 | `4.1.97.Final` | gradle, runtime/1.21, runtime/1.21.1 | Upstream-dependent remediation; reachability unproven |
| GHSA-c4c3-7fpv-j4q5 | 1.21.2-1.21.3 | `4.1.97.Final` | gradle, runtime/1.21.2, runtime/1.21.3 | Upstream-dependent remediation; reachability unproven |
| GHSA-c4c3-7fpv-j4q5 | 1.21.4-1.21.8 | `4.1.115.Final` | gradle, runtime/1.21.4 | Upstream-dependent remediation; reachability unproven |
| GHSA-c4c3-7fpv-j4q5 | 1.21.4-1.21.8 | `4.1.118.Final` | runtime/1.21.5, runtime/1.21.6, runtime/1.21.7, runtime/1.21.8 | Upstream-dependent remediation; reachability unproven |
| GHSA-c4c3-7fpv-j4q5 | 1.21.9-1.21.10 | `4.1.118.Final` | gradle, runtime/1.21.10, runtime/1.21.9 | Upstream-dependent remediation; reachability unproven |
| GHSA-fxph-q3j8-mv87 | 1.14-1.14.4 | `2.8.1` | gradle, runtime/1.14, runtime/1.14.1, runtime/1.14.2, runtime/1.14.3, runtime/1.14.4 | Upstream-dependent remediation; reachability unproven |
| GHSA-fxph-q3j8-mv87 | 1.15-1.16.5 | `2.8.1` | gradle, runtime/1.15, runtime/1.15.1, runtime/1.15.2, runtime/1.16, runtime/1.16.1, runtime/1.16.2, runtime/1.16.3, runtime/1.16.4, runtime/1.16.5 | Upstream-dependent remediation; reachability unproven |
| GHSA-jfh8-c2jp-5v3q | 1.14-1.14.4 | `2.8.1` | gradle, runtime/1.14, runtime/1.14.1, runtime/1.14.2, runtime/1.14.3, runtime/1.14.4 | Upstream-dependent remediation; reachability unproven |
| GHSA-jfh8-c2jp-5v3q | 1.15-1.16.5 | `2.8.1` | gradle, runtime/1.15, runtime/1.15.1, runtime/1.15.2, runtime/1.16, runtime/1.16.1, runtime/1.16.2, runtime/1.16.3, runtime/1.16.4, runtime/1.16.5 | Upstream-dependent remediation; reachability unproven |
| GHSA-jfh8-c2jp-5v3q | 1.17-1.19.2 | `2.14.1` | gradle, runtime/1.17, runtime/1.17.1, runtime/1.18, runtime/1.18.1 | Upstream-dependent remediation; reachability unproven |

The authoritative ledger separately records one runtime-only 26.2 Netty occurrence as upstream-dependent for remediation; it remains failing while reachability is unresolved. Other candidate findings retain their scanner's further-investigation disposition. A reviewer must determine effective configurations, actual reachable paths and compatible fixes for each group.
