# Compatibility decision record

The 1.21.11 and 26.x groups are maintained; the older rows below describe draft
candidates. No `0.0.2` artifact has been published as a coordinated release.
The [Mojang version manifest](https://piston-meta.mojang.com/mc/game/version_manifest_v2.json)
listed 26.3 as the latest stable release on 2026-11-04; 26.4 was a snapshot.
All 1.21 releases listed here require Java 21 and all listed 26.x releases require
Java 25, according to their Mojang version manifests. Fabric Loader 0.20.1 is
selected and declared as the minimum for all three maintenance builds.

| Minecraft | Injection/API evidence | Same candidate JAR | Runtime evidence | Decision |
| --- | --- | --- | --- | --- |
| 1.21, 1.21.1 | `renderArmWithItem(LivingEntity, ItemStack, ...)` | One candidate for both | Both worlds and partial map smoke | Draft [#17](https://github.com/skyRolly/third-person-readable-maps/pull/17); full acceptance pending |
| 1.21.2, 1.21.3 | `renderArmWithItem(LivingEntityRenderState, BakedModel, ...)` | One candidate for both | Both worlds and partial map smoke | Draft [#16](https://github.com/skyRolly/third-person-readable-maps/pull/16); full acceptance pending |
| 1.21.4–1.21.8 | `renderArmWithItem(ArmedEntityRenderState, ItemStackRenderState, ..., MultiBufferSource, ...)` | One candidate for all five | All five worlds and partial map smoke | Draft [#14](https://github.com/skyRolly/third-person-readable-maps/pull/14); full acceptance pending |
| 1.21.9, 1.21.10 | `submitArmWithItem` lacks the 1.21.11 `ItemStack` parameter | One candidate for both | Both worlds and partial map smoke | Draft [#13](https://github.com/skyRolly/third-person-readable-maps/pull/13); full acceptance pending |
| 1.21.11 | Exact target and signature checked against mapped game classes | 1.21.11 only | Earlier 0.0.1 development-client graphical test: [PR #1](https://github.com/skyRolly/third-person-readable-maps/pull/1); the [previously tested JAR](https://github.com/skyRolly/third-person-readable-maps/pull/4) loaded and applied its Mixin on Java 21 in an installed client and joined a single-player world | Maintained in `mc/1.21.11`; full current graphical matrix remains a release gate |
| 26.1, 26.1.1, 26.1.2, 26.2 | Same injection descriptor; these versions have `PoseStack.mulPose(Quaternionfc)` and lack 26.3’s `rotateDegrees` | One 26.1–26.2 JAR; separate from 26.3 | The identical installed Java 25 JAR loaded, applied its Mixin, and displayed map terrain in third person on all four | [Maintenance implementation #7](https://github.com/skyRolly/third-person-readable-maps/pull/7), compiled against 26.1; broader hand/arm coverage remains a release gate |
| 26.3 | Exact target and signature checked against game classes | 26.3 only | [PR #3](https://github.com/skyRolly/third-person-readable-maps/pull/3) reports a Java 25 development-client graphical test; the [previously tested JAR](https://github.com/skyRolly/third-person-readable-maps/pull/5) loaded and applied its Mixin in an installed Java 25 client using software Vulkan | Maintained in `mc/26.3`; full current graphical matrix remains a release gate |

The 1.21 entries were inspected in Mojang's official client mappings, including
the target method's complete descriptor. The 26.x entries were inspected in the
unobfuscated game class files with `javap -p -s` and by resolving the packaged
mod’s game member references in each actual client JAR. The 26.3 JAR calls
`rotateDegrees`, which is absent on 26.1–26.2; the older group’s
`mulPose(Quaternionfc)` is absent in 26.3. The same older-group JAR was then
installed and visually smoke-tested on each of its four declared versions. CI
repeats version-by-version static target and member checks; it does not automate
gameplay. The legacy candidates described below add ports and partial installed-client
smoke tests; snapshots remain outside the stable-release scope.

[Fabric's 26.1 announcement](https://fabricmc.net/2026/03/14/261.html) documents
the transition from obfuscated distributions and the remapping Loom plugin to
unobfuscated distributions and the standard Loom plugin. The 1.21.11 artifact
uses intermediary names and `remapJar`; 26.x uses official names and `jar`.
The obfuscation and pose API boundaries require separate artifacts. The 26.3 port in PR #3
also replaces removed pose rotation calls while retaining their order and values.

## Toolchain decision

| Group | Gradle execution JDK | Compiler and target | Minimum runtime | Gradle / Loom / Loader |
| --- | --- | --- | --- | --- |
| Legacy 1.20.5–1.21.10 candidates | Temurin 25.0.5+8 | JDK 25 with `--release 21` | Java 21 | 9.8.2 / 1.19.3 / 0.20.1 |
| Legacy 1.19.3–1.20.4 candidates | Temurin 25.0.5+8 | JDK 25 with `--release 17` | Java 17 | 9.8.2 / 1.19.3 / 0.20.1 |
| Legacy 1.17–1.19.2 candidate | Temurin 25.0.5+8 | JDK 25 with `--release 16` | Java 16 for 1.17; Java 17 for 1.18+ | 9.8.2 / 1.19.3 / 0.20.1 |
| Legacy 1.14–1.14.4 candidate (Yarn 1.14.4+build.18) | Temurin 25.0.5+8 | JDK 25 with `--release 8` | Java 8 | 9.8.2 / 1.19.3 / 0.20.1 |
| Legacy 1.15–1.16.5 candidate | Temurin 25.0.5+8 | JDK 25 with `--release 8` | Java 8 | 9.8.2 / 1.19.3 / 0.20.1 |
| 1.21.11 | Temurin 25.0.5+8 | JDK 25 with `--release 21` | Java 21 | 9.8.2 / 1.19.3 / 0.20.1 |
| 26.1–26.2 | Temurin 25.0.5+8 | JDK 25 with `--release 25` | Java 25 | 9.8.2 / 1.19.3 / 0.20.1 |
| 26.3 | Temurin 25.0.5+8 | JDK 25 with `--release 25` | Java 25 | 9.8.2 / 1.19.3 / 0.20.1 |

All three clean Linux builds passed with the selected tools. The 1.21.11 build's
`--release 21` restricts both the Java API surface and bytecode, and the JAR
verification rejects classes newer than Java 21. Minecraft 26.3 and the
[published Loom 1.19.3 module](https://maven.fabricmc.net/net/fabricmc/fabric-loom/1.19.3/fabric-loom-1.19.3.module)
require a Java 25 build JVM. Java 25 is not imposed as a runtime requirement on
the older artifact. CI pins the latest investigated LTS maintenance build;
local developers may use a compatible Java 25 maintenance build. Exact runtime
and graphical results must be recorded independently of compilation.

## Dependency maintenance

The old baseline had Gradle 9.8.2, Loom 1.17.21 and Loader 0.19.3. The maintained branches
use the latest stable versions observed on 2026-11-04: Gradle 9.8.2, Loom
1.19.3 and Loader 0.20.1. Fabric API remains absent because the mod does not use
it. The checked-in Actions references are pinned to release commits; see the
workflows for versions. Do not override Minecraft-managed runtime libraries in
the mod to silence an alert.

Dependabot's existing `dependency_not_found` security-update failures concern
libraries injected from Minecraft manifests by Loom, rather than missing entries
in the submitted dependency graph. [PR #3](https://github.com/skyRolly/third-person-readable-maps/pull/3)
contains the investigation and remaining advisory ranges. The alert API returned
HTTP 403 during this investigation, so individual alerts and branch protections
could not be verified. Keep security updates and alerts enabled. GitHub's
security updates primarily use the default branch; version updates can target
additional maintenance branches. Version updates target all three existing
maintenance branches. The scheduled advisory scan and its limitations are
described in the [release guide](releasing.md#dependency-maintenance).


## Maintenance verification — 2026-11-04

The cleanup PRs preserve this matrix and all Java, namespace, Mixin and rendering
boundaries. Their clean Linux builds and four-version static API checks passed;
negative checks rejected the shared JAR against 1.21.11 and 26.3. Historical runtime
reports above do not bind these new PR source SHAs and artifacts. Fresh installed-client
and graphical reports for every version remain required before release. See the
[release gates](release-readiness-2026-11-04.md).

Runtime dependency manifests are not identical across all shared-JAR versions:
26.2 updates Netty, Log4j, Guava and others. The [monitoring record](dependency-monitoring.md)
therefore adds per-version manifest auditing alongside the 26.1 Gradle snapshot.
This changes monitoring, not the supported game matrix or distributable identity.

## Legacy investigation

The [1.14–1.21.10 inventory](legacy-version-inventory.md) and
[grouping decisions](legacy-group-decisions.md) distinguish candidates from
integrated support. [PR #13](https://github.com/skyRolly/third-person-readable-maps/pull/13)
and [PRs #14 and #16–#23](legacy-group-decisions.md) contain legacy candidates. None is registered in the authoritative release configuration or security ledger.
