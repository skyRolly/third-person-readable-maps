# Issue #45 Commons Compress TAR follow-up — 2026-11-22

## Scope and sources

This follow-up examines the four High findings for `org.apache.commons:commons-compress:1.8.1` in candidate groups `1.14-1.14.4`, `1.15-1.16.5`, and `1.17-1.19.2`. Each advisory has one occurrence per group, for 12 scoped rows. The archived exact-source report identifies Mojang as the runtime dependency owner and preserves the three candidate source SHAs.

Apache's security report lists Commons Compress 1.21 as the first fixed version for CVE-2021-35517, CVE-2021-35515, CVE-2021-35516, and CVE-2021-36090. The 1.8.1 JAR and Commons IO 2.5 JAR were matched to the exact Mojang 1.14.4 version manifest; the fixed 1.21 JAR was verified against Maven Central's SHA-1 sidecar and pinned SHA-256/size.

## TAR path and bounded reproduction

The exact Mojang Realms and Minecraft artifacts show the optional world-download path reading `WorldDownload.downloadLink`, fetching a gzip TAR, wrapping it in `GzipCompressorInputStream` and then `TarArchiveInputStream`, and asking for the next TAR entry. This path exists in the affected Minecraft 1.14 through 1.17.1 clients/libraries. The earlier source-bound report retains the JAR hashes and class-level call-site evidence.

A 111-byte gzip TAR fixture expands to a 2,560-byte TAR. Its PAX extension entry contains 17 physical bytes but claims a 100,000,000-byte record. Under Temurin OpenJDK 21.0.13+9 with a 32 MiB heap, the same probe class and input produced:

- Commons Compress 1.8.1 with manifest-supplied Commons IO 2.5: `OutOfMemoryError` caught inside the isolated process.
- Upstream-fixed Commons Compress 1.21 with Commons IO 2.5: `IOException` rejects the PAX value length before allocating the claimed size.

The probe is local-only and does not launch Minecraft or contact Realms. It confirms affected component behavior and the parser API behavior, not that a remote Realm operator can cause the service to return this malformed TAR.

## Disposition and limits

`GHSA-xqfj-vm6h-2x34` / CVE-2021-35517 remains **Further investigation** and release-blocking. Its vanilla path is proven reachable after a user-selected Realm download, but the archive is produced by the Realms service. No test Realm or server-side experiment established whether a Realm owner can preserve crafted PAX record lengths or whether the service normalizes/rejects them. No mod-controlled mitigation exists; no Minecraft library override was applied.

The three 7Z/ZIP findings remain **Further investigation** and release-blocking. Exact first-party inspection recorded no direct vulnerable 7Z/ZIP parser path, but third-party mod and reflective call paths are not exhausted. No risk is accepted and no findings are cleared.

## Verification

- Local Linux probe: 2/2 outcomes matched the expected vulnerable/fixed behavior.
- The PR CI will run the same pinned fixture and exact artifacts on Linux and Windows, validate the report against exact source SHAs, and retain probe results.
- This coordination repository does not build or launch Minecraft. This evidence does not satisfy Issue #46 graphical, hardware-GPU, or multiplayer acceptance.

## Remaining actions

1. Obtain a safe test Realm or equivalent server-produced archive to test whether attacker-controlled world content can reach the malformed PAX metadata.
2. Request a compatible Minecraft/Realms update to Commons Compress 1.21 or later for the affected releases; do not override the library in this mod.
3. Complete supported launcher, third-party mod, and reflection call-path review for 7Z/ZIP findings.
4. Keep all 12 rows blocking until the applicable reachability and upstream remediation questions are resolved.
