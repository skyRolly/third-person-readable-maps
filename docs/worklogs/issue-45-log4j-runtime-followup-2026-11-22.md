# Issue #45 Log4j Runtime Follow-up — 2026-11-22

## Status

This is a new source-bound observation. Earlier audit reports remain unchanged. The local Linux matrix completed 27/27 expected component observations against analysis commit `0b49c544a31221b4c852657efeb5f694b071d1eb`. Hosted Linux and Windows matrices then each completed 27/27 on PR #53's source head `cdfbb61f6049bacfe7454095f9bbc68547ab6224`; both reports were independently revalidated after download. The hosted run and artifact hashes are recorded below and in the disposition overlay. These probes do not clear the remaining Log4j findings.

The overall inventory is unchanged: 490 blocking advisory occurrences (22 Critical, 177 High), including 385 legacy-candidate and 105 integrated-maintenance occurrences. No risk has been accepted.

## Source and dependency scope

All three findings are on Minecraft-managed `org.apache.logging.log4j:log4j-core`, not a library controlled by this mod or its Gradle plugins:

| Source group | Source SHA | Minecraft metadata versions | Log4j Core |
| --- | --- | --- | --- |
| `1.14-1.14.4` | `b6f7632af554a0e51c7d8c421c17adc893cc1379` | 1.14–1.14.4 | 2.8.1 |
| `1.15-1.16.5` | `4231b420749db2bbab3cf3e3a7825fc2516511d9` | 1.15–1.16.5 | 2.8.1 |
| `1.17-1.19.2` | `06b350856605011c1549d51d6edd3d351c5021c0` | 1.17–1.18.1 in this audit | 2.14.1 |

The `gradle` scope in the source inventory is the resolved Minecraft development graph; it does not make Log4j a Gradle plugin dependency. The runtime artifacts come from Minecraft version metadata. No library override was made.

The affected Log4j occurrence rows in this broad source group end at Minecraft 1.18.1. I separately checked current Mojang metadata and the exact Mojang Log4j Core JAR for 1.19, 1.19.1, and 1.19.2. All three select `log4j-core:2.17.0`; the downloaded JAR matched the metadata SHA-1 and size and is retained with SHA-256 `65c33dc9b24a5e5f6cacae62680641582894749c7bf16c951032ef92f3e12a60`. Apache lists 2.17.0 above the fixed releases for all three targeted advisories. Those exact version slices are recorded as **Not applicable** for these three advisory IDs only, without changing earlier 2.8.1/2.14.1 occurrences or counts. Other Log4j advisory occurrences attached to 2.17.0 remain in the inventory and are not cleared by this check.

Mojang’s current version manifest has republished metadata for 1.18 and 1.18.1. The retained content-addressed metadata still matches the historical launcher index, and the new report retains both versions. The current and retained records match on Java selection, Log4j/Patchy coordinates and order, logging argument, and logging configuration identity. The current snapshots and hashes are in the runtime evidence directory.

## Exact runtime observations

The Linux run downloaded the pinned Mojang runtime files and verified their manifest sizes and SHA-1 hashes before execution:

- 1.14.4: Mojang `jre-legacy` Java 8u202. The LDAP remote-codebase gate read `false`; no serial-data gate method was present in this runtime helper. The exact JDK LDAP `Obj` decoder accepted a harmless local serialized `String`, with zero network requests.
- 1.17.1: Mojang `java-runtime-alpha` Java 16.0.1. The codebase gate was `false`, while `trustSerialData` was `true` with the property unset. The exact LDAP decoder accepted the harmless local serialized `String`, with zero network requests.
- 1.18.1: Mojang `java-runtime-beta` Java 17.0.15. The codebase and serial-data gates were `false`; the exact LDAP decoder blocked the harmless serialized `String`, with zero network requests.
- Windows CI reproduced the same component behavior on its exact runtimes: Mojang Java 8u51 accepted the harmless serialized `String`; Java 16.0.1 accepted it; Java 17.0.15 blocked it. The JNDI codebase gate was `false` on each tested runtime. All three Windows decoder probes made zero network requests.

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

## Hosted verification and corrections

- Dedicated runtime workflow [44990273341](https://github.com/skyRolly/third-person-readable-maps/actions/runs/44990273341) passed both exact Mojang runtime jobs. Main CI [44990273351](https://github.com/skyRolly/third-person-readable-maps/actions/runs/44990273351) passed all four jobs, including the source-bound advisory validator on Linux and Windows.
- Archived report SHA-256 values: Linux `41654455bcc7d157efe9fd92fcebca5d0bca78290d6cba404d204fc066c6a33d`; Windows `3ccc71df7a299ada2f5f33ed93f653a765de13c4912e11afa53fb058785aca14`. GitHub artifact ZIP hashes are Linux `9087acdf23f0676386f95b1080dc02bb2146cc43fa9766679be10de5cab5bb09` and Windows `dc05be5705c7f46bdc2692e92aff07bcb04e0f7782a7ee5ec9537989dfc29e4c`. The archived ZIPs match GitHub's digests and contain the byte-identical reports and metadata snapshots.
- An earlier attempt to add the probe job to `.github/workflows/ci.yml` changed a file hash pinned by the source-bound evidence validator. Run `44989629297` correctly failed at that validator. I restored the pinned workflow byte-for-byte and placed the probe in a dedicated workflow; no evidence hash or security gate was relaxed.
- The first dedicated run, `44989857254`, passed Windows but Linux stopped before its first case because the relative runtime-cache path became invalid after the probe changed working directories. Commit `b0c625e` resolves the cache path before subprocess launches. A local rerun using a relative cache path passed 27/27, and the later hosted Linux and Windows jobs both passed 27/27.
- The first follow-up attempt at commit `91c4ca6` failed closed: CI run `44991949993` and runtime run `44991950010` stopped in source-bound validation because a root `.gitattributes` edit changed a hash pinned by the historical evidence. No new probes ran in those jobs. The root file is restored byte-for-byte (SHA-256 `ca2641a5b98a5f8e5955391837049be2cf0d64be90d220b6ddbbf55ccc20207e`); byte preservation for the new downloaded artifacts is now scoped in the new evidence directory's `.gitattributes`. The failed attempts remain recorded and no security gate or historical evidence was weakened.
- At commit `e60cb56`, both exact-runtime probes again produced 27/27 expected observations, and all four main CI jobs passed in run `44992126616`. The dedicated validator then caught two packaging/portability defects: the hash-verified Log4j 2.17.0 JAR was ignored by the generic `*.jar` rule and omitted from the commit, while the Windows runner represented a metadata path with backslashes and the validator constructed a POSIX ZIP prefix using `str(Path)`. A subsequent commit added the JAR explicitly and changed the ZIP prefix to `Path.as_posix()`. Dedicated run `44992126630` failed on both platforms at evidence validation, after the probes passed. The retained original reports and artifacts are unchanged.
- After those corrections, PR head `86a6f4a1c652d1b6725828bcb1caa7dcb61044d8` passed the dedicated exact-runtime workflow [44992388625](https://github.com/skyRolly/third-person-readable-maps/actions/runs/44992388625): Linux and Windows each reported 27/27 expected observations and passed evidence validation. Main CI [44992388657](https://github.com/skyRolly/third-person-readable-maps/actions/runs/44992388657) passed all four jobs, including Linux/Windows regression probes and source-bound validation. The full local Python suite passed 185 tests. The historical root `.gitattributes` hash remains exact, and the committed JAR blob matches its retained SHA-256.
- The exact Mojang version metadata and Log4j Core 2.17.0 artifact for 1.19–1.19.2 are retained in [the 1.19 version check](../dependency-evidence/critical-reachability-2026-11-21/log4j-runtime-hosted-2026-11-22/minecraft-1.19-log4j-version-check.json) and its SHA-256 verified JAR.

## Remaining work

1. Capture actual supported-launcher JVM arguments and classpaths, and verify the logging resource that the process loads.
2. Bound the supported mod/agent/custom-launcher threat model and trace custom layouts, ThreadContext writes, reflective entry points, and socket-server creation.
3. Ask Mojang for a compatible game-managed Log4j update and verify it across the affected versions before calling anything fixed.
4. Resolve the historical `GH_TOKEN` incident with the token owner’s audit and revoke/rotation action. The credential status is unchanged.

Issue #45 remains open. Issue #46’s graphics, hardware-GPU, and multiplayer acceptance is still separate.

## Evidence files

- [Linux exact-runtime probe JSON](../dependency-evidence/critical-reachability-2026-11-21/log4j-mojang-runtime-2026-11-22/mojang-log4j-runtime-probes-linux.json)
- [Hosted Linux and Windows reports and original artifact ZIPs](../dependency-evidence/critical-reachability-2026-11-21/log4j-runtime-hosted-2026-11-22/)
- [Exact 1.19–1.19.2 Log4j version check](../dependency-evidence/critical-reachability-2026-11-21/log4j-runtime-hosted-2026-11-22/minecraft-1.19-log4j-version-check.json)
- [New source-bound Log4j disposition overlay](../dependency-evidence/critical-reachability-2026-11-21/log4j-runtime-observations-2026-11-22.json)
- [Prior exact-client chat-to-logger evidence](../dependency-evidence/critical-reachability-2026-11-21/log4j-chat-input-reachability-2026-11-21.json)
- [Immutable Mojang runtime and version metadata snapshots](../dependency-evidence/critical-reachability-2026-11-21/log4j-mojang-runtime-2026-11-22/metadata/)
