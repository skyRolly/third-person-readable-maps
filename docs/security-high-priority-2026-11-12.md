# Individual high-priority dependency review — 2026-11-12

These seven high-severity advisories were selected because they span several
of the 13 proposed groups. The [current worklist](dependency-evidence/current-security-worklist-2026-11-12.json)
identifies each exact package/version/advisory occurrence, source SHA,
Gradle/runtime scope and failing state. The affected versions and fixed events
below are the OSV results for the recorded packages, not a recommendation to
override Minecraft-managed dependencies. [Exact OSV responses and hashes](dependency-evidence/high-advisories-2026-11-12/index.json)
were retained on 2026-11-12. Group counts include the current 0.0.2 integrated
heads and the final 1.0.0 legacy candidates, not the extra proposal scans.

| Advisory | Trigger and source-bound affected packages | Remaining investigation |
|---|---|---|
| [GHSA-xxph-c9ww-hj94](https://osv.dev/vulnerability/GHSA-xxph-c9ww-hj94), CVE-2026-102554 | Guava `CompactHashMap`, `CompactHashSet` or `MapMakerInternalMap` native deserialization can allocate from an attacker-controlled count. Guava 21.0, 31.0.1-jre, 31.1-jre, 32.1.2-jre, 33.3.1-jre, 33.5.0-jre and 33.6.0-jre occur across 13 groups; OSV lists 33.7.2 as fixed. | Determine whether game, loader, server or installed components deserialize untrusted Java objects containing these collections; verify a compatible upstream runtime update. |
| [GHSA-558v-64gr-wgg4](https://osv.dev/vulnerability/GHSA-558v-64gr-wgg4), CVE-2026-59901 | A malformed bzip2 stream can hang Netty's `Bzip2Decoder` event loop. Affected `netty-codec` or `netty-codec-compression` 4.1.77.Final, 4.1.82.Final, 4.1.97.Final, 4.1.115.Final, 4.1.118.Final, 4.2.7.Final and 4.2.15.Final occur across 10 groups; OSV lists fixes 4.1.136.Final and 4.2.16.Final. | Establish whether any reachable pipeline accepts attacker-controlled bzip2 streams, including multiplayer and loader paths. |
| [GHSA-mj4r-2hfc-f8p6](https://osv.dev/vulnerability/GHSA-mj4r-2hfc-f8p6), CVE-2026-42583 | Netty's `Lz4FrameDecoder` may allocate up to 32 MiB from a small malformed block. Versions 4.1.77.Final, 4.1.82.Final, 4.1.97.Final, 4.1.115.Final, 4.1.118.Final and 4.2.7.Final of the relevant codec packages occur across 10 groups; OSV lists fixes 4.1.133.Final and 4.2.13.Final. | Identify any network or other untrusted input reaching that decoder and verify upstream compatibility. |
| [GHSA-3qp7-7mw8-wx86](https://osv.dev/vulnerability/GHSA-3qp7-7mw8-wx86), CVE-2026-44249 | Incorrect IPv6 subnet masking in `IpSubnetFilterRule` can bypass a configured Netty access filter. `netty-handler` 4.1.77.Final, 4.1.82.Final, 4.1.97.Final, 4.1.115.Final, 4.1.118.Final and 4.2.7.Final occur across 10 groups; OSV lists fixes 4.1.135.Final and 4.2.15.Final. | Determine whether relevant servers or components rely on this IPv6 filter for access control. |
| [GHSA-c653-97m9-rcg9](https://osv.dev/vulnerability/GHSA-c653-97m9-rcg9), CVE-2026-50010 | A plain `X509TrustManager` wrapped by Netty can silently omit hostname verification. The same six recorded `netty-handler` versions span 10 groups; OSV lists fixes 4.1.135.Final and 4.2.15.Final. | Inspect actual TLS client trust-manager construction, including loader and server integrations; do not infer safety from the mod JAR alone. |
| [GHSA-x4gw-5cx5-pgmh](https://osv.dev/vulnerability/GHSA-x4gw-5cx5-pgmh), CVE-2026-45416 | Certain default Netty SNI handlers can reserve up to 16 MiB for a short attacker-controlled ClientHello. The same six recorded `netty-handler` versions span 10 groups; OSV lists fixes 4.1.135.Final and 4.2.15.Final. | Determine whether any reachable game, server or installed component creates the affected TLS SNI handlers and whether bounds are configured. |
| [GHSA-mcr4-qmvw-px4g](https://osv.dev/vulnerability/GHSA-mcr4-qmvw-px4g), CVE-2026-106451 | LZ4 native extraction in a shared writable temporary directory can allow another local user to replace a native library. `org.lz4:lz4-java` 1.8.0 and `at.yawk.lz4:lz4-java` 1.8.1 and 1.10.1 occur across eight groups. OSV records 1.11.4 as fixed for the `at.yawk` package; the `org.lz4` range ends at 1.8.1 without a fixed event. | Verify native extraction, temporary-directory permissions and actual platform use for each installation; assess a game-compatible upstream update for each package. |

All seven remain **Further investigation** and failing. All observed vulnerable
versions also occur in recorded Minecraft runtime inventories, though individual
occurrences may additionally appear in Gradle inventories. The mod does not
bundle those libraries. A [class-file inventory](dependency-evidence/high-advisories-2026-11-12/mod-class-reference-inventory.json)
of all 13 exact proposed JARs found no direct class references to the specific
types listed in the [collector](dependency-evidence/high-advisories-2026-11-12/check_mod_references.py).
That narrow observation does not cover reflection, indirect calls, Minecraft,
Fabric, multiplayer services or other installed mods and cannot establish
non-applicability. No residual risk has been accepted and no Minecraft-managed
library override is proposed without compatibility evidence.
