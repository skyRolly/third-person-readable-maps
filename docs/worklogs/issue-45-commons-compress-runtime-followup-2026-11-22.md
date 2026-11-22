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
- Hosted run [44980595788](https://github.com/skyRolly/third-person-readable-maps/actions/runs/44980595788) passed all four jobs on commit `51ec66fb9ace4506dcb43c738ba3ae407fafbdc3`. Both Linux and Windows Commons artifacts passed 2/2 cases; the downloaded ZIP SHA-256 values match the GitHub artifact digests. Their raw payloads and hashes are preserved in the hosted verification index.
- This coordination repository does not build or launch Minecraft. This evidence does not satisfy Issue #46 graphical, hardware-GPU, or multiplayer acceptance.

## Remaining actions

1. Obtain a safe test Realm or equivalent server-produced archive to test whether attacker-controlled world content can reach the malformed PAX metadata.
2. Request a compatible Minecraft/Realms update to Commons Compress 1.21 or later for the affected releases; do not override the library in this mod.
3. Complete supported launcher, third-party mod, and reflection call-path review for 7Z/ZIP findings.
4. Keep all 12 rows blocking until the applicable reachability and upstream remediation questions are resolved.


## Hosted matrix failure and fixture isolation — 2026-11-22

Hosted run [44980126217](https://github.com/skyRolly/third-person-readable-maps/actions/runs/44980126217) failed in both Linux and Windows reachability jobs. The existing Log4j/Netty/LZ4 runner compiles top-level Java fixtures against its own pinned classpath; the new Commons probe had been placed at that same level, so compilation failed with missing `org.apache.commons.compress` packages before either runner executed. The follow-up artifact upload then failed because its producer step was skipped. The coordination and live-prerequisite jobs passed.

The Commons fixture is now isolated under `tests/fixtures/critical_reachability/commons_compress/`, outside the existing runner's top-level source glob. The Commons-specific runner remains the only code that compiles it and supplies the exact pinned library classpath. This records a test-harness packaging defect; it does not change any security disposition or inventory count. A full Linux/Windows rerun is required before hosted probe evidence is recorded.


## Successful hosted rerun — 2026-11-22

Run [44980595788](https://github.com/skyRolly/third-person-readable-maps/actions/runs/44980595788), run 815, passed `Validate coordination`, `Validate live release prerequisites`, and both reachability jobs on source commit `51ec66fb9ace4506dcb43c738ba3ae407fafbdc3`. The Linux artifact zip SHA-256 `d44383985756c5ebf968b0d8ee0f0cb9ab5ab9275c8eec52f5696568ee85d404` matched GitHub's digest; its JSON payload SHA-256 is `4784ecd22e13ecd22aa2ff1ca4089badbfd8aaf0a0d5b0bb41d818ba2cb26725`. The Windows zip SHA-256 `1da228c197b105b9e094e651dbb8f76453511e7deb10a310c28577fe16520587` matched GitHub's digest; its JSON payload SHA-256 is `e8a0b06f7dd886d6f59002b23d814b2a8ddce0f05e882dfec41fbd96fb797798`. On both platforms, the isolated 1.8.1 probe caught `OutOfMemoryError` and fixed 1.21 rejected the identical PAX fixture before allocation. The initial failed run remains separately retained above. These component results still do not establish Realm-service attacker control or clear any advisory.
