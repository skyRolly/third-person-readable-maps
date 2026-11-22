# Issue 45: Jackson runtime reachability follow-up — 2026-11-22

This update adds source-bound Jackson investigation to the existing Issue #45
record. It does not change source dependencies, rewrite historical audit reports,
clear a finding, accept risk, or authorize integration.

## Exact source and package scope

The finding index contains 21 HIGH occurrences across three candidate groups.
Each group contains all seven listed Jackson advisories, one occurrence per ID.
The source-bound disposition record now covers 22 Critical and 44 focused High
occurrences (66 total); the full candidate and integrated inventory remains 490
failing occurrences.

| Candidate group | Legacy PR | Source SHA | Minecraft versions |
| --- | ---: | --- | --- |
| 1.21.2-1.21.3 | #16 | `d823a91c96b9bc80446116b44cd7568c70048c0d` | 1.21.2, 1.21.3 |
| 1.21.4-1.21.8 | #14 | `f63e12da0ccbf70acb41393211c864b057f5cd7c` | 1.21.4–1.21.8 |
| 1.21.9-1.21.10 | #13 | `5dd5d433fd785bf51f13827babf51a76d09f7cdb` | 1.21.9, 1.21.10 |

The hash-bound Mojang manifests list `jackson-core:2.13.4` and
`jackson-databind:2.13.4.2` for all nine game versions. These are Minecraft
runtime libraries. The `gradle` audit scope is the resolved game-library
development graph; it is not a Gradle build plugin or a dependency declared by
the mod. `msal4j:1.15.0` is listed for 1.21.2–1.21.3 and `msal4j:1.17.2` for
1.21.4–1.21.10. No compatible dependency upgrade is controlled by this mod.

## Advisory ranges and trigger requirements

| Advisory | Package in these sources | Upstream affected range covering it | First fixed version | Required vulnerable operation |
| --- | --- | --- | --- | --- |
| GHSA-7hhh-6rmp-j9qf / CVE-2026-89425 | jackson-core 2.13.4 | 2.8.0–2.18.10 | 2.18.11 | `UTF8DataInputJsonParser` through `createParser(DataInput)` on a malformed token |
| GHSA-cxp5-3px4-pw24 / CVE-2026-91777 | jackson-databind 2.13.4.2 | 2.5.0–2.18.10 | 2.18.11 | Reverse resolution of attacker-influenced forward references in `@JsonIdentityInfo` collection/map models |
| GHSA-h46c-h94j-95f3 / CVE-2025-52999 | jackson-core 2.13.4 | below 2.15.0 | 2.15.0 | Deeply nested JSON reaches a parser without a nesting limit |
| GHSA-j3rv-43j4-c7qm / CVE-2026-54512 | jackson-databind 2.13.4.2 | 2.10.0–2.18.7 | 2.18.8 | Polymorphic typing with a `PolymorphicTypeValidator` generic-parameter bypass |
| GHSA-r7wm-3cxj-wff9 / CVE-2026-68494 | jackson-core 2.13.4 | below 2.18.8 | 2.18.8 | Async parser with chunked number input |
| GHSA-rmj7-2vxq-3g9f / CVE-2026-54513 | jackson-databind 2.13.4.2 | 2.10.0–below 2.18.8 | 2.18.8 | Polymorphic typing with `allowIfSubTypeIsArray()` and attacker-controlled array type data |
| GHSA-wv8q-qhhj-9h54 / CVE-2026-91776 | jackson-databind 2.13.4.2 | 2.0.0–2.18.10 | 2.18.11 | Long-lived name-based polymorphism with a fallback/default implementation and distinct unknown IDs |

The authoritative GitHub advisory records, aliases, full version ranges, fix
references, package artifact hashes, and per-occurrence fingerprints are in the
[source-bound Jackson/MSAL and Log4j report](../dependency-evidence/critical-reachability-2026-11-21/jackson-msal-runtime-reachability-2026-11-22.json).
Original finding reports and earlier evidence remain unchanged.

## Minecraft and library call paths

Official client binaries and mappings for all nine versions were hash-checked.
The game classes have no direct Jackson references. `IntegratedServer` does not
reference `ServerTextFilter` or `PlayerSafetyServiceTextFilter`; its inherited
`MinecraftServer.createTextFilterForPlayer` returns `TextFilter.DUMMY`.

The dedicated-server code contains a separate optional path. Its constructor
calls `ServerTextFilter.createFromConfig`. The properties default
`text-filtering-config` to an empty string and `text-filtering-version` to zero;
the factory returns null for the blank config. A configured version 1 creates
`PlayerSafetyServiceTextFilter`. That filter obtains credentials through MSAL
using an HTTPS `login.microsoftonline.com/{tenantId}/` authority. MSAL's exact
`JsonHelper` calls `ObjectMapper.readValue(String, Class)` and `readTree(String)`
for identity metadata/token data. The text-filter chat request and response use
Gson, not Jackson. The identity response is therefore a reachable Jackson
input on this configured server path, but control of that HTTPS response by an
attacker was not established.

The exact Log4j Core versions also contain Jackson-backed JSON configuration and
event parser classes. `JsonConfiguration` reads a chosen JSON config stream with
`ObjectMapper.readTree(InputStream)`. The public `JsonLogEventParser` methods
use `ObjectReader.readValue(String/byte[])` for `Log4jLogEvent`. Neither
`TcpSocketServer` nor the old input-stream event bridge exists in these two
Log4j Core artifacts, and no in-jar caller of `JsonLogEventParser` was found.
Mojang's hash-verified default metadata argument is
`-Dlog4j.configurationFile=${path}`; the captured config uses `LegacyXMLLayout`
and `PatternLayout`, not JSON/YAML layouts or an event socket server. Actual
launcher arguments and third-party mods are not verified. A mod or custom
launcher can invoke the public parser or select a JSON configuration, so these
observations do not support a package-wide non-applicability disposition.

The two exact MSAL artifacts were scanned at the class-file level. They contain
no references to `DataInput`, async parser creation, `JsonIdentityInfo`,
`JsonTypeInfo`, `PolymorphicTypeValidator`, `BasicPolymorphicTypeValidator`, or
default-typing activation. The Log4j Core artifacts likewise show no such
advisory-specific configuration. These are first-party-library observations,
not a scan of arbitrary mods, custom class loaders, agents, or the entire running
process.

## Bounded parser experiment

The preserved local probes used Temurin OpenJDK 21.0.13 with a 96 MiB heap and
256 KiB stack, with no network access. `jackson-core:2.13.4` and
`jackson-databind:2.13.4.2` parsed generated nested arrays through depth 32,768
and nested objects through depth 16,384 without `StackOverflowError`. This did
not reproduce GHSA-h46c-h94j-95f3 for those input shapes and does not clear it.

The same depth-4,096 array probe against upstream `jackson-core:2.15.0` threw
`StreamConstraintsException` at depth 1,001 with the default maximum of 1,000.
The fixed artifacts matched Maven Central SHA-1 checksum files. This verifies the
upstream depth guard, not compatibility with Minecraft's dependency graph. No
game-managed library override was made.

## Disposition and remaining work

All seven Jackson advisories remain **Further investigation**, failing and
release-blocking. No finding is marked Fixed, Not applicable, or Risk accepted.
The limited default integrated-server path and absent first-party triggers for
six advisory-specific operations narrow the first-party exposure; configured
dedicated-server identity parsing, public Log4j parser APIs, other installed
mods, and custom launchers keep package-wide reachability unresolved.

There is no mod-controlled fix. The compatible upstream release endpoints are
recorded above, but an updated library version is not by itself an approved
Minecraft runtime change. Mojang must provide a compatible game-managed update
or the project must obtain complete, supported launcher and mod-scope evidence
before any disposition can change. All 490 scanner matches continue to fail.
Legacy PRs #13, #14, and #16–#23 remain open and blocked; passing CI does not
resolve these findings. Issue #45 remains open, and the historical token owner
still needs to review account activity and rotate or revoke the credential if
exposure cannot be excluded.
