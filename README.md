# Third Person Readable Maps — Minecraft 26.1–26.2 candidate

This client-side Fabric mod makes filled maps readable while held in
third-person view. This candidate JAR targets **Minecraft 26.1, 26.1.1,
26.1.2 and 26.2**, Java **25+** and Fabric Loader **0.20.1+**. It is not a
26.3 JAR: Minecraft 26.3 removed a pose API used by this implementation.

The port is based on the unmerged modernization PR #3, but is reviewed against
a separate candidate base so accepting it will not replace the 26.3 build. It
is not yet an approved maintenance branch or a published release. Mod version
`0.0.2` is a coordinated release candidate.

## Build

Install JDK 25 (CI pins Temurin 25.0.5+8), then use Gradle 9.8.2 via the
committed wrapper:

```sh
./gradlew --no-daemon clean build
python3 scripts/verify_supported_apis.py --jar build/libs
```

On Windows, use `gradlew.bat --no-daemon clean build` or `Build-Windows.bat`.
The installable artifact is
`build/libs/third-person-readable-maps-<version>-mc26.1-26.2.jar`. Build and
runtime both use Java 25; Fabric Loom 1.19.3 and Loader 0.20.1 are pinned in
`gradle.properties`. Fabric API is not needed.

The API check downloads the four official game client JARs, verifies their
Mojang manifest hashes and checks the exact Mixin target and packaged game
member references in each. It requires Python 3 and network access. It cannot
prove that rendering is correct; use an installed Fabric client for graphical
checks. The same candidate JAR was smoke-tested in each listed game version.
Check both hands, occupied opposite hands, left and right dominant arms, map
data and missing data, motion and first-person rendering before release.

Copy the JAR into the client instance's `mods` directory. Map contents require
the client to have received the relevant map data. The server does not need the
mod. Minecraft-managed libraries are not bundled here; keep security alerts
enabled and track compatible upstream fixes. Licensed under [MIT](LICENSE).
