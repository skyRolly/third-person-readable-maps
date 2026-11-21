# Issue #45: source-bound critical reachability investigation

Observed on 2026-11-21. This is an incomplete investigation, not security
clearance, release approval, or risk acceptance. The companion
[source-bound disposition record](../dependency-evidence/critical-reachability-2026-11-21/source-bound-dispositions-2026-11-21.json)
binds every focused finding to its package version, source group and SHA,
runtime scopes, exact audit report hash, and supporting artifact hashes.

## Inventory and provenance

The archived exact-source index contains 13 groups and 490 failing
occurrences: 385 candidate and 105 integrated. The severity totals are 22
Critical, 177 High, 274 Moderate, and 17 Low. All archive report hashes and
source identities verified (39 archived report/snapshot/tool files and 490
individual finding records). Candidate and integrated counts remain separate.
No match disappeared, no fix was applied, and no risk was accepted.

The 13 source branch heads still match the index. Their exact Gradle Wrapper
files were fetched by source SHA and checked against Gradle's published Wrapper
and distribution SHA-256 values. All 13 use Gradle 9.9.2 and passed the
Wrapper verifier. Evidence is in
[wrapper-source-verification-2026-11-21.json](../dependency-evidence/critical-reachability-2026-11-21/wrapper-source-verification-2026-11-21.json).
The coordination checkout itself has no `gradle/wrapper` directory, so a
direct root-level wrapper check is not applicable; the check used each exact
Minecraft source commit instead.

The [Netty artifact inventory](../dependency-evidence/critical-reachability-2026-11-21/netty-manifest-artifacts-2026-11-21.json)
verifies Mojang metadata SHA-1 values, Netty artifact size and SHA-1, and
artifact SHA-256 for each exact affected handler and HTTP codec artifact. It
also binds `SniHandler`, `AbstractSniHandler`, `SslClientHelloHandler`, and
HTTP decoder class hashes. All 17 Netty finding occurrences across the two
focused advisories are represented.

## Critical advisories

### GHSA-c4c3-7fpv-j4q5 / CVE-2026-75595

The finding index contains 14 exact package occurrences. Affected
`netty-handler` versions are 4.1.77.Final, 4.1.82.Final, 4.1.97.Final,
4.1.115.Final, 4.1.118.Final, 4.2.7.Final, 4.2.15.Final, and 4.2.16.Final.
The upstream advisory's fixed versions are 4.1.137.Final and 4.2.17.Final.
Every package is supplied by the Minecraft runtime; the `gradle` inventory
scope represents the same game libraries in development resolution, not a
Gradle plugin.

Component tests using local TLS inputs reproduced default-context fallback on
affected 4.1.118.Final, 4.2.7.Final, and 4.2.15.Final. Fixed 4.1.137.Final and
4.2.17.Final waited for the complete fragmented ClientHello and selected the
requested host context. These tests exercise Netty's `SniHandler` component;
they did not reproduce an authentication bypass in Minecraft.

The hash-verified Minecraft client search found no direct `SniHandler`,
`AbstractSniHandler`, or `SslClientHelloHandler` reference. The inspected
optional management JSON-RPC pipeline in Minecraft 1.21.9 through 26.3 uses
`SslContext.newHandler`, `HttpServerCodec`, `HttpObjectAggregator`, and a
WebSocket handler, without SNI routing. That management service defaults to
disabled; when enabled, its server SSL context does not require client
certificates and its request handler checks an API key. The advisory's mTLS-only
gate, permissive fallback, and missing secondary certificate check were not
found on this first-party path.

This narrows the built-in path but does not establish process-wide
non-reachability. Runtime-added code, reflection, custom launcher classpaths,
and other mods remain unexamined. Every occurrence remains failing; the 26.2
occurrence retains its existing **Upstream-dependent** remediation
classification, and other source occurrences remain **Further investigation**.
No runtime override was applied.

### Log4j: GHSA-jfh8-c2jp-5v3q, GHSA-7rjr-3q55-vv33, GHSA-fxph-q3j8-mv87

The findings are Core 2.8.1 in Minecraft 1.14–1.16.5 and Core 2.14.1 in
Minecraft 1.17–1.18.1. Upstream first-patched endpoints for these advisory
records are 2.12.2 or 2.15.0 for GHSA-jfh8, 2.12.2 or 2.16.0 for GHSA-7rjr,
and 2.8.2 for GHSA-fxph. Those endpoints are not a combined compatibility
recommendation: 2.15.0 does not address GHSA-7rjr. Minecraft supplies the
affected libraries.

Mojang metadata selects the hash-verified `client-1.12.xml` through
`-Dlog4j.configurationFile=${path}`. The actual Patchy `LegacyXMLLayout`
implementation formats and escapes message text without Log4j substitution;
the rolling file pattern uses `%msg{nolookups}`. An isolated local marker probe
did not expand message lookups under that exact default layout. A synthetic
fallback `PatternLayout` with `%msg%n` did expand a harmless local property.
Synthetic MDC/context-layout tests invoked a local JNDI factory that refused
all lookups, including with `formatMsgNoLookups=true`; this confirms that the
flag alone is not sufficient. No network lookup was attempted.

The default XML does not start a TCP or UDP Log4j socket server, and the client
constant-pool survey did not find direct references to those server classes.
However, actual launcher arguments and classpaths, remote/chat input-to-log
flows, and configuration changes from other mods were not verified for every
launcher. The socket-server classes exist in Core 2.8.1, so alternate plugin or
reflective startup paths remain possible. All eight findings remain
**Further investigation** and blocking; no blanket non-applicability claim is
made.

## Focused High advisories

### GHSA-pwqr-wmgm-9rr8 / CVE-2026-33870

Three source occurrences cover Netty HTTP codec 4.1.118.Final and 4.2.7.Final.
The upstream fixed endpoints are 4.1.132.Final and 4.2.10.Final. A local
`EmbeddedChannel` test with the advisory request-smuggling payload showed
affected codecs accepting both the outer and smuggled request; tested fixed
4.1.137.Final and 4.2.15.Final rejected the malformed framing.

The source-bound first-party management server pipeline includes
`HttpServerCodec`, but defaults disabled and validates an API key when enabled.
The isolated parser test did not start Minecraft, test a proxy, or establish
the required downstream parser disagreement. All three occurrences remain
**Further investigation** and blocking. The dependency owner is Minecraft.

### GHSA-mcr4-qmvw-px4g / CVE-2026-106451

Eight source occurrences cover Minecraft-supplied LZ4 Java 1.8.0, 1.8.1, and
1.10.1. Minecraft's `RegionFileVersion` contains the path that constructs
`LZ4BlockInputStream(InputStream)` for local region data; the constructor
reaches `LZ4Factory.fastestInstance`. With native lookup isolated, local probes
observed native extraction and lock/prefix files in the affected versions.
The tested upstream-fixed 1.11.4 artifact loaded without the observed lock-file
pattern. These probes did not race a second local user or test a real game
world/launcher.

The upstream advisory identifies 1.11.4 as fixed for the `at.yawk.lz4` line;
it lists no first patched version for `org.lz4` through 1.8.1. A per-user
`java.io.tmpdir` is a possible launcher mitigation, but supported launchers and
host temporary-directory permissions were not tested. The actual triggering
conditions for imported or user-selected LZ4 region files and the local race
remain to be verified. All eight findings remain **Further investigation** and
blocking; no library override was applied.

## Credential and integration status

The historical repository-write-capable `GH_TOKEN` exposure remains unresolved.
The 25 captured logs contain no literal value, which does not rule out exposure
through build plugins or other surfaces. The token owner still needs to inspect
available account and GitHub audit activity and rotate or revoke the token if
exposure cannot be excluded. PR #47's credential isolation remains in place;
the current full unit suite passed its isolated-Gradle environment tests. The
local probe reported no named sensitive environment variables in its test
child. This does not establish the historical token's safety or sandbox builds.

All ten legacy PRs (#13, #14, #16–#23) remain open. Live GitHub heads match the
audited source SHAs. Each exact-head CI run passed Linux, Windows, Wrapper
verification, and packaged API checks. They remain blocked by the unresolved
Critical and High findings; no PR was merged. Integrated source branches were
not changed. Issue #44 therefore needs no integration-status update. Issue #46
remains a separate graphical, hardware-GPU, and multiplayer acceptance gate.

## Verification recorded

- Exact-source archive and all 490 finding report hashes/source identities: verified.
- 13 current source heads and Gradle 9.9.2 Wrapper checks: verified.
- Component reachability suite: 28/28 expected local-only results on Linux.
- `python3 scripts/validate_critical_reachability_evidence.py`: passed.
- `python3 -m unittest discover -s tests -v`: 185 passed after the evidence validator, ledger, documentation, and workflow changes.
- `python3 scripts/validate_current_evidence.py`: returned `PENDING` for runtime observations and selected current integrated security inventories. This remains a separate release/readiness blocker.
- Local workflow lint could not run because this environment's `/usr/bin/go` rejects `go run` (`Go: Unknown option: run`); the repository CI actionlint step will check the workflow on the PR.
- Initial Windows run of the new reachability workflow failed during checkout:
  Git for Windows rejected ten historical archive paths because long path
  handling was disabled. The source contents were unchanged and Linux completed
  the same evidence and component checks. The checkout step now enables
  `core.longpaths` through Git's per-process configuration environment; a fresh
  Windows PR run is required to verify checkout and the Windows probes.
- Fresh OSV scan after this documentation-only source branch: not run. No game source or dependency declarations changed; the checked-in exact-source candidate/integrated audit reports remain unchanged and failing.

Counts remain 490 failing occurrences (22 Critical, 177 High, 274 Moderate,
17 Low): 385 candidate and 105 integrated. Issue #45 remains open. No tags,
releases, risk acceptance, or security clearance were created.
