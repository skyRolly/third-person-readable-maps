# Third Person Readable Maps

[![CI — mc/1.21.9-1.21.10](https://github.com/skyRolly/third-person-readable-maps/actions/workflows/ci.yml/badge.svg?branch=mc%2F1.21.9-1.21.10)](https://github.com/skyRolly/third-person-readable-maps/actions/workflows/ci.yml?query=branch%3Amc%2F1.21.9-1.21.10)

A client-side Fabric mod that renders filled map contents on maps held in third-person view. Maps follow the holding arm, with layouts for the main hand, off hand, and occupied opposite hand, including left-handed players.

## Requirements and installation

Build from source, or download and extract an artifact from a successful
[branch CI run](https://github.com/skyRolly/third-person-readable-maps/actions/workflows/ci.yml?query=branch%3Amc%2F1.21.9-1.21.10). CI artifacts are development builds;
mod version `0.0.2` has not yet been publicly released.

- Candidate for Minecraft **1.21.9 and 1.21.10** and Fabric Loader **0.20.1 or newer**.
- Java **21 or newer** to play. Fabric API is not required.
- Copy `third-person-readable-maps-<version>-mc1.21.9-1.21.10.jar` into the client
  instance's `mods` directory, then launch its Fabric profile.

Your client must have received the map data to display its contents. The server
does not need the mod. Mod ID: `thirdpersonreadablemaps`.

## Build from source

Install a **Java 25 JDK**, with `JAVA_HOME` pointing to it or its `bin` directory
on `PATH`. CI pins Eclipse Temurin **25.0.5+8**. The committed Gradle **9.8.2**
wrapper downloads and verifies Gradle; no separate Gradle installation is needed.
Network access is required for Gradle, Minecraft, and Fabric dependencies.
Fabric Loom **1.19.3** and Fabric Loader **0.20.1** are pinned in `gradle.properties`.

Gradle and the compiler use Java 25; `--release 21` preserves Java 21 APIs
and bytecode. Remapping Loom produces the intermediary/remapped installable JAR.
`build/devlibs/` contains development intermediates; install from `build/libs/`.

```sh
# Linux / macOS
./gradlew --no-daemon clean build
```

```bat
:: Windows Command Prompt
gradlew.bat --no-daemon clean build
:: Or use the entry point from any directory:
Build-Windows.bat
```

In PowerShell, prefix Windows commands with `.\`. The installable output is
`build/libs/third-person-readable-maps-<version>-mc1.21.9-1.21.10.jar` (currently `0.0.2`).
Generated build files stay under `build/`.

## Validation and contributions

Open game-specific PRs against `mc/1.21.9-1.21.10` and coordination PRs against `main`.
Port shared changes to each affected maintenance branch in separate reviewed PRs.
CI runs clean Java 25 builds on Linux and Windows, validates the Gradle wrapper,
and checks Fabric metadata, the packaged MIT license, Java bytecode, mapping
namespace, both Mixin target signatures, and game symbols against both advertised clients. It retains JARs and verification reports.
Run the same build checks locally with `./gradlew build`.

For graphical checks, run `./gradlew runClient` (Windows: `.\gradlew.bat runClient`)
on a machine with graphics support. Check filled maps in each hand, both maps,
an occupied opposite hand, both dominant-arm settings, missing map data, arm
movement, and unchanged first-person behavior. CI does not verify visual rendering;
installed-client and graphical evidence for every supported version remain release gates.

Report bugs in the [issue tracker](https://github.com/skyRolly/third-person-readable-maps/issues), including Minecraft, Fabric Loader,
Java, and mod versions, reproduction steps, and the relevant client log.

## Dependency maintenance and security

The dependency inspection job resolves Gradle dependencies and retains a snapshot
for 14 days. Uploading it does **not** submit it to GitHub's Dependency Graph.
Weekly Dependabot version-update configuration is owned by `main`; security alerts
on the default branch do not provide equivalent coverage for this branch.
Central OSV auditing reports maintenance dependencies and game runtime manifests.
See the [monitoring record](https://github.com/skyRolly/third-person-readable-maps/blob/main/docs/dependency-monitoring.md)
and [advisory ledger](https://github.com/skyRolly/third-person-readable-maps/blob/main/docs/security-advisories.md) for coverage,
individual dispositions, and unresolved risks.

Minecraft supplies libraries such as Netty, Log4j, Guava, and LZ4 to the client
runtime through Loom and its version manifests. These are not bundled in the mod
JAR. Compatible upstream fixes require review; arbitrary overrides in this mod's
build do not safely patch an installed game's libraries.

## Compatibility and release status

`mc/1.21.9-1.21.10` is a proposed maintenance branch; the artifact is a candidate pending installed-client and graphical acceptance for both versions. Version `0.0.2` remains unreleased.
A coordinated release uses one `X.X.X` tag and one JAR per verified group, with
reviewed source revisions, runtime evidence, provenance, checksums, and independent
approvals. See the [compatibility record](https://github.com/skyRolly/third-person-readable-maps/blob/main/docs/compatibility.md)
and [release guide](https://github.com/skyRolly/third-person-readable-maps/blob/main/docs/releasing.md).

Licensed under [MIT](LICENSE).
