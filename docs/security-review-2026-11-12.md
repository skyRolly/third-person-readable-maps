# Security review worklist — 2026-11-12

The [individual candidate worklist](dependency-evidence/candidate-security-worklist-2026-11-12.json)
preserves all 180 distinct package/version/advisory pairs and their 385
group-scoped occurrences from the **2026-11-05 historical scans**. It records
each source SHA, inventory scope and fingerprint. These are not fresh scans of
the proposed `1.0.0` heads. Every finding remains failing; no risk is accepted.
The authoritative three-group ledger and the original reports remain unchanged.

The [current OSV details](dependency-evidence/critical-advisory-details-2026-11-12.json)
for the four critical advisory IDs below were retrieved on 2026-11-12. Their
fingerprints matched the retained candidate snapshots. The group counts below
are historical candidate occurrences, not conclusions about exploitability.

| Advisory | Historical occurrences | Evidence and remaining investigation |
|---|---:|---|
| [GHSA-c4c3-7fpv-j4q5](https://osv.dev/vulnerability/GHSA-c4c3-7fpv-j4q5) / CVE-2026-75595 | 10 | Netty's advisory describes fragmented TLS ClientHello handling in SNI/mTLS server routing. Determine whether any relevant game, integrated-server, loader or other component uses that path. The affected runtime versions are supplied by Minecraft; no dependency override is proposed. |
| [GHSA-jfh8-c2jp-5v3q](https://osv.dev/vulnerability/GHSA-jfh8-c2jp-5v3q) / CVE-2021-44228 | 3 | The advisory describes attacker-controlled log content and JNDI lookup behavior. The default client configurations described below use no-lookups formatting; effective launcher configuration and other paths still require assessment. |
| [GHSA-7rjr-3q55-vv33](https://osv.dev/vulnerability/GHSA-7rjr-3q55-vv33) / CVE-2021-45046 | 3 | The advisory describes non-default Thread Context patterns or lookups. The default client configurations below do not contain the searched context patterns or lookups; alternate configurations and runtime paths remain unverified. |
| [GHSA-fxph-q3j8-mv87](https://osv.dev/vulnerability/GHSA-fxph-q3j8-mv87) / CVE-2017-5645 | 2 | The advisory describes a TCP or UDP Log4j socket server receiving serialized events. Determine whether the game, loader, server or other installed components expose that path. |

For all 48 target versions, the [logging inventory](dependency-evidence/log4j-default-config-2026-11-12.json)
records SHA-1-verified Mojang version metadata, the declared Log4j coordinate,
and the default client logging configuration. The two retained configuration
files both contain `nolookups` and neither contains the searched context lookup
or context-pattern strings. This is evidence about Mojang's default client
configuration, not proof of the effective configuration in every launcher,
server, or modded installation. The [collector](dependency-evidence/log4j-config-2026-11-12/collect.py)
and exact configuration files are retained with their hashes.

These four advisory investigations remain **Further investigation**. A
reviewer must verify relevant execution paths and effective configuration,
assess compatible fixes or upstream ownership, and record a defensible
individual disposition. Fresh source-bound `1.0.0` candidate and proposal
inventories were subsequently scanned as described below; scan again whenever
the reviewed source or inventory changes. Do not treat an absent result, an
unbundled dependency, or this worklist as an approval.

The 2026-11-09 Maintenance Dependency Audit completed its scans and failed on
105 known unresolved matches; that failure followed the intended fail-closed
policy, not an OSV or dependency-resolution outage. A fresh source-bound local
scan on 2026-11-12 again completed with 41, 53 and 11 known failing matches on
the actual `mc/1.21.11`, `mc/26.1-26.2` and `mc/26.3` heads respectively,
with no disappeared matches. A separate review found a
latent comparison defect: a previously recorded match absent from a successful
later scan was automatically counted as resolved and could leave the gate
green. The proposed fix keeps such records failing as `resolved_needing_review`
until an explicit `Fixed`/`Resolved upstream` review names the source commit,
complete scoped-inventory digest, reviewer and evidence reference. Changed
sources or inventories invalidate that review. This defect did not cause the
observed 105-match failure, in which no findings had disappeared.

The fresh 2026-11-12 candidate scans also reported one changed advisory in
three groups: [GHSA-hgj6-7826-r7m5](https://osv.dev/vulnerability/GHSA-hgj6-7826-r7m5)
for `com.fasterxml.jackson.core:jackson-databind:2.13.4.2` in the
1.21.2–1.21.3, 1.21.4–1.21.8, and 1.21.9–1.21.10 candidates. OSV's 2026-11-10
update removed separate 3.x and differently named package entries from the
affected list. The `com.fasterxml.jackson.core` 2.x range containing 2.13.4.2
is still present. The three matches remain changed, unreviewed and failing;
the update is not a basis for accepting risk or overriding the game dependency.

The [current source-bound worklist](dependency-evidence/current-security-worklist-2026-11-12.json)
now indexes complete fresh scans for all 13 groups: ten final candidate heads
and the three actual integrated maintenance heads. It records 490 group-scoped
matches across 243 distinct package/version/advisory combinations and 89 OSV
IDs. The ten candidate scans contain 385 matches, including the three changed
matches above; the maintenance scans contain 105 known failing matches. No
previous match disappeared. Each record includes its scope, source identity,
advisory references and affected/fixed ranges, dependency ownership, packaged
artifact check, and remaining investigation. A fixed version in an upstream
advisory is not by itself proof that overriding Minecraft's runtime is safe.
All dispositions remain unresolved; no risk has been accepted.

The [high-priority advisory review](security-high-priority-2026-11-12.md)
adds individual trigger, affected-package and remediation analysis for 21
widely distributed high-severity IDs. It retains exact OSV responses and a
source- and artifact-bound inventory of direct mod-class references. The
absence of those direct references does not exclude a vulnerable game,
loader, multiplayer or other installed-mod path, so these findings still fail.
The [2026-11-13 follow-up](security-high-priority-2026-11-13.md) individually
reviews the remaining 12 high-severity IDs in the current worklist. These
targeted advisory reads do not replace a fresh full scan, and all 33 high IDs
remain unresolved and failing.

The [retained snapshots and reports](dependency-evidence/1.0.0-2026-11-12/)
were produced locally from the exact source commits using the pinned
`gradle/actions` dependency-graph init scripts, forced dependency resolution
and `--refresh-dependencies`, followed by the source-bound audit. The
maintenance snapshots describe the currently integrated 0.0.2 sources; they are
not relabeled as scans of the proposed maintenance PR heads. The historical
[pre-numeric-fix snapshots](dependency-evidence/1.0.0-pre-numeric-2026-11-12/)
remain separate. These local results do not replace a later scan of approved
merged heads or independent security review.

The separate [maintenance-proposal scans](dependency-evidence/1.0.0-maintenance-proposals-2026-11-12/)
also cover the exact unmerged 1.0.0 heads for PRs #31–#33. They found 41, 53
and 11 matches respectively; every proposal finding is unreviewed and failing,
with no disappeared baseline match accepted as resolved. These are additional
source identities for the same three groups, so their 105 matches are not
added a second time to the 490-group total above.

A [2026-11-13 OSV rescan](dependency-evidence/1.0.0-osv-rescan-2026-11-13/)
completed on all 13 unchanged source identities using the earlier source-bound
Gradle snapshots. It found the same 490 failing group-scoped matches, including
the same three changed candidate matches and no accepted disappearance. The
rescan queried OSV again; it did not re-resolve Gradle dependencies or turn
the historical maintenance snapshots into scans of unmerged proposals.
The separately retained [proposal OSV rescans](dependency-evidence/1.0.0-proposal-osv-rescan-2026-11-13/)
also queried the three unchanged 1.0.0 PR heads using their earlier snapshots;
their 41, 53 and 11 matches remain unreviewed and failing.
