# Third Person Readable Maps

[![CI](https://github.com/skyRolly/third-person-readable-maps/actions/workflows/ci.yml/badge.svg)](https://github.com/skyRolly/third-person-readable-maps/actions/workflows/ci.yml)

A client-side Fabric mod that renders filled map contents on maps held in
third-person view. Maps follow the holding arm, with layouts for the main hand,
off hand, and occupied opposite hand, including left-handed players.

## Requirements and installation

Build the mod below, or download and extract a mod artifact from a successful
[CI run](https://github.com/skyRolly/third-person-readable-maps/actions/workflows/ci.yml).

- Minecraft **1.21.11** and Fabric Loader **0.20.1 or newer**.
- Java **21 or newer** to play. Fabric API is not required.
- Copy `third-person-readable-maps-<version>-mc1.21.11.jar` into your instance's `mods`
  directory, then launch its Fabric profile.

Your client must have received the map data to display its contents. The mod does
not need to be installed on the server. Mod ID: `thirdpersonreadablemaps`.

## Build from source

Install a **Java 25 JDK**, with `JAVA_HOME` pointing to it or its `bin` directory
on `PATH`. The committed Gradle **9.8.2** wrapper downloads and verifies Gradle;
you do not need a separate Gradle installation. Network access is required for
Gradle, Minecraft, and Fabric dependencies. Builds use Fabric Loom **1.19.3**
and Fabric Loader **0.20.1**, as pinned in `gradle.properties`. Gradle and the
compiler use Java 25; `--release 21` preserves Java 21 APIs and bytecode, and
Minecraft 1.21.11 still runs with Java 21.

```sh
# Linux / macOS
./gradlew --no-daemon clean build
```

```bat
:: Windows Command Prompt
gradlew.bat --no-daemon clean build
:: Or use the convenient entry point:
Build-Windows.bat
```

In PowerShell, prefix these Windows commands with `.\`. `Build-Windows.bat` also
works when invoked by its full path from another directory. The installable output is
`build/libs/third-person-readable-maps-<version>-mc1.21.11.jar` (currently `0.0.2`).
`build/devlibs/` contains development intermediates; install the remapped JAR
from `build/libs/`. Build scripts leave generated files under `build/`.

## Validation and contributions

Open pull requests against `mc/1.21.11`. CI runs clean Java 25 builds on Linux and
Windows, validates the Gradle wrapper, checks Fabric metadata, the packaged MIT
license, Java bytecode, and the Mixin target signature, and uploads the mod JARs
and verification reports. Run the same checks locally with `./gradlew build`.
The dependency job also resolves the Gradle graph and uploads its snapshot;
GitHub's automatic Gradle dependency submission remains the submission source.
Dependabot checks Gradle and GitHub Actions weekly.

Minecraft's Netty, Log4j, and LZ4 libraries come from its version manifest through
Loom. Dependabot can report these libraries but cannot update their versions in
this mod's build file. Keep security alerts enabled; resolving those alerts needs
a compatible upstream Minecraft/library fix and review, rather than arbitrary
dependency overrides in this mod.

For an in-game check, run `./gradlew runClient` (Windows: `.\gradlew.bat runClient`)
on a machine with graphics support. Check a filled map in each hand, both maps,
an occupied opposite hand, and both dominant-arm settings in third-person view.
Also check missing map data, arm movement, and unchanged first-person behavior.
CI's bytecode and artifact checks do not verify visual rendering.

Report bugs in the [issue tracker](https://github.com/skyRolly/third-person-readable-maps/issues),
including Minecraft, Fabric Loader, Java, and mod versions, reproduction steps,
and the relevant client log. Licensed under [MIT](LICENSE).
