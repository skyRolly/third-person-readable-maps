# Issue #45 Log4j Runtime Follow-up — 2026-11-22

## Status

This is a new source-bound observation. Earlier audit reports remain unchanged. The Linux Mojang runtime matrix completed 27/27 expected component observations against analysis commit `0b49c544a31221b4c852657efeb5f694b071d1eb`. Its JSON SHA-256 is `cc9196e73b1928acac20a8975ef489344a81715436545bee82b24dc949e4623e`. It does not clear security findings. The Windows runtime matrix is now part of Linux/Windows CI and remains pending that run.

The overall inventory is unchanged: 490 blocking advisory occurrences (22 Critical, 177 High), including 385 legacy-candidate and 105 integrated-maintenance occurrences. No risk has been accepted.

## Source and dependency scope

All three findings are on Minecraft-managed `org.apache.logging.log4j:log4j-core`, not a library controlled by this mod or its Gradle plugins:

| Source group | Source SHA | Minecraft metadata versions | Log4j Core |
| --- | --- | --- | --- |
| `1.14-1.14.4` | `b6f7632af554a0e51c7d8c421c17adc893cc1379` | 1.14–1.14.4 | 2.8.1 |
| `1.15-1.16.5` | `4231b420749db2bbab3cf3e3a7825fc2516511d9` | 1.15–1.16.5 | 2.8.1 |
| `1.17-1.19.2` | `06b350856605011c1549d51d6edd3d351c5021c0` | 1.17–1.18.1 in this audit | 2.14.1 |

The `gradle` scope in the source inventory is the resolved Minecraft development graph; it does not make Log4j a Gradle plugin dependency. The runtime artifacts come from Minecraft version metadata. No library override was made.

Mojang’s current version manifest has republished metadata for 1.18 and 1.18.1. The retained content-addressed metadata still matches the historical launcher index, and the new report retains both versions. The current and retained records match on Java selection, Log4j/Patchy coordinates and order, logging argument, and logging configuration identity. The current snapshots and hashes are in the runtime evidence directory.

## Exact runtime observations

The Linux run downloaded the pinned Mojang runtime files and verified their manifest sizes and SHA-1 hashes before execution:

- 1.14.4: Mojang `jre-legacy` Java 8u202. The LDAP remote-codebase gate read `false`; no serial-data gate method was present in this runtime helper. The exact JDK LDAP `Obj` decoder accepted a harmless local serialized `String`, with zero network requests.
- 1.17.1: Mojang `java-runtime-alpha` Java 16.0.1. The codebase gate was `false`, while `trustSerialData` was `true` with the property unset. The exact LDAP decoder accepted the harmless local serialized `String`, with zero network requests.
- 1.18.1: Mojang `java-runtime-beta` Java 17.0.15. The codebase and serial-data gates were `false`; the exact LDAP decoder blocked the harmless serialized `String`, with zero network requests.

The serialized-data test invokes the JDK LDAP `Obj.decodeObject` locally. It proves only the exact runtime’s handling of a benign serialized value. It does not use a remote LDAP server, a gadget, executable object, or network connection, and does not prove a remote exploit.

## Log4j and game input path

The retained launcher survey covers 18 Minecraft metadata versions. Each specifies `-Dlog4j.configurationFile=${path}` and the same `client-1.12.xml`. The metadata contains no Log4j/JNDI-specific JVM argument. No live launcher process was captured, so actual argument preservation and classpath assembly remain unverified.

Exact Minecraft client analysis in the prior report traces remote chat text to the `[CHAT]` logger for 1.14.4 and 1.17.1. In the new exact-runtime component run, the launcher XML kept lookup syntax literal and the local JNDI context received zero calls for all three representative versions. The embedded fallback XML produced two synthetic JNDI calls on Log4j 2.14.1. For 2.8.1, manifest order put Patchy 1.3.9 before Core and the fallback probe made zero calls; reversing the order produced two. These were local synthetic lookups, not external LDAP requests.

For CVE-2021-45046, the inspected vanilla chat path did not place the message in ThreadContext/MDC and the launcher XML did not contain a context lookup. The synthetic non-default context-layout probe did activate JNDI on Log4j 2.14.1. Installed mods and custom layouts were not exhaustively inspected.

For CVE-2017-5645, Apache describes the affected path as Log4j Core TCP/UDP socket servers receiving serialized log events. The retained default XML does not configure these servers, and the prior exact-client literal scan found no direct `TcpSocketServer` or `UdpSocketServer` reference. The JDK LDAP deserialization results above concern a separate JNDI path and are not evidence that the Log4j socket-server path is active.

## Advisory dispositions

All three findings remain **Further investigation**, failing, and release-blocking:

- `GHSA-jfh8-c2jp-5v3q` / CVE-2021-44228: exact default logging probes do not expand chat markers, but JNDI lookup is active with alternate configurations; Java 8u202 and Java 16.0.1 accepted a benign LDAP serialized object. The supported-launcher process and third-party mod/configuration scope remain unverified.
- `GHSA-7rjr-3q55-vv33` / CVE-2021-45046: the default vanilla chat/MDC path did not activate the condition in probes. Non-default context layouts did activate lookup behavior; mod and launcher changes remain unexamined.
- `GHSA-fxph-q3j8-mv87` / CVE-2017-5645: no default socket-server configuration or direct game-client reference was found. Supported launchers, reflective startup, and third-party appenders/mods remain outside the captured scope.

Apache identifies Log4j 2.15.0 as the first fix for CVE-2021-44228, 2.16.0 for CVE-2021-45046, and 2.8.2 for CVE-2017-5645. Apache documents 2.17.2 as Java 8 compatible. A later compatible Log4j release is a possible upstream remediation target for the combined family, but compatibility with each historical Minecraft client and its mod ecosystem has not been tested. Minecraft owns these dependencies, so this repository did not force an override.

## Remaining work

1. Complete the Windows CI run against the exact Mojang Windows runtimes, especially `jre-legacy` 8u51, and inspect its JSON artifact.
2. Capture actual supported-launcher JVM arguments and classpaths, and verify the logging resource that the process loads.
3. Bound the supported mod/agent/custom-launcher threat model and trace custom layouts, ThreadContext writes, reflective entry points, and socket-server creation.
4. Ask Mojang for a compatible game-managed Log4j update and verify it across the affected versions before calling anything fixed.
5. Resolve the historical `GH_TOKEN` incident with the token owner’s audit and revoke/rotation action. The credential status is unchanged.

Issue #45 remains open. Issue #46’s graphics, hardware-GPU, and multiplayer acceptance is still separate.

## Evidence files

- [Linux exact-runtime probe JSON](../dependency-evidence/critical-reachability-2026-11-21/log4j-mojang-runtime-2026-11-22/mojang-log4j-runtime-probes-linux.json)
- [New source-bound Log4j disposition overlay](../dependency-evidence/critical-reachability-2026-11-21/log4j-runtime-observations-2026-11-22.json)
- [Prior exact-client chat-to-logger evidence](../dependency-evidence/critical-reachability-2026-11-21/log4j-chat-input-reachability-2026-11-21.json)
- [Immutable Mojang runtime and version metadata snapshots](../dependency-evidence/critical-reachability-2026-11-21/log4j-mojang-runtime-2026-11-22/metadata/)
