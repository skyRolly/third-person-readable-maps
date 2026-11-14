# Security advisory ledger

Reviewed 2026-11-04. The [structured ledger](security-advisories.json) is the comparison source of truth. Each key is `group|canonical Maven purl|OSV ID`; scopes distinguish Gradle resolution and each runtime manifest. Aliases are preserved rather than counted as separate advisories. Raw OSV records, including severity vectors, complete affected ranges and references, are stored once under `advisories` in that file. [Inventory evidence](dependency-evidence/) binds each source SHA and hash-verified game manifest.

## Disposition and release policy

Current matches remain unresolved. The 26.2 runtime-only `netty-handler` 4.2.15.Final occurrence of GHSA-c4c3-7fpv-j4q5 is classified **Upstream-dependent** for remediation; the other records remain **Further investigation**. Reachability of the critical occurrence is still unproven and it remains failing. None is a verified non-applicability determination or an accepted risk. No game-library overrides were applied. The ledger distinguishes Fixed, Actionable, Upstream-dependent, Not applicable, Risk accepted, Further investigation, and Resolved upstream. Risk acceptance requires an identified independent decision and reference. A reviewed record does not authorize release.

There is no repository SECURITY.md. Supported surfaces are the client-only Fabric mod and the published compatibility groups; source evidence is each branch's `build.gradle`, Fabric metadata, `ReadableMapSurface.java`, and `ReadableMapLayerMixin.java`. Those classes render maps using game APIs and contain no direct HTTP, TLS, logging-layout, native deserialization, or LZ4 entry point. This limits the mod-specific claim but does not prove that the hosting Minecraft process cannot reach an affected feature. Dependency origin is established by version manifests, not merely snapshot `relationship: direct`. Game libraries can run both in installed clients and development runs; the build does not bundle them.

## Additional static evidence

[Runtime feature evidence](dependency-evidence/runtime-features.json) records a
constant-pool search of all six hash-verified game client JARs and the official,
hash-verified default logging configurations. RegionFileVersion (`erz` on
1.21.11) constructs `LZ4BlockInputStream(InputStream)`; the searched direct call
does not set `stopOnEmptyBlock=false`. This narrows GHSA-343h-94h5-c4wr's direct
game path but does not exhaust library/reflective paths. Default logging uses
LegacyXMLLayout/PatternLayout rather than the named SocketAppender,
Rfc5424Layout or JsonTemplateLayout features; the custom LegacyXMLLayout
implementation and operator/other-mod configuration remain unverified. Targeted
Netty/Guava feature references were not established by this game-JAR-only search;
transitive library implementations, reflection and other installed mods were
outside it. None of these narrow negative observations justifies a game-wide
Not applicable disposition. Specific evidence/proof gaps are attached to every
structured record. No runtime PoC or game-wide exploitability proof is claimed.

## Current counts

| Group | Gradle packages | Runtime packages per version | Affected package/version pairs across scopes | Advisory/package/version/group matches | Unique advisories |
| --- | ---: | --- | ---: | ---: | ---: |
| 1.21.11 | 86 | 1.21.11: 53 | 10 | 41 | 40 |
| 26.1-26.2 | 84 | 26.1: 53; 26.1.1: 53; 26.1.2: 53; 26.2: 57 | 15 | 53 | 39 |
| 26.3 | 86 | 26.3: 56 | 5 | 11 | 11 |

Total: 40 unique advisories; 105 advisory/package/version/group combinations. Fixed: 0; Actionable with a verified direct compatible fix: 0; Further investigation: 105; formal risk acceptances: 0. All runtime-owned matches need upstream coordination if applicable. Native binaries, non-Maven advisories and unrepresented build-plugin dependencies remain coverage gaps.

The earlier 1.21.11 report counted 85 snapshot packages; the recovered hosted snapshot has 86, including `org.gradle/gradle-core@9.8.2`. The affected-package count remains 10. This correction does not erase the historical report. Runtime inventories include all listed platform variants and normalize classifier variants to a Maven advisory package.

## Individual investigations

### GHSA-343h-94h5-c4wr

yawkat LZ4 Java: LZ4BlockInputStream with stopOnEmptyBlock=false recurses once per empty block, causing StackOverflowError

Aliases: CVE-2026-106449. Severity: **LOW**, GitHub-reviewed OSV record; vectors: CVSS_V3 CVSS:3.1/AV:N/AC:H/PR:N/UI:N/S:U/C:N/I:N/A:L.

[OSV](https://osv.dev/vulnerability/GHSA-343h-94h5-c4wr) · [GitHub advisory](https://github.com/advisories/GHSA-343h-94h5-c4wr)

Affected ranges and fixed endpoints (each release line is separate; a listed fix is not a compatibility approval):

- `at.yawk.lz4:lz4-java`: introduced 0; fixed 1.11.4.
- `org.lz4:lz4-java`: introduced 0; last_affected 1.8.1.

**Disposition: Further investigation.** Trace game LZ4BlockInputStream construction and stopOnEmptyBlock=false with attacker-controlled concatenated blocks. If reachable, request a compatible upstream game fix; do not override game-managed libraries in the mod.

| Group | Package/version | Inventory scopes | Origin / relevance |
| --- | --- | --- | --- |
| 1.21.11 | `at.yawk.lz4/lz4-java@1.8.1` | gradle, runtime/1.21.11 | Minecraft version manifests: 1.21.11; game-supplied client runtime and development classpath |
| 26.1-26.2 | `at.yawk.lz4/lz4-java@1.10.1` | gradle, runtime/26.1, runtime/26.1.1, runtime/26.1.2, runtime/26.2 | Minecraft version manifests: 26.1, 26.1.1, 26.1.2, 26.2; game-supplied client runtime and development classpath |
| 26.3 | `at.yawk.lz4/lz4-java@1.10.1` | gradle, runtime/26.3 | Minecraft version manifests: 26.3; game-supplied client runtime and development classpath |

Follow-up owner: repository maintainer and security reviewer. Re-evaluate before release, on changed game libraries or advisory scope, and no later than 2027-02-02. Runtime traces/configuration for the named vulnerable feature are still needed; uncertainty is not non-applicability.

### GHSA-38f8-5428-x5cv

Netty vulnerable to HTTP Request Smuggling due to malformed Transfer-Encoding

Aliases: CVE-2026-42585. Severity: **MODERATE**, GitHub-reviewed OSV record; vectors: CVSS_V3 CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:L/I:L/A:N.

[OSV](https://osv.dev/vulnerability/GHSA-38f8-5428-x5cv) · [GitHub advisory](https://github.com/advisories/GHSA-38f8-5428-x5cv)

Affected ranges and fixed endpoints (each release line is separate; a listed fix is not a compatibility approval):

- `io.netty:netty-codec-http`: introduced 4.2.0.Alpha1; fixed 4.2.13.Final.
- `io.netty:netty-codec-http`: introduced 0; fixed 4.1.133.Final.

**Disposition: Further investigation.** Trace HTTP Transfer-Encoding parsing across game HTTP clients/servers and any intermediaries. If reachable, request a compatible upstream game fix; do not override game-managed libraries in the mod.

| Group | Package/version | Inventory scopes | Origin / relevance |
| --- | --- | --- | --- |
| 1.21.11 | `io.netty/netty-codec-http@4.2.7.Final` | gradle, runtime/1.21.11 | Minecraft version manifests: 1.21.11; game-supplied client runtime and development classpath |
| 26.1-26.2 | `io.netty/netty-codec-http@4.2.7.Final` | gradle, runtime/26.1, runtime/26.1.1, runtime/26.1.2 | Minecraft version manifests: 26.1, 26.1.1, 26.1.2; game-supplied client runtime and development classpath |

Follow-up owner: repository maintainer and security reviewer. Re-evaluate before release, on changed game libraries or advisory scope, and no later than 2027-02-02. Runtime traces/configuration for the named vulnerable feature are still needed; uncertainty is not non-applicability.

### GHSA-3pxv-7cmr-fjr4

Apache Log4j Core: Silent log event loss in XmlLayout due to unescaped XML 1.0 forbidden characters

Aliases: CVE-2026-34480. Severity: **MODERATE**, GitHub-reviewed OSV record; vectors: CVSS_V4 CVSS:4.0/AV:N/AC:L/AT:N/PR:N/UI:N/VC:N/VI:N/VA:N/SC:N/SI:L/SA:N.

[OSV](https://osv.dev/vulnerability/GHSA-3pxv-7cmr-fjr4) · [GitHub advisory](https://github.com/advisories/GHSA-3pxv-7cmr-fjr4)

Affected ranges and fixed endpoints (each release line is separate; a listed fix is not a compatibility approval):

- `org.apache.logging.log4j:log4j-core`: introduced 2.0-alpha1; fixed 2.25.4.
- `org.apache.logging.log4j:log4j-core`: introduced 3.0.0-alpha1; last_affected 3.0.0-beta3.

**Disposition: Further investigation.** Inspect installed logging configuration for XmlLayout and attacker-controlled forbidden XML characters. If reachable, request a compatible upstream game fix; do not override game-managed libraries in the mod.

| Group | Package/version | Inventory scopes | Origin / relevance |
| --- | --- | --- | --- |
| 1.21.11 | `org.apache.logging.log4j/log4j-core@2.25.2` | gradle, runtime/1.21.11 | Minecraft version manifests: 1.21.11; game-supplied client runtime and development classpath |
| 26.1-26.2 | `org.apache.logging.log4j/log4j-core@2.25.2` | gradle, runtime/26.1, runtime/26.1.1, runtime/26.1.2 | Minecraft version manifests: 26.1, 26.1.1, 26.1.2; game-supplied client runtime and development classpath |

Follow-up owner: repository maintainer and security reviewer. Re-evaluate before release, on changed game libraries or advisory scope, and no later than 2027-02-02. Runtime traces/configuration for the named vulnerable feature are still needed; uncertainty is not non-applicability.

### GHSA-3qp7-7mw8-wx86

Netty has an IPv6 Subnet Filter Bypass via Incorrect Comparator Masking

Aliases: CVE-2026-44249. Severity: **HIGH**, GitHub-reviewed OSV record; vectors: CVSS_V3 CVSS:3.1/AV:N/AC:H/PR:N/UI:N/S:U/C:H/I:H/A:H.

[OSV](https://osv.dev/vulnerability/GHSA-3qp7-7mw8-wx86) · [GitHub advisory](https://github.com/advisories/GHSA-3qp7-7mw8-wx86)

Affected ranges and fixed endpoints (each release line is separate; a listed fix is not a compatibility approval):

- `io.netty:netty-handler`: introduced 4.2.0.Final; fixed 4.2.15.Final.
- `io.netty:netty-handler`: introduced 0; fixed 4.1.135.Final.

**Disposition: Further investigation.** Determine use of IPv6 subnet filters as a security boundary and whether comparator masking bypass is reachable. If reachable, request a compatible upstream game fix; do not override game-managed libraries in the mod.

| Group | Package/version | Inventory scopes | Origin / relevance |
| --- | --- | --- | --- |
| 1.21.11 | `io.netty/netty-handler@4.2.7.Final` | gradle, runtime/1.21.11 | Minecraft version manifests: 1.21.11; game-supplied client runtime and development classpath |
| 26.1-26.2 | `io.netty/netty-handler@4.2.7.Final` | gradle, runtime/26.1, runtime/26.1.1, runtime/26.1.2 | Minecraft version manifests: 26.1, 26.1.1, 26.1.2; game-supplied client runtime and development classpath |

Follow-up owner: repository maintainer and security reviewer. Re-evaluate before release, on changed game libraries or advisory scope, and no later than 2027-02-02. Runtime traces/configuration for the named vulnerable feature are still needed; uncertainty is not non-applicability.

### GHSA-445c-vh5m-36rj

Apache Log4j Core: log injection in `Rfc5424Layout` due to silent configuration incompatibility

Aliases: CVE-2026-34478. Severity: **MODERATE**, GitHub-reviewed OSV record; vectors: CVSS_V4 CVSS:4.0/AV:N/AC:L/AT:N/PR:N/UI:N/VC:N/VI:N/VA:N/SC:N/SI:L/SA:N.

[OSV](https://osv.dev/vulnerability/GHSA-445c-vh5m-36rj) · [GitHub advisory](https://github.com/advisories/GHSA-445c-vh5m-36rj)

Affected ranges and fixed endpoints (each release line is separate; a listed fix is not a compatibility approval):

- `org.apache.logging.log4j:log4j-core`: introduced 2.21.0; fixed 2.25.4.
- `org.apache.logging.log4j:log4j-core`: introduced 3.0.0-beta1; last_affected 3.0.0-beta3.

**Disposition: Further investigation.** Inspect Rfc5424Layout and escapeNewLine/configuration combinations with attacker-controlled logs. If reachable, request a compatible upstream game fix; do not override game-managed libraries in the mod.

| Group | Package/version | Inventory scopes | Origin / relevance |
| --- | --- | --- | --- |
| 1.21.11 | `org.apache.logging.log4j/log4j-core@2.25.2` | gradle, runtime/1.21.11 | Minecraft version manifests: 1.21.11; game-supplied client runtime and development classpath |
| 26.1-26.2 | `org.apache.logging.log4j/log4j-core@2.25.2` | gradle, runtime/26.1, runtime/26.1.1, runtime/26.1.2 | Minecraft version manifests: 26.1, 26.1.1, 26.1.2; game-supplied client runtime and development classpath |

Follow-up owner: repository maintainer and security reviewer. Re-evaluate before release, on changed game libraries or advisory scope, and no later than 2027-02-02. Runtime traces/configuration for the named vulnerable feature are still needed; uncertainty is not non-applicability.

### GHSA-4mp9-239f-g9hg

Netty: WebSockets V07/V08 handshaker missing Connection/Upgrade validation

Aliases: CVE-2026-59898. Severity: **MODERATE**, GitHub-reviewed OSV record; vectors: CVSS_V4 CVSS:4.0/AV:N/AC:H/AT:N/PR:N/UI:N/VC:N/VI:N/VA:N/SC:L/SI:L/SA:N.

[OSV](https://osv.dev/vulnerability/GHSA-4mp9-239f-g9hg) · [GitHub advisory](https://github.com/advisories/GHSA-4mp9-239f-g9hg)

Affected ranges and fixed endpoints (each release line is separate; a listed fix is not a compatibility approval):

- `io.netty:netty-codec-http`: introduced 4.2.0.Final; fixed 4.2.16.Final.
- `io.netty:netty-codec-http`: introduced 0; fixed 4.1.136.Final.

**Disposition: Further investigation.** Determine whether WebSocket V07/V08 server handshakers process untrusted upgrades. If reachable, request a compatible upstream game fix; do not override game-managed libraries in the mod.

| Group | Package/version | Inventory scopes | Origin / relevance |
| --- | --- | --- | --- |
| 1.21.11 | `io.netty/netty-codec-http@4.2.7.Final` | gradle, runtime/1.21.11 | Minecraft version manifests: 1.21.11; game-supplied client runtime and development classpath |
| 26.1-26.2 | `io.netty/netty-codec-http@4.2.15.Final` | runtime/26.2 | Minecraft version manifests: 26.2; game-supplied client runtime and development classpath |
| 26.1-26.2 | `io.netty/netty-codec-http@4.2.7.Final` | gradle, runtime/26.1, runtime/26.1.1, runtime/26.1.2 | Minecraft version manifests: 26.1, 26.1.1, 26.1.2; game-supplied client runtime and development classpath |

Follow-up owner: repository maintainer and security reviewer. Re-evaluate before release, on changed game libraries or advisory scope, and no later than 2027-02-02. Runtime traces/configuration for the named vulnerable feature are still needed; uncertainty is not non-applicability.

### GHSA-4v53-57pg-c464

yawkat LZ4 Java: LZ4BlockInputStream allocates an unvalidated compressed length from the stream header

Aliases: CVE-2026-106452. Severity: **MODERATE**, GitHub-reviewed OSV record; vectors: CVSS_V3 CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:N/I:N/A:L.

[OSV](https://osv.dev/vulnerability/GHSA-4v53-57pg-c464) · [GitHub advisory](https://github.com/advisories/GHSA-4v53-57pg-c464)

Affected ranges and fixed endpoints (each release line is separate; a listed fix is not a compatibility approval):

- `at.yawk.lz4:lz4-java`: introduced 0; fixed 1.11.2.
- `org.lz4:lz4-java`: introduced 0; last_affected 1.8.1.

**Disposition: Further investigation.** Trace untrusted LZ4Block stream compressed-length validation and caller allocation limits. If reachable, request a compatible upstream game fix; do not override game-managed libraries in the mod.

| Group | Package/version | Inventory scopes | Origin / relevance |
| --- | --- | --- | --- |
| 1.21.11 | `at.yawk.lz4/lz4-java@1.8.1` | gradle, runtime/1.21.11 | Minecraft version manifests: 1.21.11; game-supplied client runtime and development classpath |
| 26.1-26.2 | `at.yawk.lz4/lz4-java@1.10.1` | gradle, runtime/26.1, runtime/26.1.1, runtime/26.1.2, runtime/26.2 | Minecraft version manifests: 26.1, 26.1.1, 26.1.2, 26.2; game-supplied client runtime and development classpath |
| 26.3 | `at.yawk.lz4/lz4-java@1.10.1` | gradle, runtime/26.3 | Minecraft version manifests: 26.3; game-supplied client runtime and development classpath |

Follow-up owner: repository maintainer and security reviewer. Re-evaluate before release, on changed game libraries or advisory scope, and no later than 2027-02-02. Runtime traces/configuration for the named vulnerable feature are still needed; uncertainty is not non-applicability.

### GHSA-558v-64gr-wgg4

Netty: [Bzip2Decoder] Infinite Loop in RLE State Machine Leads to Event-Loop Thread Hang

Aliases: CVE-2026-59901. Severity: **HIGH**, GitHub-reviewed OSV record; vectors: CVSS_V4 CVSS:4.0/AV:N/AC:L/AT:N/PR:N/UI:N/VC:N/VI:N/VA:H/SC:N/SI:N/SA:N.

[OSV](https://osv.dev/vulnerability/GHSA-558v-64gr-wgg4) · [GitHub advisory](https://github.com/advisories/GHSA-558v-64gr-wgg4)

Affected ranges and fixed endpoints (each release line is separate; a listed fix is not a compatibility approval):

- `io.netty:netty-codec-compression`: introduced 4.2.0.Final; fixed 4.2.16.Final.
- `io.netty:netty-codec`: introduced 0; fixed 4.1.136.Final.

**Disposition: Further investigation.** Identify Bzip2Decoder use in game network pipelines and whether untrusted RLE state can hang the event loop. If reachable, request a compatible upstream game fix; do not override game-managed libraries in the mod.

| Group | Package/version | Inventory scopes | Origin / relevance |
| --- | --- | --- | --- |
| 1.21.11 | `io.netty/netty-codec-compression@4.2.7.Final` | gradle, runtime/1.21.11 | Minecraft version manifests: 1.21.11; game-supplied client runtime and development classpath |
| 26.1-26.2 | `io.netty/netty-codec-compression@4.2.15.Final` | runtime/26.2 | Minecraft version manifests: 26.2; game-supplied client runtime and development classpath |
| 26.1-26.2 | `io.netty/netty-codec-compression@4.2.7.Final` | gradle, runtime/26.1, runtime/26.1.1, runtime/26.1.2 | Minecraft version manifests: 26.1, 26.1.1, 26.1.2; game-supplied client runtime and development classpath |

Follow-up owner: repository maintainer and security reviewer. Re-evaluate before release, on changed game libraries or advisory scope, and no later than 2027-02-02. Runtime traces/configuration for the named vulnerable feature are still needed; uncertainty is not non-applicability.

### GHSA-57rv-r2g8-2cj3

Netty has HttpClientCodec response desynchronization

Aliases: CVE-2026-42584. Severity: **HIGH**, GitHub-reviewed OSV record; vectors: CVSS_V3 CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:L/I:L/A:L.

[OSV](https://osv.dev/vulnerability/GHSA-57rv-r2g8-2cj3) · [GitHub advisory](https://github.com/advisories/GHSA-57rv-r2g8-2cj3)

Affected ranges and fixed endpoints (each release line is separate; a listed fix is not a compatibility approval):

- `io.netty:netty-codec-http`: introduced 4.2.0.Alpha1; fixed 4.2.13.Final.
- `io.netty:netty-codec-http`: introduced 0; fixed 4.1.133.Final.

**Disposition: Further investigation.** Trace HttpClientCodec response parsing of untrusted HTTP responses and connection reuse. If reachable, request a compatible upstream game fix; do not override game-managed libraries in the mod.

| Group | Package/version | Inventory scopes | Origin / relevance |
| --- | --- | --- | --- |
| 1.21.11 | `io.netty/netty-codec-http@4.2.7.Final` | gradle, runtime/1.21.11 | Minecraft version manifests: 1.21.11; game-supplied client runtime and development classpath |
| 26.1-26.2 | `io.netty/netty-codec-http@4.2.7.Final` | gradle, runtime/26.1, runtime/26.1.1, runtime/26.1.2 | Minecraft version manifests: 26.1, 26.1.1, 26.1.2; game-supplied client runtime and development classpath |

Follow-up owner: repository maintainer and security reviewer. Re-evaluate before release, on changed game libraries or advisory scope, and no later than 2027-02-02. Runtime traces/configuration for the named vulnerable feature are still needed; uncertainty is not non-applicability.

### GHSA-6cqp-g7gg-8hr5

Netty: Security Control Bypass via CORS Short-Circuit Failure

Aliases: CVE-2026-56746. Severity: **MODERATE**, GitHub-reviewed OSV record; vectors: CVSS_V3 CVSS:3.1/AV:N/AC:L/PR:N/UI:R/S:U/C:N/I:H/A:N.

[OSV](https://osv.dev/vulnerability/GHSA-6cqp-g7gg-8hr5) · [GitHub advisory](https://github.com/advisories/GHSA-6cqp-g7gg-8hr5)

Affected ranges and fixed endpoints (each release line is separate; a listed fix is not a compatibility approval):

- `io.netty:netty-codec-http`: introduced 4.2.0.Final; fixed 4.2.16.Final.
- `io.netty:netty-codec-http`: introduced 0; fixed 4.1.136.Final.

**Disposition: Further investigation.** Determine whether a game HTTP server relies on CorsHandler short-circuit denial for authorization. If reachable, request a compatible upstream game fix; do not override game-managed libraries in the mod.

| Group | Package/version | Inventory scopes | Origin / relevance |
| --- | --- | --- | --- |
| 1.21.11 | `io.netty/netty-codec-http@4.2.7.Final` | gradle, runtime/1.21.11 | Minecraft version manifests: 1.21.11; game-supplied client runtime and development classpath |
| 26.1-26.2 | `io.netty/netty-codec-http@4.2.15.Final` | runtime/26.2 | Minecraft version manifests: 26.2; game-supplied client runtime and development classpath |
| 26.1-26.2 | `io.netty/netty-codec-http@4.2.7.Final` | gradle, runtime/26.1, runtime/26.1.1, runtime/26.1.2 | Minecraft version manifests: 26.1, 26.1.1, 26.1.2; game-supplied client runtime and development classpath |

Follow-up owner: repository maintainer and security reviewer. Re-evaluate before release, on changed game libraries or advisory scope, and no later than 2027-02-02. Runtime traces/configuration for the named vulnerable feature are still needed; uncertainty is not non-applicability.

### GHSA-6cx8-rjf8-pr8g

yawkat LZ4 Java: LZ4DecompressorWithLength allocates the unvalidated size from the 4-byte length header, so a 5-byte input triggers a 1 GiB allocation and OutOfMemoryError

Aliases: CVE-2026-106453. Severity: **MODERATE**, GitHub-reviewed OSV record; vectors: CVSS_V3 CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:N/I:N/A:L.

[OSV](https://osv.dev/vulnerability/GHSA-6cx8-rjf8-pr8g) · [GitHub advisory](https://github.com/advisories/GHSA-6cx8-rjf8-pr8g)

Affected ranges and fixed endpoints (each release line is separate; a listed fix is not a compatibility approval):

- `at.yawk.lz4:lz4-java`: introduced 0; fixed 1.11.2.
- `org.lz4:lz4-java`: introduced 0; last_affected 1.8.1.

**Disposition: Further investigation.** Determine whether the game uses LZ4DecompressorWithLength on attacker-controlled lengths. If reachable, request a compatible upstream game fix; do not override game-managed libraries in the mod.

| Group | Package/version | Inventory scopes | Origin / relevance |
| --- | --- | --- | --- |
| 1.21.11 | `at.yawk.lz4/lz4-java@1.8.1` | gradle, runtime/1.21.11 | Minecraft version manifests: 1.21.11; game-supplied client runtime and development classpath |
| 26.1-26.2 | `at.yawk.lz4/lz4-java@1.10.1` | gradle, runtime/26.1, runtime/26.1.1, runtime/26.1.2, runtime/26.2 | Minecraft version manifests: 26.1, 26.1.1, 26.1.2, 26.2; game-supplied client runtime and development classpath |
| 26.3 | `at.yawk.lz4/lz4-java@1.10.1` | gradle, runtime/26.3 | Minecraft version manifests: 26.3; game-supplied client runtime and development classpath |

Follow-up owner: repository maintainer and security reviewer. Re-evaluate before release, on changed game libraries or advisory scope, and no later than 2027-02-02. Runtime traces/configuration for the named vulnerable feature are still needed; uncertainty is not non-applicability.

### GHSA-6hg6-v5c8-fphq

Apache Log4j Core: `verifyHostName` attribute silently ignored in TLS configuration

Aliases: CVE-2026-34477. Severity: **MODERATE**, GitHub-reviewed OSV record; vectors: CVSS_V4 CVSS:4.0/AV:N/AC:H/AT:N/PR:N/UI:N/VC:L/VI:N/VA:N/SC:N/SI:L/SA:N.

[OSV](https://osv.dev/vulnerability/GHSA-6hg6-v5c8-fphq) · [GitHub advisory](https://github.com/advisories/GHSA-6hg6-v5c8-fphq)

Affected ranges and fixed endpoints (each release line is separate; a listed fix is not a compatibility approval):

- `org.apache.logging.log4j:log4j-core`: introduced 2.12.0; fixed 2.25.4.
- `org.apache.logging.log4j:log4j-core`: introduced 3.0.0-alpha1; last_affected 3.0.0-beta3.

**Disposition: Further investigation.** Inspect logging TLS configuration and reliance on verifyHostName; identify network appenders. If reachable, request a compatible upstream game fix; do not override game-managed libraries in the mod.

| Group | Package/version | Inventory scopes | Origin / relevance |
| --- | --- | --- | --- |
| 1.21.11 | `org.apache.logging.log4j/log4j-core@2.25.2` | gradle, runtime/1.21.11 | Minecraft version manifests: 1.21.11; game-supplied client runtime and development classpath |
| 26.1-26.2 | `org.apache.logging.log4j/log4j-core@2.25.2` | gradle, runtime/26.1, runtime/26.1.1, runtime/26.1.2 | Minecraft version manifests: 26.1, 26.1.1, 26.1.2; game-supplied client runtime and development classpath |

Follow-up owner: repository maintainer and security reviewer. Re-evaluate before release, on changed game libraries or advisory scope, and no later than 2027-02-02. Runtime traces/configuration for the named vulnerable feature are still needed; uncertainty is not non-applicability.

### GHSA-6jqx-86gh-f27w

Netty SPDY SETTINGS frame count materializes unbounded settings map

Aliases: CVE-2026-55831. Severity: **HIGH**, GitHub-reviewed OSV record; vectors: CVSS_V3 CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:N/I:N/A:H.

[OSV](https://osv.dev/vulnerability/GHSA-6jqx-86gh-f27w) · [GitHub advisory](https://github.com/advisories/GHSA-6jqx-86gh-f27w)

Affected ranges and fixed endpoints (each release line is separate; a listed fix is not a compatibility approval):

- `io.netty:netty-codec-http`: introduced 4.2.0.Final; fixed 4.2.16.Final.
- `io.netty:netty-codec-http`: introduced 4.1.0.Final; fixed 4.1.136.Final.

**Disposition: Further investigation.** Determine whether SPDY SETTINGS decoding processes untrusted frame counts. If reachable, request a compatible upstream game fix; do not override game-managed libraries in the mod.

| Group | Package/version | Inventory scopes | Origin / relevance |
| --- | --- | --- | --- |
| 1.21.11 | `io.netty/netty-codec-http@4.2.7.Final` | gradle, runtime/1.21.11 | Minecraft version manifests: 1.21.11; game-supplied client runtime and development classpath |
| 26.1-26.2 | `io.netty/netty-codec-http@4.2.15.Final` | runtime/26.2 | Minecraft version manifests: 26.2; game-supplied client runtime and development classpath |
| 26.1-26.2 | `io.netty/netty-codec-http@4.2.7.Final` | gradle, runtime/26.1, runtime/26.1.1, runtime/26.1.2 | Minecraft version manifests: 26.1, 26.1.1, 26.1.2; game-supplied client runtime and development classpath |

Follow-up owner: repository maintainer and security reviewer. Re-evaluate before release, on changed game libraries or advisory scope, and no later than 2027-02-02. Runtime traces/configuration for the named vulnerable feature are still needed; uncertainty is not non-applicability.

### GHSA-84h7-rjj3-6jx4

Netty has a CRLF Injection vulnerability in io.netty.handler.codec.http.HttpRequestEncoder

Aliases: CVE-2025-67735. Severity: **MODERATE**, GitHub-reviewed OSV record; vectors: CVSS_V3 CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:L/I:L/A:N.

[OSV](https://osv.dev/vulnerability/GHSA-84h7-rjj3-6jx4) · [GitHub advisory](https://github.com/advisories/GHSA-84h7-rjj3-6jx4)

Affected ranges and fixed endpoints (each release line is separate; a listed fix is not a compatibility approval):

- `io.netty:netty-codec-http`: introduced 4.2.0.Alpha1; fixed 4.2.8.Final.
- `io.netty:netty-codec-http`: introduced 0; fixed 4.1.129.Final.

**Disposition: Further investigation.** Trace attacker-controlled method/URI values into HttpRequestEncoder without CRLF validation. If reachable, request a compatible upstream game fix; do not override game-managed libraries in the mod.

| Group | Package/version | Inventory scopes | Origin / relevance |
| --- | --- | --- | --- |
| 1.21.11 | `io.netty/netty-codec-http@4.2.7.Final` | gradle, runtime/1.21.11 | Minecraft version manifests: 1.21.11; game-supplied client runtime and development classpath |
| 26.1-26.2 | `io.netty/netty-codec-http@4.2.7.Final` | gradle, runtime/26.1, runtime/26.1.1, runtime/26.1.2 | Minecraft version manifests: 26.1, 26.1.1, 26.1.2; game-supplied client runtime and development classpath |

Follow-up owner: repository maintainer and security reviewer. Re-evaluate before release, on changed game libraries or advisory scope, and no later than 2027-02-02. Runtime traces/configuration for the named vulnerable feature are still needed; uncertainty is not non-applicability.

### GHSA-8c42-7qj2-3j46

Netty Vulnerable to Cache Poisoning and Information Disclosure via CORS Vary Header Overwrite

Aliases: CVE-2026-59903. Severity: **MODERATE**, GitHub-reviewed OSV record; vectors: CVSS_V3 CVSS:3.1/AV:N/AC:H/PR:N/UI:N/S:U/C:H/I:L/A:N.

[OSV](https://osv.dev/vulnerability/GHSA-8c42-7qj2-3j46) · [GitHub advisory](https://github.com/advisories/GHSA-8c42-7qj2-3j46)

Affected ranges and fixed endpoints (each release line is separate; a listed fix is not a compatibility approval):

- `io.netty:netty-codec-http`: introduced 4.2.0.Final; fixed 4.2.17.Final.
- `io.netty:netty-codec-http`: introduced 0; fixed 4.1.137.Final.

**Disposition: Further investigation.** Identify CorsHandler Vary-header overwrite with shared caches and sensitive responses. If reachable, request a compatible upstream game fix; do not override game-managed libraries in the mod.

| Group | Package/version | Inventory scopes | Origin / relevance |
| --- | --- | --- | --- |
| 1.21.11 | `io.netty/netty-codec-http@4.2.7.Final` | gradle, runtime/1.21.11 | Minecraft version manifests: 1.21.11; game-supplied client runtime and development classpath |
| 26.1-26.2 | `io.netty/netty-codec-http@4.2.15.Final` | runtime/26.2 | Minecraft version manifests: 26.2; game-supplied client runtime and development classpath |
| 26.1-26.2 | `io.netty/netty-codec-http@4.2.7.Final` | gradle, runtime/26.1, runtime/26.1.1, runtime/26.1.2 | Minecraft version manifests: 26.1, 26.1.1, 26.1.2; game-supplied client runtime and development classpath |
| 26.3 | `io.netty/netty-codec-http@4.2.16.Final` | gradle, runtime/26.3 | Minecraft version manifests: 26.3; game-supplied client runtime and development classpath |

Follow-up owner: repository maintainer and security reviewer. Re-evaluate before release, on changed game libraries or advisory scope, and no later than 2027-02-02. Runtime traces/configuration for the named vulnerable feature are still needed; uncertainty is not non-applicability.

### GHSA-c4c3-7fpv-j4q5

Netty: SNI Routing Bypass via Fragmented TLS ClientHello Causing Fallback to Default SslContext

Aliases: CVE-2026-75595. Severity: **CRITICAL**, GitHub-reviewed OSV record; vectors: CVSS_V4 CVSS:4.0/AV:N/AC:L/AT:P/PR:N/UI:N/VC:H/VI:H/VA:N/SC:N/SI:N/SA:N.

[OSV](https://osv.dev/vulnerability/GHSA-c4c3-7fpv-j4q5) · [GitHub advisory](https://github.com/advisories/GHSA-c4c3-7fpv-j4q5)

Affected ranges and fixed endpoints (each release line is separate; a listed fix is not a compatibility approval):

- `io.netty:netty-handler`: introduced 4.2.0.Final; fixed 4.2.17.Final.
- `io.netty:netty-handler`: introduced 0; fixed 4.1.137.Final.

**Disposition:** The `26.2` runtime-only `netty-handler` 4.2.15.Final occurrence is **Upstream-dependent** for a compatible runtime update; the other occurrences remain **Further investigation**. The [upstream advisory](https://github.com/netty/netty/security/advisories/GHSA-c4c3-7fpv-j4q5) describes fragmented ClientHello fallback and the additional conditions for an mTLS bypass, and identifies 4.2.17.Final as fixed. The [GitHub advisory API response](dependency-evidence/ghsa-c4c3-2026-11-14.json) was retrieved on November 14; its SHA-256 is `1ef10fdd35708ed6bc960f39a884c04fb8fb702a602e18b414e819a0a9e87113`. The recorded 26.2 game JAR search found no direct `SniHandler` or `AbstractSniHandler` reference, but does not cover transitive libraries, reflection, configuration or other installed components. Trace those paths; the critical occurrence remains failing and no risk is accepted.

| Group | Package/version | Inventory scopes | Origin / relevance |
| --- | --- | --- | --- |
| 1.21.11 | `io.netty/netty-handler@4.2.7.Final` | gradle, runtime/1.21.11 | Minecraft version manifests: 1.21.11; game-supplied client runtime and development classpath |
| 26.1-26.2 | `io.netty/netty-handler@4.2.15.Final` | runtime/26.2 | Minecraft 26.2 runtime manifest; the recorded Gradle inventory does not contain this version |
| 26.1-26.2 | `io.netty/netty-handler@4.2.7.Final` | gradle, runtime/26.1, runtime/26.1.1, runtime/26.1.2 | Minecraft version manifests: 26.1, 26.1.1, 26.1.2; game-supplied client runtime and development classpath |
| 26.3 | `io.netty/netty-handler@4.2.16.Final` | gradle, runtime/26.3 | Minecraft version manifests: 26.3; game-supplied client runtime and development classpath |

Follow-up owner: repository maintainer and security reviewer. Re-evaluate before release, on changed game libraries or advisory scope, and no later than 2027-02-02. Runtime traces/configuration for the named vulnerable feature are still needed; uncertainty is not non-applicability.

### GHSA-c653-97m9-rcg9

Netty: Wrapping plain trust manager silently disables hostname verification

Aliases: CVE-2026-50010. Severity: **HIGH**, GitHub-reviewed OSV record; vectors: CVSS_V3 CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:N/A:N.

[OSV](https://osv.dev/vulnerability/GHSA-c653-97m9-rcg9) · [GitHub advisory](https://github.com/advisories/GHSA-c653-97m9-rcg9)

Affected ranges and fixed endpoints (each release line is separate; a listed fix is not a compatibility approval):

- `io.netty:netty-handler`: introduced 4.2.0.Final; fixed 4.2.15.Final.
- `io.netty:netty-handler`: introduced 0; fixed 4.1.135.Final.

**Disposition: Further investigation.** Trace wrapping of plain trust managers and expected hostname verification in game HTTP/TLS clients. If reachable, request a compatible upstream game fix; do not override game-managed libraries in the mod.

| Group | Package/version | Inventory scopes | Origin / relevance |
| --- | --- | --- | --- |
| 1.21.11 | `io.netty/netty-handler@4.2.7.Final` | gradle, runtime/1.21.11 | Minecraft version manifests: 1.21.11; game-supplied client runtime and development classpath |
| 26.1-26.2 | `io.netty/netty-handler@4.2.7.Final` | gradle, runtime/26.1, runtime/26.1.1, runtime/26.1.2 | Minecraft version manifests: 26.1, 26.1.1, 26.1.2; game-supplied client runtime and development classpath |

Follow-up owner: repository maintainer and security reviewer. Re-evaluate before release, on changed game libraries or advisory scope, and no later than 2027-02-02. Runtime traces/configuration for the named vulnerable feature are still needed; uncertainty is not non-applicability.

### GHSA-cmp6-m4wj-q63q

yawkat LZ4 Java has a possible information leak in Java safe decompressor

Aliases: CVE-2025-66566. Severity: **HIGH**, GitHub-reviewed OSV record; vectors: CVSS_V4 CVSS:4.0/AV:N/AC:L/AT:P/PR:N/UI:N/VC:H/VI:N/VA:N/SC:N/SI:N/SA:N.

[OSV](https://osv.dev/vulnerability/GHSA-cmp6-m4wj-q63q) · [GitHub advisory](https://github.com/advisories/GHSA-cmp6-m4wj-q63q)

Affected ranges and fixed endpoints (each release line is separate; a listed fix is not a compatibility approval):

- `at.yawk.lz4:lz4-java`: introduced 0; fixed 1.10.1.
- `org.lz4:lz4-java`: introduced 0; last_affected 1.8.1.
- `org.lz4:lz4-pure-java`: introduced 0; last_affected 1.8.1.
- `net.jpountz.lz4:lz4`: introduced 0; last_affected 1.8.1.

**Disposition: Further investigation.** Identify Java versus JNI decompressor selection and reuse/zeroing of destination buffers for untrusted input. If reachable, request a compatible upstream game fix; do not override game-managed libraries in the mod.

| Group | Package/version | Inventory scopes | Origin / relevance |
| --- | --- | --- | --- |
| 1.21.11 | `at.yawk.lz4/lz4-java@1.8.1` | gradle, runtime/1.21.11 | Minecraft version manifests: 1.21.11; game-supplied client runtime and development classpath |

Follow-up owner: repository maintainer and security reviewer. Re-evaluate before release, on changed game libraries or advisory scope, and no later than 2027-02-02. Runtime traces/configuration for the named vulnerable feature are still needed; uncertainty is not non-applicability.

### GHSA-f6hv-jmp6-3vwv

Netty: HttpContentDecompressor maxAllocation bypass when Content-Encoding set to br/zstd/snappy leads to decompression bomb DoS

Aliases: CVE-2026-42587. Severity: **HIGH**, GitHub-reviewed OSV record; vectors: CVSS_V3 CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:N/I:N/A:H.

[OSV](https://osv.dev/vulnerability/GHSA-f6hv-jmp6-3vwv) · [GitHub advisory](https://github.com/advisories/GHSA-f6hv-jmp6-3vwv)

Affected ranges and fixed endpoints (each release line is separate; a listed fix is not a compatibility approval):

- `io.netty:netty-codec-http`: introduced 4.2.0.Alpha1; fixed 4.2.13.Final.
- `io.netty:netty-codec-http2`: introduced 4.2.0.Alpha1; fixed 4.2.13.Final.
- `io.netty:netty-codec-http`: introduced 0; fixed 4.1.133.Final.
- `io.netty:netty-codec-http2`: introduced 0; fixed 4.1.133.Final.

**Disposition: Further investigation.** Identify HttpContentDecompressor with br/zstd/snappy and effective expansion limits on untrusted content. If reachable, request a compatible upstream game fix; do not override game-managed libraries in the mod.

| Group | Package/version | Inventory scopes | Origin / relevance |
| --- | --- | --- | --- |
| 1.21.11 | `io.netty/netty-codec-http@4.2.7.Final` | gradle, runtime/1.21.11 | Minecraft version manifests: 1.21.11; game-supplied client runtime and development classpath |
| 26.1-26.2 | `io.netty/netty-codec-http@4.2.7.Final` | gradle, runtime/26.1, runtime/26.1.1, runtime/26.1.2 | Minecraft version manifests: 26.1, 26.1.1, 26.1.2; game-supplied client runtime and development classpath |

Follow-up owner: repository maintainer and security reviewer. Re-evaluate before release, on changed game libraries or advisory scope, and no later than 2027-02-02. Runtime traces/configuration for the named vulnerable feature are still needed; uncertainty is not non-applicability.

### GHSA-fccg-mwvh-qqg4

Netty: Fragmented ClientHello records trigger quadratic pre-handshake reassembly in default SNI parsing

Aliases: CVE-2026-75596. Severity: **MODERATE**, GitHub-reviewed OSV record; vectors: CVSS_V4 CVSS:4.0/AV:N/AC:L/AT:N/PR:N/UI:N/VC:N/VI:N/VA:L/SC:N/SI:N/SA:N.

[OSV](https://osv.dev/vulnerability/GHSA-fccg-mwvh-qqg4) · [GitHub advisory](https://github.com/advisories/GHSA-fccg-mwvh-qqg4)

Affected ranges and fixed endpoints (each release line is separate; a listed fix is not a compatibility approval):

- `io.netty:netty-handler`: introduced 4.2.0.Final; fixed 4.2.17.Final.
- `io.netty:netty-handler`: introduced 0; fixed 4.1.137.Final.

**Disposition: Further investigation.** Determine server-side SNI parsing reachability and pre-handshake fragmentation/reassembly limits. If reachable, request a compatible upstream game fix; do not override game-managed libraries in the mod.

| Group | Package/version | Inventory scopes | Origin / relevance |
| --- | --- | --- | --- |
| 1.21.11 | `io.netty/netty-handler@4.2.7.Final` | gradle, runtime/1.21.11 | Minecraft version manifests: 1.21.11; game-supplied client runtime and development classpath |
| 26.1-26.2 | `io.netty/netty-handler@4.2.15.Final` | runtime/26.2 | Minecraft 26.2 runtime manifest; the recorded Gradle inventory does not contain this version |
| 26.1-26.2 | `io.netty/netty-handler@4.2.7.Final` | gradle, runtime/26.1, runtime/26.1.1, runtime/26.1.2 | Minecraft version manifests: 26.1, 26.1.1, 26.1.2; game-supplied client runtime and development classpath |
| 26.3 | `io.netty/netty-handler@4.2.16.Final` | gradle, runtime/26.3 | Minecraft version manifests: 26.3; game-supplied client runtime and development classpath |

Follow-up owner: repository maintainer and security reviewer. Re-evaluate before release, on changed game libraries or advisory scope, and no later than 2027-02-02. Runtime traces/configuration for the named vulnerable feature are still needed; uncertainty is not non-applicability.

### GHSA-gcjf-9mgh-3p7g

Netty: CRLF Injection via Multipart Filename in Netty HttpPostRequestEncoder

Aliases: CVE-2026-59921. Severity: **MODERATE**, GitHub-reviewed OSV record; vectors: CVSS_V3 CVSS:3.1/AV:A/AC:L/PR:L/UI:N/S:U/C:N/I:H/A:N.

[OSV](https://osv.dev/vulnerability/GHSA-gcjf-9mgh-3p7g) · [GitHub advisory](https://github.com/advisories/GHSA-gcjf-9mgh-3p7g)

Affected ranges and fixed endpoints (each release line is separate; a listed fix is not a compatibility approval):

- `io.netty:netty-codec-http`: introduced 4.2.0.Final; fixed 4.2.16.Final.
- `io.netty:netty-codec-http`: introduced 0; fixed 4.1.136.Final.

**Disposition: Further investigation.** Trace untrusted multipart filenames into HttpPostRequestEncoder. If reachable, request a compatible upstream game fix; do not override game-managed libraries in the mod.

| Group | Package/version | Inventory scopes | Origin / relevance |
| --- | --- | --- | --- |
| 1.21.11 | `io.netty/netty-codec-http@4.2.7.Final` | gradle, runtime/1.21.11 | Minecraft version manifests: 1.21.11; game-supplied client runtime and development classpath |
| 26.1-26.2 | `io.netty/netty-codec-http@4.2.15.Final` | runtime/26.2 | Minecraft version manifests: 26.2; game-supplied client runtime and development classpath |
| 26.1-26.2 | `io.netty/netty-codec-http@4.2.7.Final` | gradle, runtime/26.1, runtime/26.1.1, runtime/26.1.2 | Minecraft version manifests: 26.1, 26.1.1, 26.1.2; game-supplied client runtime and development classpath |

Follow-up owner: repository maintainer and security reviewer. Re-evaluate before release, on changed game libraries or advisory scope, and no later than 2027-02-02. Runtime traces/configuration for the named vulnerable feature are still needed; uncertainty is not non-applicability.

### GHSA-gm45-99xc-r7wv

yawkat LZ4 Java: LZ4FrameInputStream reallocates block buffers for every frame, allowing CPU and GC amplification from small inputs

Aliases: CVE-2026-106450. Severity: **MODERATE**, GitHub-reviewed OSV record; vectors: CVSS_V3 CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:N/I:N/A:L.

[OSV](https://osv.dev/vulnerability/GHSA-gm45-99xc-r7wv) · [GitHub advisory](https://github.com/advisories/GHSA-gm45-99xc-r7wv)

Affected ranges and fixed endpoints (each release line is separate; a listed fix is not a compatibility approval):

- `at.yawk.lz4:lz4-java`: introduced 0; fixed 1.11.4.
- `org.lz4:lz4-java`: introduced 0; last_affected 1.8.1.

**Disposition: Further investigation.** Trace repeated LZ4FrameInputStream frames from untrusted input and aggregate CPU/allocation limits. If reachable, request a compatible upstream game fix; do not override game-managed libraries in the mod.

| Group | Package/version | Inventory scopes | Origin / relevance |
| --- | --- | --- | --- |
| 1.21.11 | `at.yawk.lz4/lz4-java@1.8.1` | gradle, runtime/1.21.11 | Minecraft version manifests: 1.21.11; game-supplied client runtime and development classpath |
| 26.1-26.2 | `at.yawk.lz4/lz4-java@1.10.1` | gradle, runtime/26.1, runtime/26.1.1, runtime/26.1.2, runtime/26.2 | Minecraft version manifests: 26.1, 26.1.1, 26.1.2, 26.2; game-supplied client runtime and development classpath |
| 26.3 | `at.yawk.lz4/lz4-java@1.10.1` | gradle, runtime/26.3 | Minecraft version manifests: 26.3; game-supplied client runtime and development classpath |

Follow-up owner: repository maintainer and security reviewer. Re-evaluate before release, on changed game libraries or advisory scope, and no later than 2027-02-02. Runtime traces/configuration for the named vulnerable feature are still needed; uncertainty is not non-applicability.

### GHSA-h383-gmxw-35v2

Apache Log4j 1 to Log4j 2 bridge: silent log event loss in Log4j1XmlLayout due to unescaped XML 1.0 forbidden characters

Aliases: CVE-2026-34479. Severity: **MODERATE**, GitHub-reviewed OSV record; vectors: CVSS_V4 CVSS:4.0/AV:N/AC:L/AT:N/PR:N/UI:N/VC:N/VI:N/VA:N/SC:N/SI:L/SA:N.

[OSV](https://osv.dev/vulnerability/GHSA-h383-gmxw-35v2) · [GitHub advisory](https://github.com/advisories/GHSA-h383-gmxw-35v2)

Affected ranges and fixed endpoints (each release line is separate; a listed fix is not a compatibility approval):

- `org.apache.logging.log4j:log4j-core`: introduced 2.7; fixed 2.25.4.
- `org.apache.logging.log4j:log4j-core`: introduced 3.0.0-beta1; last_affected 3.0.0-beta2.

**Disposition: Further investigation.** Determine use of Log4j1XmlLayout bridge and attacker-controlled forbidden XML characters. If reachable, request a compatible upstream game fix; do not override game-managed libraries in the mod.

| Group | Package/version | Inventory scopes | Origin / relevance |
| --- | --- | --- | --- |
| 1.21.11 | `org.apache.logging.log4j/log4j-core@2.25.2` | gradle, runtime/1.21.11 | Minecraft version manifests: 1.21.11; game-supplied client runtime and development classpath |
| 26.1-26.2 | `org.apache.logging.log4j/log4j-core@2.25.2` | gradle, runtime/26.1, runtime/26.1.1, runtime/26.1.2 | Minecraft version manifests: 26.1, 26.1.1, 26.1.2; game-supplied client runtime and development classpath |

Follow-up owner: repository maintainer and security reviewer. Re-evaluate before release, on changed game libraries or advisory scope, and no later than 2027-02-02. Runtime traces/configuration for the named vulnerable feature are still needed; uncertainty is not non-applicability.

### GHSA-hvcg-qmg6-jm4c

Netty: HttpObjectDecoder skips arbitrary initial control characters when only initial CRLF characters are permitted

Aliases: CVE-2026-50020. Severity: **MODERATE**, GitHub-reviewed OSV record; vectors: CVSS_V3 CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:N/I:L/A:N.

[OSV](https://osv.dev/vulnerability/GHSA-hvcg-qmg6-jm4c) · [GitHub advisory](https://github.com/advisories/GHSA-hvcg-qmg6-jm4c)

Affected ranges and fixed endpoints (each release line is separate; a listed fix is not a compatibility approval):

- `io.netty:netty-codec-http`: introduced 4.2.0.Final; fixed 4.2.15.Final.
- `io.netty:netty-codec-http`: introduced 0; fixed 4.1.135.Final.

**Disposition: Further investigation.** Trace HTTP start-line control-character handling and intermediaries with different parsing. If reachable, request a compatible upstream game fix; do not override game-managed libraries in the mod.

| Group | Package/version | Inventory scopes | Origin / relevance |
| --- | --- | --- | --- |
| 1.21.11 | `io.netty/netty-codec-http@4.2.7.Final` | gradle, runtime/1.21.11 | Minecraft version manifests: 1.21.11; game-supplied client runtime and development classpath |
| 26.1-26.2 | `io.netty/netty-codec-http@4.2.7.Final` | gradle, runtime/26.1, runtime/26.1.1, runtime/26.1.2 | Minecraft version manifests: 26.1, 26.1.1, 26.1.2; game-supplied client runtime and development classpath |

Follow-up owner: repository maintainer and security reviewer. Re-evaluate before release, on changed game libraries or advisory scope, and no later than 2027-02-02. Runtime traces/configuration for the named vulnerable feature are still needed; uncertainty is not non-applicability.

### GHSA-jppx-w49h-x2qq

Netty: [SpdyHttpDecoder] ByteBuf Reference Leak on RST_STREAM Leads to Native Memory Exhaustion

Aliases: CVE-2026-56745. Severity: **HIGH**, GitHub-reviewed OSV record; vectors: CVSS_V4 CVSS:4.0/AV:N/AC:L/AT:N/PR:N/UI:N/VC:N/VI:N/VA:H/SC:N/SI:N/SA:N.

[OSV](https://osv.dev/vulnerability/GHSA-jppx-w49h-x2qq) · [GitHub advisory](https://github.com/advisories/GHSA-jppx-w49h-x2qq)

Affected ranges and fixed endpoints (each release line is separate; a listed fix is not a compatibility approval):

- `io.netty:netty-codec-http`: introduced 4.2.0.Final; fixed 4.2.16.Final.
- `io.netty:netty-codec-http`: introduced 4.1.0.Final; fixed 4.1.136.Final.

**Disposition: Further investigation.** Identify SpdyHttpDecoder RST_STREAM handling and buffer lifetime for untrusted streams. If reachable, request a compatible upstream game fix; do not override game-managed libraries in the mod.

| Group | Package/version | Inventory scopes | Origin / relevance |
| --- | --- | --- | --- |
| 1.21.11 | `io.netty/netty-codec-http@4.2.7.Final` | gradle, runtime/1.21.11 | Minecraft version manifests: 1.21.11; game-supplied client runtime and development classpath |
| 26.1-26.2 | `io.netty/netty-codec-http@4.2.15.Final` | runtime/26.2 | Minecraft version manifests: 26.2; game-supplied client runtime and development classpath |
| 26.1-26.2 | `io.netty/netty-codec-http@4.2.7.Final` | gradle, runtime/26.1, runtime/26.1.1, runtime/26.1.2 | Minecraft version manifests: 26.1, 26.1.1, 26.1.2; game-supplied client runtime and development classpath |

Follow-up owner: repository maintainer and security reviewer. Re-evaluate before release, on changed game libraries or advisory scope, and no later than 2027-02-02. Runtime traces/configuration for the named vulnerable feature are still needed; uncertainty is not non-applicability.

### GHSA-m4cv-j2px-7723

Netty vulnerable to HTTP Request Smuggling due to incorrect chunk size parsing

Aliases: CVE-2026-42580. Severity: **MODERATE**, GitHub-reviewed OSV record; vectors: CVSS_V3 CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:N/I:L/A:L.

[OSV](https://osv.dev/vulnerability/GHSA-m4cv-j2px-7723) · [GitHub advisory](https://github.com/advisories/GHSA-m4cv-j2px-7723)

Affected ranges and fixed endpoints (each release line is separate; a listed fix is not a compatibility approval):

- `io.netty:netty-codec-http`: introduced 4.2.0.Alpha1; fixed 4.2.13.Final.
- `io.netty:netty-codec-http`: introduced 0; fixed 4.1.133.Final.

**Disposition: Further investigation.** Trace HTTP chunk-size parsing and intermediary disagreement for request smuggling. If reachable, request a compatible upstream game fix; do not override game-managed libraries in the mod.

| Group | Package/version | Inventory scopes | Origin / relevance |
| --- | --- | --- | --- |
| 1.21.11 | `io.netty/netty-codec-http@4.2.7.Final` | gradle, runtime/1.21.11 | Minecraft version manifests: 1.21.11; game-supplied client runtime and development classpath |
| 26.1-26.2 | `io.netty/netty-codec-http@4.2.7.Final` | gradle, runtime/26.1, runtime/26.1.1, runtime/26.1.2 | Minecraft version manifests: 26.1, 26.1.1, 26.1.2; game-supplied client runtime and development classpath |

Follow-up owner: repository maintainer and security reviewer. Re-evaluate before release, on changed game libraries or advisory scope, and no later than 2027-02-02. Runtime traces/configuration for the named vulnerable feature are still needed; uncertainty is not non-applicability.

### GHSA-mcr4-qmvw-px4g

yawkat LZ4 Java: Native library extraction to a shared temporary directory is vulnerable to file replacement by another local user

Aliases: CVE-2026-106451. Severity: **HIGH**, GitHub-reviewed OSV record; vectors: CVSS_V4 CVSS:4.0/AV:L/AC:H/AT:P/PR:L/UI:N/VC:H/VI:H/VA:H/SC:N/SI:N/SA:N.

[OSV](https://osv.dev/vulnerability/GHSA-mcr4-qmvw-px4g) · [GitHub advisory](https://github.com/advisories/GHSA-mcr4-qmvw-px4g)

Affected ranges and fixed endpoints (each release line is separate; a listed fix is not a compatibility approval):

- `at.yawk.lz4:lz4-java`: introduced 0; fixed 1.11.4.
- `org.lz4:lz4-java`: introduced 1.7.0; last_affected 1.8.1.

**Disposition: Further investigation.** Verify JNI extraction use, shared temporary directory permissions and host hardening; private java.io.tmpdir is a possible operator mitigation, not verified here. If reachable, request a compatible upstream game fix; do not override game-managed libraries in the mod.

| Group | Package/version | Inventory scopes | Origin / relevance |
| --- | --- | --- | --- |
| 1.21.11 | `at.yawk.lz4/lz4-java@1.8.1` | gradle, runtime/1.21.11 | Minecraft version manifests: 1.21.11; game-supplied client runtime and development classpath |
| 26.1-26.2 | `at.yawk.lz4/lz4-java@1.10.1` | gradle, runtime/26.1, runtime/26.1.1, runtime/26.1.2, runtime/26.2 | Minecraft version manifests: 26.1, 26.1.1, 26.1.2, 26.2; game-supplied client runtime and development classpath |
| 26.3 | `at.yawk.lz4/lz4-java@1.10.1` | gradle, runtime/26.3 | Minecraft version manifests: 26.3; game-supplied client runtime and development classpath |

Follow-up owner: repository maintainer and security reviewer. Re-evaluate before release, on changed game libraries or advisory scope, and no later than 2027-02-02. Runtime traces/configuration for the named vulnerable feature are still needed; uncertainty is not non-applicability.

### GHSA-mj4r-2hfc-f8p6

Netty Lz4FrameDecoder is vulnerable to resource exhaustion 

Aliases: CVE-2026-42583. Severity: **HIGH**, GitHub-reviewed OSV record; vectors: CVSS_V3 CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:N/I:N/A:H.

[OSV](https://osv.dev/vulnerability/GHSA-mj4r-2hfc-f8p6) · [GitHub advisory](https://github.com/advisories/GHSA-mj4r-2hfc-f8p6)

Affected ranges and fixed endpoints (each release line is separate; a listed fix is not a compatibility approval):

- `io.netty:netty-codec-compression`: introduced 0; fixed 4.2.13.Final.
- `io.netty:netty-codec`: introduced 0; fixed 4.1.133.Final.

**Disposition: Further investigation.** Identify Lz4FrameDecoder use, attacker-controlled decompressedLength and aggregate/per-channel memory limits. If reachable, request a compatible upstream game fix; do not override game-managed libraries in the mod.

| Group | Package/version | Inventory scopes | Origin / relevance |
| --- | --- | --- | --- |
| 1.21.11 | `io.netty/netty-codec-compression@4.2.7.Final` | gradle, runtime/1.21.11 | Minecraft version manifests: 1.21.11; game-supplied client runtime and development classpath |
| 26.1-26.2 | `io.netty/netty-codec-compression@4.2.7.Final` | gradle, runtime/26.1, runtime/26.1.1, runtime/26.1.2 | Minecraft version manifests: 26.1, 26.1.1, 26.1.2; game-supplied client runtime and development classpath |

Follow-up owner: repository maintainer and security reviewer. Re-evaluate before release, on changed game libraries or advisory scope, and no later than 2027-02-02. Runtime traces/configuration for the named vulnerable feature are still needed; uncertainty is not non-applicability.

### GHSA-mvh2-crg5-v77c

Netty SPDY zlib header block continues decoded expansion after maxHeaderSize truncation

Aliases: CVE-2026-55833. Severity: **HIGH**, GitHub-reviewed OSV record; vectors: CVSS_V3 CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:N/I:N/A:H.

[OSV](https://osv.dev/vulnerability/GHSA-mvh2-crg5-v77c) · [GitHub advisory](https://github.com/advisories/GHSA-mvh2-crg5-v77c)

Affected ranges and fixed endpoints (each release line is separate; a listed fix is not a compatibility approval):

- `io.netty:netty-codec-http`: introduced 4.2.0.Final; fixed 4.2.16.Final.
- `io.netty:netty-codec-http`: introduced 4.1.0.Final; fixed 4.1.136.Final.

**Disposition: Further investigation.** Identify SPDY zlib header decoding and expansion after maxHeaderSize truncation. If reachable, request a compatible upstream game fix; do not override game-managed libraries in the mod.

| Group | Package/version | Inventory scopes | Origin / relevance |
| --- | --- | --- | --- |
| 1.21.11 | `io.netty/netty-codec-http@4.2.7.Final` | gradle, runtime/1.21.11 | Minecraft version manifests: 1.21.11; game-supplied client runtime and development classpath |
| 26.1-26.2 | `io.netty/netty-codec-http@4.2.15.Final` | runtime/26.2 | Minecraft version manifests: 26.2; game-supplied client runtime and development classpath |
| 26.1-26.2 | `io.netty/netty-codec-http@4.2.7.Final` | gradle, runtime/26.1, runtime/26.1.1, runtime/26.1.2 | Minecraft version manifests: 26.1, 26.1.1, 26.1.2; game-supplied client runtime and development classpath |

Follow-up owner: repository maintainer and security reviewer. Re-evaluate before release, on changed game libraries or advisory scope, and no later than 2027-02-02. Runtime traces/configuration for the named vulnerable feature are still needed; uncertainty is not non-applicability.

### GHSA-pwqr-wmgm-9rr8

Netty: HTTP Request Smuggling via Chunked Extension Quoted-String Parsing

Aliases: CVE-2026-33870. Severity: **HIGH**, GitHub-reviewed OSV record; vectors: CVSS_V3 CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:N/I:H/A:N.

[OSV](https://osv.dev/vulnerability/GHSA-pwqr-wmgm-9rr8) · [GitHub advisory](https://github.com/advisories/GHSA-pwqr-wmgm-9rr8)

Affected ranges and fixed endpoints (each release line is separate; a listed fix is not a compatibility approval):

- `io.netty:netty-codec-http`: introduced 0; fixed 4.1.132.Final.
- `io.netty:netty-codec-http`: introduced 4.2.0.Alpha1; fixed 4.2.10.Final.

**Disposition: Further investigation.** Trace quoted-string chunk extension parsing through intermediaries. If reachable, request a compatible upstream game fix; do not override game-managed libraries in the mod.

| Group | Package/version | Inventory scopes | Origin / relevance |
| --- | --- | --- | --- |
| 1.21.11 | `io.netty/netty-codec-http@4.2.7.Final` | gradle, runtime/1.21.11 | Minecraft version manifests: 1.21.11; game-supplied client runtime and development classpath |
| 26.1-26.2 | `io.netty/netty-codec-http@4.2.7.Final` | gradle, runtime/26.1, runtime/26.1.1, runtime/26.1.2 | Minecraft version manifests: 26.1, 26.1.1, 26.1.2; game-supplied client runtime and development classpath |

Follow-up owner: repository maintainer and security reviewer. Re-evaluate before release, on changed game libraries or advisory scope, and no later than 2027-02-02. Runtime traces/configuration for the named vulnerable feature are still needed; uncertainty is not non-applicability.

### GHSA-q4f6-jm68-57ww

Netty: [HttpContentEncoder] Unbounded Per-Connection Queue Growth via HTTP/1.1 Pipelining Leads to Denial of Service

Aliases: CVE-2026-59899. Severity: **MODERATE**, GitHub-reviewed OSV record; vectors: CVSS_V4 CVSS:4.0/AV:N/AC:L/AT:N/PR:N/UI:N/VC:N/VI:N/VA:L/SC:N/SI:N/SA:N.

[OSV](https://osv.dev/vulnerability/GHSA-q4f6-jm68-57ww) · [GitHub advisory](https://github.com/advisories/GHSA-q4f6-jm68-57ww)

Affected ranges and fixed endpoints (each release line is separate; a listed fix is not a compatibility approval):

- `io.netty:netty-codec-http`: introduced 4.2.0.Final; fixed 4.2.16.Final.
- `io.netty:netty-codec-http`: introduced 0; fixed 4.1.136.Final.

**Disposition: Further investigation.** Determine HttpContentEncoder use with HTTP/1.1 pipelining and per-connection queue limits. If reachable, request a compatible upstream game fix; do not override game-managed libraries in the mod.

| Group | Package/version | Inventory scopes | Origin / relevance |
| --- | --- | --- | --- |
| 1.21.11 | `io.netty/netty-codec-http@4.2.7.Final` | gradle, runtime/1.21.11 | Minecraft version manifests: 1.21.11; game-supplied client runtime and development classpath |
| 26.1-26.2 | `io.netty/netty-codec-http@4.2.15.Final` | runtime/26.2 | Minecraft version manifests: 26.2; game-supplied client runtime and development classpath |
| 26.1-26.2 | `io.netty/netty-codec-http@4.2.7.Final` | gradle, runtime/26.1, runtime/26.1.1, runtime/26.1.2 | Minecraft version manifests: 26.1, 26.1.1, 26.1.2; game-supplied client runtime and development classpath |

Follow-up owner: repository maintainer and security reviewer. Re-evaluate before release, on changed game libraries or advisory scope, and no later than 2027-02-02. Runtime traces/configuration for the named vulnerable feature are still needed; uncertainty is not non-applicability.

### GHSA-qv9r-c865-cp47

Apache Log4j API: Improper encoding of non-finite floating-point values during MapMessage JSON serialization

Aliases: CVE-2026-49844. Severity: **MODERATE**, GitHub-reviewed OSV record; vectors: CVSS_V4 CVSS:4.0/AV:N/AC:L/AT:P/PR:N/UI:N/VC:N/VI:N/VA:N/SC:N/SI:L/SA:N.

[OSV](https://osv.dev/vulnerability/GHSA-qv9r-c865-cp47) · [GitHub advisory](https://github.com/advisories/GHSA-qv9r-c865-cp47)

Affected ranges and fixed endpoints (each release line is separate; a listed fix is not a compatibility approval):

- `org.apache.logging.log4j:log4j-api`: introduced 2.13.1; fixed 2.25.5.
- `org.apache.logging.log4j:log4j-api`: introduced 2.26.0; fixed 2.26.1.

**Disposition: Further investigation.** Determine JsonTemplateLayout/MapMessage JSON formatting of attacker-controlled NaN/Infinity values. If reachable, request a compatible upstream game fix; do not override game-managed libraries in the mod.

| Group | Package/version | Inventory scopes | Origin / relevance |
| --- | --- | --- | --- |
| 1.21.11 | `org.apache.logging.log4j/log4j-api@2.25.2` | gradle, runtime/1.21.11 | Minecraft version manifests: 1.21.11; game-supplied client runtime and development classpath |
| 26.1-26.2 | `org.apache.logging.log4j/log4j-api@2.25.2` | gradle, runtime/26.1, runtime/26.1.1, runtime/26.1.2 | Minecraft version manifests: 26.1, 26.1.1, 26.1.2; game-supplied client runtime and development classpath |
| 26.1-26.2 | `org.apache.logging.log4j/log4j-api@2.26.0` | runtime/26.2 | Minecraft version manifests: 26.2; game-supplied client runtime and development classpath |
| 26.3 | `org.apache.logging.log4j/log4j-api@2.26.0` | gradle, runtime/26.3 | Minecraft version manifests: 26.3; game-supplied client runtime and development classpath |

Follow-up owner: repository maintainer and security reviewer. Re-evaluate before release, on changed game libraries or advisory scope, and no later than 2027-02-02. Runtime traces/configuration for the named vulnerable feature are still needed; uncertainty is not non-applicability.

### GHSA-rwm7-x88c-3g2p

Netty epoll transport denial of service via RST on half-closed TCP connection

Aliases: CVE-2026-42577. Severity: **HIGH**, GitHub-reviewed OSV record; vectors: CVSS_V3 CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:N/I:N/A:H.

[OSV](https://osv.dev/vulnerability/GHSA-rwm7-x88c-3g2p) · [GitHub advisory](https://github.com/advisories/GHSA-rwm7-x88c-3g2p)

Affected ranges and fixed endpoints (each release line is separate; a listed fix is not a compatibility approval):

- `io.netty:netty-transport-classes-epoll`: introduced 4.2.0.Final; fixed 4.2.13.Final.

**Disposition: Further investigation.** Verify epoll half-closure configuration and reachability of peer RST on half-closed TCP connections. If reachable, request a compatible upstream game fix; do not override game-managed libraries in the mod.

| Group | Package/version | Inventory scopes | Origin / relevance |
| --- | --- | --- | --- |
| 1.21.11 | `io.netty/netty-transport-classes-epoll@4.2.7.Final` | gradle, runtime/1.21.11 | Minecraft version manifests: 1.21.11; game-supplied client runtime and development classpath |
| 26.1-26.2 | `io.netty/netty-transport-classes-epoll@4.2.7.Final` | gradle, runtime/26.1, runtime/26.1.1, runtime/26.1.2 | Minecraft version manifests: 26.1, 26.1.1, 26.1.2; game-supplied client runtime and development classpath |

Follow-up owner: repository maintainer and security reviewer. Re-evaluate before release, on changed game libraries or advisory scope, and no later than 2027-02-02. Runtime traces/configuration for the named vulnerable feature are still needed; uncertainty is not non-applicability.

### GHSA-v8h7-rr48-vmmv

Netty: Start-Line Injection in DefaultHttpRequest.setUri() Allows HTTP Request Smuggling and RTSP Request Injection

Aliases: CVE-2026-41417. Severity: **MODERATE**, GitHub-reviewed OSV record; vectors: CVSS_V3 CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:N/I:L/A:N.

[OSV](https://osv.dev/vulnerability/GHSA-v8h7-rr48-vmmv) · [GitHub advisory](https://github.com/advisories/GHSA-v8h7-rr48-vmmv)

Affected ranges and fixed endpoints (each release line is separate; a listed fix is not a compatibility approval):

- `io.netty:netty-codec-http`: introduced 0; fixed 4.1.133.Final.
- `io.netty:netty-codec-http`: introduced 4.2.0.Alpha1; fixed 4.2.13.Final.

**Disposition: Further investigation.** Trace untrusted URI input into DefaultHttpRequest.setUri and HTTP/RTSP encoding. If reachable, request a compatible upstream game fix; do not override game-managed libraries in the mod.

| Group | Package/version | Inventory scopes | Origin / relevance |
| --- | --- | --- | --- |
| 1.21.11 | `io.netty/netty-codec-http@4.2.7.Final` | gradle, runtime/1.21.11 | Minecraft version manifests: 1.21.11; game-supplied client runtime and development classpath |
| 26.1-26.2 | `io.netty/netty-codec-http@4.2.7.Final` | gradle, runtime/26.1, runtime/26.1.1, runtime/26.1.2 | Minecraft version manifests: 26.1, 26.1.1, 26.1.2; game-supplied client runtime and development classpath |

Follow-up owner: repository maintainer and security reviewer. Re-evaluate before release, on changed game libraries or advisory scope, and no later than 2027-02-02. Runtime traces/configuration for the named vulnerable feature are still needed; uncertainty is not non-applicability.

### GHSA-vc5p-v9hr-52mj

Apache Log4j does not verify the TLS hostname in its Socket Appender

Aliases: CVE-2025-68161. Severity: **MODERATE**, GitHub-reviewed OSV record; vectors: CVSS_V4 CVSS:4.0/AV:N/AC:H/AT:N/PR:N/UI:N/VC:L/VI:N/VA:N/SC:N/SI:L/SA:N.

[OSV](https://osv.dev/vulnerability/GHSA-vc5p-v9hr-52mj) · [GitHub advisory](https://github.com/advisories/GHSA-vc5p-v9hr-52mj)

Affected ranges and fixed endpoints (each release line is separate; a listed fix is not a compatibility approval):

- `org.apache.logging.log4j:log4j-core`: introduced 2.0-beta9; fixed 2.25.3.

**Disposition: Further investigation.** Determine TLS SocketAppender use and required endpoint hostname authentication. If reachable, request a compatible upstream game fix; do not override game-managed libraries in the mod.

| Group | Package/version | Inventory scopes | Origin / relevance |
| --- | --- | --- | --- |
| 1.21.11 | `org.apache.logging.log4j/log4j-core@2.25.2` | gradle, runtime/1.21.11 | Minecraft version manifests: 1.21.11; game-supplied client runtime and development classpath |
| 26.1-26.2 | `org.apache.logging.log4j/log4j-core@2.25.2` | gradle, runtime/26.1, runtime/26.1.1, runtime/26.1.2 | Minecraft version manifests: 26.1, 26.1.1, 26.1.2; game-supplied client runtime and development classpath |

Follow-up owner: repository maintainer and security reviewer. Re-evaluate before release, on changed game libraries or advisory scope, and no later than 2027-02-02. Runtime traces/configuration for the named vulnerable feature are still needed; uncertainty is not non-applicability.

### GHSA-w573-9ffj-6ff9

Netty: Unix-socket fd receive leaks descriptors when peer sends two at once

Aliases: CVE-2026-45536. Severity: **MODERATE**, GitHub-reviewed OSV record; vectors: CVSS_V3 CVSS:3.1/AV:L/AC:L/PR:N/UI:N/S:U/C:N/I:N/A:L.

[OSV](https://osv.dev/vulnerability/GHSA-w573-9ffj-6ff9) · [GitHub advisory](https://github.com/advisories/GHSA-w573-9ffj-6ff9)

Affected ranges and fixed endpoints (each release line is separate; a listed fix is not a compatibility approval):

- `io.netty:netty-transport-native-epoll`: introduced 4.2.0.Final; fixed 4.2.15.Final.
- `io.netty:netty-transport-native-kqueue`: introduced 4.2.0.Final; fixed 4.2.15.Final.
- `io.netty:netty-transport-native-kqueue`: introduced 0; fixed 4.1.135.Final.
- `io.netty:netty-transport-native-epoll`: introduced 0; fixed 4.1.135.Final.

**Disposition: Further investigation.** Determine use of Epoll/KQueue DomainSocketChannel with non-default FILE_DESCRIPTORS mode and a less-trusted local peer. If reachable, request a compatible upstream game fix; do not override game-managed libraries in the mod.

| Group | Package/version | Inventory scopes | Origin / relevance |
| --- | --- | --- | --- |
| 1.21.11 | `io.netty/netty-transport-native-epoll@4.2.7.Final` | gradle, runtime/1.21.11 | Minecraft version manifests: 1.21.11; game-supplied client runtime and development classpath |
| 1.21.11 | `io.netty/netty-transport-native-kqueue@4.2.7.Final` | gradle, runtime/1.21.11 | Minecraft version manifests: 1.21.11; game-supplied client runtime and development classpath |
| 26.1-26.2 | `io.netty/netty-transport-native-epoll@4.2.7.Final` | gradle, runtime/26.1, runtime/26.1.1, runtime/26.1.2 | Minecraft version manifests: 26.1, 26.1.1, 26.1.2; game-supplied client runtime and development classpath |
| 26.1-26.2 | `io.netty/netty-transport-native-kqueue@4.2.7.Final` | gradle, runtime/26.1, runtime/26.1.1, runtime/26.1.2 | Minecraft version manifests: 26.1, 26.1.1, 26.1.2; game-supplied client runtime and development classpath |

Follow-up owner: repository maintainer and security reviewer. Re-evaluate before release, on changed game libraries or advisory scope, and no later than 2027-02-02. Runtime traces/configuration for the named vulnerable feature are still needed; uncertainty is not non-applicability.

### GHSA-x4gw-5cx5-pgmh

Netty: SNI handler pre-allocates up to 16 MiB from nine attacker bytes

Aliases: CVE-2026-45416. Severity: **HIGH**, GitHub-reviewed OSV record; vectors: CVSS_V3 CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:N/I:N/A:H.

[OSV](https://osv.dev/vulnerability/GHSA-x4gw-5cx5-pgmh) · [GitHub advisory](https://github.com/advisories/GHSA-x4gw-5cx5-pgmh)

Affected ranges and fixed endpoints (each release line is separate; a listed fix is not a compatibility approval):

- `io.netty:netty-handler`: introduced 4.2.0.Final; fixed 4.2.15.Final.
- `io.netty:netty-handler`: introduced 0; fixed 4.1.135.Final.

**Disposition: Further investigation.** Determine server-side SNI handler reachability and untrusted ClientHello length allocation limits. If reachable, request a compatible upstream game fix; do not override game-managed libraries in the mod.

| Group | Package/version | Inventory scopes | Origin / relevance |
| --- | --- | --- | --- |
| 1.21.11 | `io.netty/netty-handler@4.2.7.Final` | gradle, runtime/1.21.11 | Minecraft version manifests: 1.21.11; game-supplied client runtime and development classpath |
| 26.1-26.2 | `io.netty/netty-handler@4.2.7.Final` | gradle, runtime/26.1, runtime/26.1.1, runtime/26.1.2 | Minecraft version manifests: 26.1, 26.1.1, 26.1.2; game-supplied client runtime and development classpath |

Follow-up owner: repository maintainer and security reviewer. Re-evaluate before release, on changed game libraries or advisory scope, and no later than 2027-02-02. Runtime traces/configuration for the named vulnerable feature are still needed; uncertainty is not non-applicability.

### GHSA-xx22-p4ch-683r

LZ4 Java: Native XXHash implementations can crash the JVM when passed invalid byte array ranges

Aliases: CVE-2026-59949. Severity: **MODERATE**, GitHub-reviewed OSV record; vectors: CVSS_V3 CVSS:3.1/AV:N/AC:H/PR:N/UI:N/S:U/C:L/I:N/A:H.

[OSV](https://osv.dev/vulnerability/GHSA-xx22-p4ch-683r) · [GitHub advisory](https://github.com/advisories/GHSA-xx22-p4ch-683r)

Affected ranges and fixed endpoints (each release line is separate; a listed fix is not a compatibility approval):

- `at.yawk.lz4:lz4-java`: introduced 0; fixed 1.11.1.
- `org.lz4:lz4-java`: introduced 0; last_affected 1.8.1.

**Disposition: Further investigation.** Determine whether invalid byte-array ranges can reach native XXHash from less-trusted callers. If reachable, request a compatible upstream game fix; do not override game-managed libraries in the mod.

| Group | Package/version | Inventory scopes | Origin / relevance |
| --- | --- | --- | --- |
| 1.21.11 | `at.yawk.lz4/lz4-java@1.8.1` | gradle, runtime/1.21.11 | Minecraft version manifests: 1.21.11; game-supplied client runtime and development classpath |
| 26.1-26.2 | `at.yawk.lz4/lz4-java@1.10.1` | gradle, runtime/26.1, runtime/26.1.1, runtime/26.1.2, runtime/26.2 | Minecraft version manifests: 26.1, 26.1.1, 26.1.2, 26.2; game-supplied client runtime and development classpath |
| 26.3 | `at.yawk.lz4/lz4-java@1.10.1` | gradle, runtime/26.3 | Minecraft version manifests: 26.3; game-supplied client runtime and development classpath |

Follow-up owner: repository maintainer and security reviewer. Re-evaluate before release, on changed game libraries or advisory scope, and no later than 2027-02-02. Runtime traces/configuration for the named vulnerable feature are still needed; uncertainty is not non-applicability.

### GHSA-xxph-c9ww-hj94

Google Guava: CompactHashMap/CompactHashSet/MapMakerInternalMap deserialization triggers uncontrolled memory allocation

Aliases: CVE-2026-102554. Severity: **HIGH**, GitHub-reviewed OSV record; vectors: CVSS_V3 CVSS:3.1/AV:N/AC:H/PR:N/UI:N/S:U/C:N/I:N/A:H; CVSS_V4 CVSS:4.0/AV:N/AC:L/AT:P/PR:N/UI:N/VC:N/VI:N/VA:H/SC:N/SI:N/SA:N.

[OSV](https://osv.dev/vulnerability/GHSA-xxph-c9ww-hj94) · [GitHub advisory](https://github.com/advisories/GHSA-xxph-c9ww-hj94)

Affected ranges and fixed endpoints (each release line is separate; a listed fix is not a compatibility approval):

- `com.google.guava:guava`: introduced 4.0; fixed 33.7.2.

**Disposition: Further investigation.** Trace native ObjectInputStream deserialization of untrusted Guava collections and serialization filters. If reachable, request a compatible upstream game fix; do not override game-managed libraries in the mod.

| Group | Package/version | Inventory scopes | Origin / relevance |
| --- | --- | --- | --- |
| 1.21.11 | `com.google.guava/guava@33.5.0-jre` | gradle, runtime/1.21.11 | Minecraft version manifests: 1.21.11; game-supplied client runtime and development classpath |
| 26.1-26.2 | `com.google.guava/guava@33.5.0-jre` | gradle, runtime/26.1, runtime/26.1.1, runtime/26.1.2 | Minecraft version manifests: 26.1, 26.1.1, 26.1.2; game-supplied client runtime and development classpath |
| 26.1-26.2 | `com.google.guava/guava@33.6.0-jre` | runtime/26.2 | Minecraft version manifests: 26.2; game-supplied client runtime and development classpath |
| 26.3 | `com.google.guava/guava@33.6.0-jre` | gradle, runtime/26.3 | Minecraft version manifests: 26.3; game-supplied client runtime and development classpath |

Follow-up owner: repository maintainer and security reviewer. Re-evaluate before release, on changed game libraries or advisory scope, and no later than 2027-02-02. Runtime traces/configuration for the named vulnerable feature are still needed; uncertainty is not non-applicability.

### GHSA-xxqh-mfjm-7mv9

Netty HTTP/1.0 TE+CL Coexistence Bypasses Smuggling Sanitization

Aliases: CVE-2026-42581. Severity: **MODERATE**, GitHub-reviewed OSV record; vectors: CVSS_V3 CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:C/C:N/I:L/A:N.

[OSV](https://osv.dev/vulnerability/GHSA-xxqh-mfjm-7mv9) · [GitHub advisory](https://github.com/advisories/GHSA-xxqh-mfjm-7mv9)

Affected ranges and fixed endpoints (each release line is separate; a listed fix is not a compatibility approval):

- `io.netty:netty-codec-http`: introduced 4.2.0.Alpha1; fixed 4.2.13.Final.
- `io.netty:netty-codec-http`: introduced 0; fixed 4.1.133.Final.

**Disposition: Further investigation.** Identify HTTP/1.0 Transfer-Encoding plus Content-Length handling across intermediaries. If reachable, request a compatible upstream game fix; do not override game-managed libraries in the mod.

| Group | Package/version | Inventory scopes | Origin / relevance |
| --- | --- | --- | --- |
| 1.21.11 | `io.netty/netty-codec-http@4.2.7.Final` | gradle, runtime/1.21.11 | Minecraft version manifests: 1.21.11; game-supplied client runtime and development classpath |
| 26.1-26.2 | `io.netty/netty-codec-http@4.2.7.Final` | gradle, runtime/26.1, runtime/26.1.1, runtime/26.1.2 | Minecraft version manifests: 26.1, 26.1.1, 26.1.2; game-supplied client runtime and development classpath |

Follow-up owner: repository maintainer and security reviewer. Re-evaluate before release, on changed game libraries or advisory scope, and no later than 2027-02-02. Runtime traces/configuration for the named vulnerable feature are still needed; uncertainty is not non-applicability.

