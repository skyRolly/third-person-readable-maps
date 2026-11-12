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
individual disposition. Re-scan final source-bound `1.0.0` dependency
inventories; do not treat an absent result, unbundled dependency, or this
worklist as an approval.
