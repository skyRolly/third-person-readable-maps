# Third Person Readable Maps

[![CI — mc/26.3](https://github.com/skyRolly/third-person-readable-maps/actions/workflows/ci.yml/badge.svg?branch=mc%2F26.3)](https://github.com/skyRolly/third-person-readable-maps/actions/workflows/ci.yml?query=branch%3Amc%2F26.3)

A client-side Fabric mod that renders filled map contents on maps held in third-person view. Maps follow the holding arm, with layouts for the main hand, off hand, and occupied opposite hand, including left-handed players.

## Requirements and installation

Build from source, or download and extract an artifact from a successful
[branch CI run](https://github.com/skyRolly/third-person-readable-maps/actions/workflows/ci.yml?query=branch%3Amc%2F26.3). CI artifacts are development builds;
mod version `0.0.2` has not yet been publicly released.

- Minecraft **26.3** and Fabric Loader **0.20.1 or newer**.
- Java **25 or newer** to play. Fabric API is not required.
- Copy `third-person-readable-maps-<version>-mc26.3.jar` into the client
  instance's `mods` directory, then launch its Fabric profile.

Your client must have received the map data to display its contents. The server
does not need the mod. Mod ID: `thirdpersonreadablemaps`.

## Build from source

Install **Python 3** and a **Java 25 JDK**, with `JAVA_HOME` pointing to it or its `bin` directory
on `PATH`. CI pins Eclipse Temurin **25.0.5+8**. The committed Gradle **9.8.2**
wrapper downloads and verifies Gradle; no separate Gradle installation is needed.
Network access is required for Gradle, Minecraft, and Fabric dependencies.
Fabric Loom **1.19.3** and Fabric Loader **0.20.1** are pinned in `gradle.properties`.

Build and runtime use Java 25. Minecraft 26.3 ships unobfuscated; Loom's
standard `jar` task produces an official-namespace distributable. This separate
JAR preserves the rendering API adaptations required by 26.3.

```sh
# Linux / macOS
python3 scripts/verify_gradle_wrapper.py
./gradlew --no-daemon clean build
```

```bat
:: Windows Command Prompt
python scripts\verify_gradle_wrapper.py
gradlew.bat --no-daemon clean build
:: Or use the entry point from any directory:
Build-Windows.bat
```

In PowerShell, prefix Windows commands with `.\`. The installable output is
`build/libs/third-person-readable-maps-<version>-mc26.3.jar` (currently `0.0.2`).
Generated build files stay under `build/`.

## Validation and contributions

Open game-specific PRs against `mc/26.3` and coordination PRs against `main`.
Port shared changes to each affected maintenance branch in separate reviewed PRs.
CI runs clean Java 25 builds on Linux and Windows, validates the Gradle wrapper,
and checks Fabric metadata, the packaged MIT license, Java bytecode, mapping
namespace, and the Mixin target signature. It retains JARs and verification reports.
Run the Wrapper preflight before Gradle and run `python -m unittest discover -s tests` to check the preflight fixtures.

For graphical checks, run the Wrapper preflight first, then `./gradlew runClient` (Windows: `.\gradlew.bat runClient`)
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

`mc/26.3` is an established maintenance branch. Version `0.0.2` remains unreleased.
A coordinated release uses one `X.X.X` tag and three game-specific JARs, with
reviewed source revisions, runtime evidence, provenance, checksums, and independent
approvals. See the [compatibility record](https://github.com/skyRolly/third-person-readable-maps/blob/main/docs/compatibility.md)
and [release guide](https://github.com/skyRolly/third-person-readable-maps/blob/main/docs/releasing.md).

Licensed under [MIT](LICENSE).
