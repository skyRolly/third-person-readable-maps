# Issue #45 Guava deserialization runtime follow-up — 2026-11-22

## Scope and source bindings

Investigated `GHSA-xxph-c9ww-hj94` / `CVE-2026-102554` for the exact candidate and integrated records in the 2026-11-21 finding index. The advisory covers `com.google.guava:guava` versions `>= 4.0, <= 33.7.1`; upstream identifies `33.7.2` as the first fixed version. The 16 indexed occurrences cover 13 source groups, 48 Minecraft versions, and seven exact Guava versions: 21.0, 31.0.1-jre, 31.1-jre, 32.1.2-jre, 33.3.1-jre, 33.5.0-jre, and 33.6.0-jre.

Official Minecraft version manifests supply every affected Guava runtime artifact. The finding records also show Gradle resolution scopes, which describe the resolved game library graph and do not make Guava a mod-declared dependency or Gradle plugin dependency. Each occurrence retains its exact source SHA, purl, runtime scopes, source report checksum, and Minecraft client/manifest identities in the [source-bound disposition record](../dependency-evidence/critical-reachability-2026-11-21/source-bound-dispositions-2026-11-21.json).

## Vulnerable component and fixed release

The captured [GitHub advisory response](../dependency-evidence/critical-reachability-2026-11-21/guava-probes-2026-11-22/guava-upstream-advisory.json), [upstream fix patch](../dependency-evidence/critical-reachability-2026-11-21/guava-probes-2026-11-22/upstream-fix.patch), and [33.7.2 release response](../dependency-evidence/critical-reachability-2026-11-21/guava-probes-2026-11-22/guava-release.json) bind the affected range and fix. Upstream caps eager collection allocation at `min(elementCount, 256)` in `CompactHashMap`, `CompactHashSet`, and `MapMakerInternalMap` deserialization and adds malicious-stream tests.

An isolated probe used a 64 MiB heap and modified a serialized collection size to `Integer.MAX_VALUE`. Guava 21.0's `MapMakerInternalMap` and all three tested classes in 33.6.0-jre produced `OutOfMemoryError`. In 33.7.2-jre, the compact map and set rejected the intentionally truncated stream after bounded allocation, while `MapMakerInternalMap` deserialized normally. The tested 33.7.2 artifact matches the captured Maven Central SHA-1 and SHA-256 sidecars. This verifies the component behavior; it is not a live Minecraft or remote-stream exploit test.

## Minecraft and library paths

The reproducible [runtime scanner](../../scripts/scan_guava_runtime_reachability.py) hash-checks and inspects 48 exact Minecraft client jars and 655 unique runtime library artifacts. No client jar contains a literal reference to the targeted Java object deserialization, Netty `ObjectDecoder`, or vulnerable Guava collection classes. Eighty-six library artifacts contain at least one targeted serialization-related class reference; Netty's generic `ObjectDecoder` is present in the runtime library set. The [compressed scan result](../dependency-evidence/critical-reachability-2026-11-21/guava-probes-2026-11-22/runtime-scan.json.gz) records each client and library identity, hash, coordinate, version set, and match.

Bytecode captures bind vanilla packet paths to exact client artifacts for Minecraft 1.14.4, 1.21.10, and 26.3. In these samples, the connection pipeline constructs Minecraft's `PacketDecoder`, which extends Netty `ByteToMessageDecoder` and feeds a Minecraft packet codec. That is evidence about those vanilla paths only. The other 45 client versions have literal-reference results but no individual packet-decoder trace in this follow-up.

This narrows vanilla-client reachability but does not establish general non-reachability. Launchers, mod loaders, third-party mods, agents, reflection, and custom pipelines can add deserialization paths to the same JVM. No supported production launcher classpath or mod list was available, and no attacker-controlled Java object stream was delivered through an actual game endpoint.

## Disposition and remediation

All 16 findings remain **Further investigation**, failing, and release-blocking. No risk is accepted, and no occurrence is marked fixed or not applicable. Guava is Minecraft-managed across these source groups; the mod/build does not control these version pins. No dependency override was added. Compatible remediation requires a Minecraft runtime update to a fixed Guava line or a separately supported launcher replacement with game and mod compatibility verification.

The focused source-bound set now contains 22 Critical and 60 High occurrences (82 total). The complete candidate/integrated inventory remains unchanged at 490 failing occurrences. Candidate (385) and integrated (105) counts remain separate.

## Remaining work

- Capture each supported launcher's effective classpath and loaded mod/agent list.
- Review third-party networking and deserialization entry points with attacker-controlled input for each supported launcher family.
- Obtain and verify compatible Minecraft-managed library remediation before clearing these findings.
- Complete independent human security review. Issue #45 remains open and these occurrences remain blockers.
