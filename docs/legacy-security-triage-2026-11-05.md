# Legacy candidate advisory review index — 2026-11-05

This index summarizes retained OSV candidate scan snapshots; it is not a security approval, applicability finding, remediation plan or release authorization. All 385 group-scoped package/version/advisory matches remain unreviewed and failing. The snapshots include 88 distinct OSV advisory IDs and 180 distinct package/version/advisory pairs; the same pair can occur in more than one group. Severity labels below are copied from the scan results, not independently assessed.

Every match appears in at least one scanned Mojang runtime manifest; 332 also occur in the collected Gradle dependency graph and 53 appear only in the runtime inventories. The inventories include all listed platform variants. These counts do not establish which paths are reached, which libraries are bundled by the mod, or whether an advisory applies in a specific installation. Native advisories may be missing from OSV.

| Candidate group | Total | Critical | High | Moderate | Low | Runtime and Gradle | Runtime only |
|---|---:|---:|---:|---:|---:|---:|---:|
| 1.14-1.14.4 | 27 | 3 | 9 | 13 | 2 | 27 | 0 |
| 1.15-1.16.5 | 27 | 3 | 9 | 13 | 2 | 27 | 0 |
| 1.17-1.19.2 | 53 | 3 | 17 | 31 | 2 | 27 | 26 |
| 1.19.3 | 24 | 1 | 7 | 15 | 1 | 24 | 0 |
| 1.19.4-1.20.4 | 42 | 2 | 15 | 24 | 1 | 24 | 18 |
| 1.20.5-1.20.6 | 28 | 1 | 10 | 16 | 1 | 28 | 0 |
| 1.21-1.21.1 | 28 | 1 | 10 | 16 | 1 | 28 | 0 |
| 1.21.2-1.21.3 | 45 | 1 | 18 | 25 | 1 | 45 | 0 |
| 1.21.4-1.21.8 | 52 | 2 | 23 | 26 | 1 | 43 | 9 |
| 1.21.9-1.21.10 | 59 | 1 | 23 | 33 | 2 | 59 | 0 |
| **Total** | **385** | **18** | **141** | **212** | **14** | **332** | **53** |

The full package/version/advisory records, scopes, fingerprints and original source references are retained in the following scan reports:

- [legacy-candidate-114-osv-2026-11-05.json](dependency-evidence/legacy-candidate-114-osv-2026-11-05.json)
- [legacy-candidate-1212-osv-2026-11-05.json](dependency-evidence/legacy-candidate-1212-osv-2026-11-05.json)
- [legacy-candidate-more-osv-2026-11-05.json](dependency-evidence/legacy-candidate-more-osv-2026-11-05.json)
- [legacy-candidate-older-osv-2026-11-05.json](dependency-evidence/legacy-candidate-older-osv-2026-11-05.json)
- [legacy-candidate-osv-2026-11-05.json](dependency-evidence/legacy-candidate-osv-2026-11-05.json)

The proposed [scheduled candidate audit](dependency-monitoring.md#proposed-scheduled-legacy-candidate-audit) fails closed on current and unreviewed disappeared findings; it has not yet run as a hosted schedule. Reviewers must re-scan the eventual maintained heads, assess each applicable advisory and record individual dispositions in the authoritative reviewed ledger before release. No finding has been accepted by this index.
