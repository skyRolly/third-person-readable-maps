# Issue 45: exact-source audit and credential follow-up

This is a work in progress, not a release authorization or risk acceptance.
Candidate and integrated counts are separate group/package/version/advisory
occurrences. Scopes within an occurrence are retained individually; they are not
independent CVEs or proof of exploitation. Issue #46 remains the separate GPU and
multiplayer acceptance gate.

## Fresh source-bound monitoring

The [candidate run 44940017926](https://github.com/skyRolly/third-person-readable-maps/actions/runs/44940017926)
and [integrated run 44940018290](https://github.com/skyRolly/third-person-readable-maps/actions/runs/44940018290)
used diagnostic coordination commit `01ba93db13d977e3bb0bf3400a6e373d35ff14e7`.
The diagnostic changes exported evidence and guarded credential inheritance;
they did not change the audit comparison or candidate source. Every source
Wrapper preflight and Gradle snapshot step passed. All ten candidate and all
three integrated OSV jobs failed. Each Gradle 9.9.2 upstream advisory check
completed with zero matches, which says nothing about other dependencies. The
[current-main candidate run 44939599991](https://github.com/skyRolly/third-person-readable-maps/actions/runs/44939599991)
independently returned 385 failing matches, zero disappeared baseline matches,
and passed all ten Wrapper preflights. Its companion
[maintenance run 44939599352](https://github.com/skyRolly/third-person-readable-maps/actions/runs/44939599352)
failed all three OSV jobs after successful snapshot generation and wrapper checks.

The fresh reports, original Gradle snapshots and Gradle-tool reports are retained
without modifying earlier evidence in the adjacent exact-source archive. Their
source SHAs, runtime scopes, advisory fingerprints, detailed OSV records and
SHA-256 hashes are in the reports and archive index. A snapshot resolution is not
a complete inventory of plugin classpaths, non-Maven packages, platform native
code, arbitrary launcher additions or other installed mods.

The [finding index](../dependency-evidence/issue45-exact-source-2026-11-21-v2/finding-index.json) retains every exact-source match and its report hash; the [archive index](../dependency-evidence/issue45-exact-source-2026-11-21-v2/archive-index.json) records hashes of original reports and snapshots. All matches below remain failing. The candidate set has 180 distinct package-version/advisory pairs and 88 advisory IDs; the integrated set has 63 pairs and 40 IDs. These identities overlap across groups and between sets.

| Source group | PR / target | Source SHA | Critical | High | Moderate | Low |
| --- | --- | --- | ---: | ---: | ---: |
| 1.14-1.14.4 | #23 | `b6f7632af554a0e51c7d8c421c17adc893cc1379` | 3 | 9 | 13 | 2 |
| 1.15-1.16.5 | #21 | `4231b420749db2bbab3cf3e3a7825fc2516511d9` | 3 | 9 | 13 | 2 |
| 1.17-1.19.2 | #20 | `06b350856605011c1549d51d6edd3d351c5021c0` | 3 | 17 | 31 | 2 |
| 1.19.3 | #22 | `a9cd58a4efdb5e9505006bb62914a89e19df0d71` | 1 | 7 | 15 | 1 |
| 1.19.4-1.20.4 | #19 | `9326fbbbdfa79d54512b655282c53739d3a4be25` | 2 | 15 | 24 | 1 |
| 1.20.5-1.20.6 | #18 | `aa64abb6fd47c0a634dad03fb445634f3715a624` | 1 | 10 | 16 | 1 |
| 1.21-1.21.1 | #17 | `a62780429512a4e4072b56348e06059d127cfb1d` | 1 | 10 | 16 | 1 |
| 1.21.2-1.21.3 | #16 | `d823a91c96b9bc80446116b44cd7568c70048c0d` | 1 | 18 | 25 | 1 |
| 1.21.4-1.21.8 | #14 | `f63e12da0ccbf70acb41393211c864b057f5cd7c` | 2 | 23 | 26 | 1 |
| 1.21.9-1.21.10 | #13 | `5dd5d433fd785bf51f13827babf51a76d09f7cdb` | 1 | 23 | 33 | 2 |
| 1.21.11 | `mc/1.21.11` | `ec61f4cf3c6d72558c35e919bf865fa9b51bf0d1` | 1 | 15 | 24 | 1 |
| 26.1-26.2 | `mc/26.1-26.2` | `b7620ef8174180698cc36d273981aeadd3447941` | 2 | 19 | 31 | 1 |
| 26.3 | `mc/26.3` | `38bac1c010250838b47f6f16f98a5ced5e0d7b8a` | 1 | 2 | 7 | 1 |

Candidate totals: 18 Critical, 141 High, 212 Moderate, 14 Low (385). Integrated totals: 4 Critical, 36 High, 62 Moderate, 3 Low (105). Across the two sets, 424 occurrences have both Gradle and game-runtime scopes and 66 have runtime scopes only; none is Gradle-only in these reports. These scope labels describe inventory membership, not proof of which configuration invokes an API. The older proposed-JAR inspection did not find embedded third-party classes or nested JARs for the critical cases; it is not a fresh packaging examination for every current-source finding.

## Critical investigation and remaining proof

The [historical default-launcher survey](../dependency-evidence/log4j-default-launcher-2026-11-14/)
checked Mojang manifest hashes, the logging file hash and launcher argument for
18 older runtime versions: each selected `client-1.12.xml` through
`-Dlog4j.configurationFile=${path}`. Its file pattern contains `%msg{nolookups}`;
the console uses Mojang's `LegacyXMLLayout`. This is evidence about the
published default, not the effective configuration on every launcher, the
implementation of the custom layout, all input paths, or other mods.

- [GHSA-c4c3-7fpv-j4q5 / CVE-2026-75595](https://github.com/netty/netty/security/advisories/GHSA-c4c3-7fpv-j4q5):
  a fragmented ClientHello can cause SNI server routing to fall back to a
  default SSL context. The described authentication bypass additionally requires
  per-SNI mutual TLS as the only gate, a permissive fallback and no independent
  certificate check. Upstream gives 4.1.137.Final and 4.2.17.Final as fixes.
  Minecraft manifests supply affected versions, some also resolved by Gradle.
  Existing game-JAR searches do not trace transitive library, reflection,
  launcher or mod configurations. Effective Netty server pipelines and fallback
  authentication remain unverified. The project-specific finding remains
  **Further investigation**, with game-managed remediation upstream-dependent;
  no blanket runtime override or non-applicability is justified.
- [GHSA-jfh8-c2jp-5v3q / CVE-2021-44228](https://github.com/advisories/GHSA-jfh8-c2jp-5v3q):
  affected historical Log4j Core 2.8.1 and 2.14.1 can perform JNDI lookups
  from attacker-controlled log data under vulnerable configurations. GitHub's
  advisory lists 2.12.2 and 2.15.0 as the respective fixed endpoints for the
  affected lines; later Log4j advisories must also be addressed. The default
  logging evidence narrows but does not establish effective configuration or
  eliminate all lookup paths. **Further investigation** remains blocking.
- [GHSA-7rjr-3q55-vv33 / CVE-2021-45046](https://github.com/advisories/GHSA-7rjr-3q55-vv33):
  the earlier mitigation was incomplete for affected non-default context lookup
  and MDC layouts. GitHub lists 2.12.2 and 2.16.0 for the relevant lines. The
  advisory says `formatMsgNoLookups` alone is insufficient. Effective layouts,
  lookup class availability and reachable attacker-controlled context need
  testing. **Further investigation** remains blocking.
- [GHSA-fxph-q3j8-mv87 / CVE-2017-5645](https://github.com/advisories/GHSA-fxph-q3j8-mv87):
  Core 2.8.1 is affected; 2.8.2 is the upstream endpoint. The vulnerable path
  requires a Log4j TCP/UDP socket server deserializing untrusted serialized log
  events. The default launcher file does not prove whether any effective
  configuration or component starts one. **Further investigation** remains
  blocking.

The [older critical disposition evidence](../dependency-evidence/log4j-default-launcher-2026-11-14/critical-dispositions.json)
and [Netty analysis](../dependency-evidence/advisory-dispositions/netty-critical-tls-2026-11-15.json)
classify remediation ownership, not verified absence of reachable behavior. The
new reports bind the affected package versions and exact Minecraft runtime
scopes to the current source heads. None of these observations proves a client
exploit or proves safety.

## High and remaining families

The source reports preserve each advisory's upstream affected ranges, aliases,
severity and references. Prior investigation material includes the
[high advisory evidence](../dependency-evidence/high-advisories-2026-11-13/),
[Netty high review](../dependency-evidence/netty-high-review-2026-11-15.json)
and [moderate/low review](../dependency-evidence/moderate-low-advisory-review-2026-11-13.json).
Netty findings require tracing actual HTTP, decoder, IP-filter or TLS pipeline
use; Log4j findings require effective layouts, appenders and lookup paths; LZ4
requires tracing stream constructors and untrusted input; Jackson requires
checking the affected parsing or polymorphic-deserialization configurations;
Guava and Commons findings require the specific vulnerable API and input path.
Individual advisory triggers and fixed versions differ. A package being
Minecraft-supplied or absent from the mod JAR does not establish non-reachability.
The archived inventory does not establish a compatible mod-controlled upgrade for
these game-owned dependencies. No override or risk acceptance was applied.
Unresolved records and changes in advisory data remain subject to the existing
fail-closed checks and release policy.

## Credential isolation and owner action

The [original factual record](late-review-2026-11-16.md#local-build-credential-isolation)
identified a repository-write-capable `GH_TOKEN` in the environment inherited by
initial local Gradle subprocesses. A literal-value scan of 25 captured logs
found no token; arbitrary build/plugin network activity or other surfaces were
not ruled out. Full permissions and lifetime were not established. **The token
owner should review available GitHub and other audit activity and revoke or rotate
that token**, since disclosure cannot be excluded. This cannot be completed or
verified from the available evidence.

For future local Linux builds, `python3 scripts/isolated_gradle.py --root PATH --
clean build` passes only selected tool/locale variables, uses a disposable HOME
and Gradle home, and forces `--no-daemon`. It does not forward GitHub, cloud,
proxy, Gradle-option or SSH-agent environment credentials. This may require
network/tool configuration changes in environments relying on a proxy. It is not
a sandbox: build code can still access files and the network available to the
user, and direct `./gradlew` invocations bypass this helper. Continue reviewing
source and plugins and use isolated machines when needed.

The hosted candidate and integrated snapshot workflows use the pinned Gradle
action in `generate-and-upload` mode. Its default GitHub token input is
unnecessary in that mode and is inherited by its Gradle subprocess through the
action input environment. The updated workflows explicitly supply an empty input
and run an init-script check that rejects nonempty `GH_TOKEN`, `GITHUB_TOKEN`,
and `INPUT_GITHUB-TOKEN` before project configuration. All 13 modified snapshot
steps passed that check in the diagnostic runs linked above. This checks those
names in those Gradle processes; it does not prove absence of every possible
credential source or sandbox untrusted build code. Credentialed API checks use
separate steps, and the read-only job token and runner artifact infrastructure
are separate from the historical local write-capable token.


## Commons Compress Realms library correction — 2026-11-21

A follow-up scan of the exact Minecraft runtime libraries found that the earlier client-only TAR caller statement was incomplete for Minecraft 1.14–1.14.3. The exact official version manifests map those clients to Mojang Realms 1.14.14, 1.14.15, 1.14.16, and 1.14.17 respectively. Each artifact matched its manifest SHA-1 and size and the recorded SHA-256. All four contain `realms/c.class` with a literal `TarArchiveInputStream` reference; the extraction class SHA-256 is `f3eb2f48eb3b81b43f84cb8e67961f7f52ea9f39a3bbe9ebf4dd3fd516d50ee0`. Related downloader and caller classes `realms/ah.class` and `realms/ab.class` were also hash-checked and are byte-identical across the four artifacts.

CFR 0.152 inspection of the exact 1.14.17 Realms JAR confirmed the path: `realms/ab` obtains a `WorldDownload` and opens the download UI; `realms/ah` starts the download worker; `realms/c` uses `WorldDownload.downloadLink`, issues an HTTP GET, downloads the gzip TAR, constructs `GzipCompressorInputStream` and `TarArchiveInputStream`, calls `getNextTarEntry`, and extracts entries. The earlier 1.14.4 and 1.17.1 client traces cover the next versions, so source-bound component reachability is now established for Minecraft 1.14–1.17.1 behind an optional Realms download action.

This corrects the reachability scope only. It does not establish that a Realm owner controls the malformed TAR metadata required by CVE-2021-35517, and no isolated exact-version reproducer or end-to-end test has been run. The finding remains **Further investigation**, blocking, and game-managed. No dependency override or source fix was applied. The 490 archived advisory occurrences and all severity counts are unchanged.

## Log4j attacker-controlled chat input trace — 2026-11-21

The exact Minecraft 1.14.4 client (Log4j Core 2.8.1) and 1.17.1 client (Log4j Core 2.14.1) were decompiled locally with CFR 0.152. In both, the server-to-client `ClientboundChatPacket` reads a component from the network buffer, `ClientPacketListener.handleChat` passes it to the chat component, and that component logs the resulting text with the parameterized call `Logger.info("[CHAT] {}", component.getString())`. Exact client artifact SHA-256 values and the three caller class hashes per sample are in the new source-bound observation file. This establishes a first-party attacker-controlled log input path; it is not a full in-game exploit test.

The exact version metadata for both samples specifies `-Dlog4j.configurationFile=${path}` and the same hash-bound external `client-1.12.xml`. Its console appender uses Mojang Patchy's `LegacyXMLLayout`; its file appender uses `%msg{nolookups}`. The isolated parameterized `[CHAT]` probe with a no-network JNDI factory made zero lookup attempts for this external configuration. The game binaries also contain embedded fallback XML with `%msg%n`. Against Log4j 2.14.1 / Patchy 2.1.6, the matching parameterized probe made two local factory calls under that fallback. No network provider was used. This means the standard metadata configuration is a conditional mitigation, not general non-applicability; production launch arguments and the behavior of supported third-party launchers were not captured.

For the 2.8.1 sample, Minecraft's manifest order puts Patchy 1.3.9 before Log4j Core, and Patchy supplies a `JndiLookup` stub whose methods return null. The Patchy-first fallback probe made zero local JNDI calls. Reversing the order caused two local calls, demonstrating that classpath order changes the result; that reversed order is a synthetic condition and was not observed in the official manifest. Log4j 2.8.1 message marker expansion still depends on configuration, and this observation does not clear the affected package for modified launchers or mods.

The `GHSA-jfh8-c2jp-5v3q` record remains **Further investigation** and release-blocking. The `GHSA-7rjr-3q55-vv33` and `GHSA-fxph-q3j8-mv87` findings also remain blocking: the inspected chat path does not itself populate ThreadContext/MDC, and the default/embedded XML does not start Log4j socket servers, but launcher overrides, third-party appenders, reflective paths, and mods were not exhaustively ruled out. New parameterized probes are preserved separately; earlier probe reports and historical logging evidence were not overwritten. Advisory totals and dispositions are unchanged.
