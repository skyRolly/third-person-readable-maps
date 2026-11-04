# Third Person Readable Maps

A client-side Fabric mod that renders filled map contents on maps held in
third-person view, including main and off hands, occupied opposite hands and
left-handed players. The server does not need the mod. Fabric API is not needed.

## Minecraft compatibility

The candidates in this repository build separate JARs with a shared mod version:

| Minecraft | Java to play | Fabric Loader | Status |
| --- | --- | --- | --- |
| 1.21.11 | 21+ | 0.20.1+ | Maintenance candidate, intermediary/remapped JAR |
| 26.3 | 25+ | 0.20.1+ | Candidate based on unmerged PR #3, official-name JAR |

These are exact game versions, not claims that the JARs work on a whole release
family. There is no coordinated public release yet. The prior `main` history
contains mod version `0.0.1`; `0.0.2` is proposed for the first coordinated
release and must not be tagged or published until reviewed. See the full
[compatibility decision record](docs/compatibility.md).

## Build this branch

Install **JDK 25**, set `JAVA_HOME` to it, and run:

```sh
./gradlew --no-daemon clean build
python3 -m unittest discover -s tests -v
```

On Windows, use `gradlew.bat --no-daemon clean build` or `Build-Windows.bat`.
The Gradle 9.8.2 wrapper is included. The 1.21.11 branch executes Gradle and
compiles with JDK 25 using `--release 21`: the resulting mod requires Java 21,
not Java 25, to run. The artifact is
`build/libs/third-person-readable-maps-<mod-version>-mc1.21.11.jar`.
The separate 26.3 candidate uses Java 25 for both build and runtime and packages
`third-person-readable-maps-<mod-version>-mc26.3.jar`.

Do not install development intermediates. Copy the exact JAR for your game
version into the client instance's `mods` directory and launch its Fabric
profile. Map contents require the client to have received that map's data.

## Development and releases

Linux and Windows CI build the branch under review, validate the exact Mixin
target and inspect the distributable. Those checks do not replace an installed
client or visual test. The [maintenance and release guide](docs/releasing.md)
describes branch roles, propagation of changes, the single global tag and the
review gates for a coordinated release. No release workflow runs automatically.

Minecraft-managed libraries such as Netty, Log4j, Guava and LZ4 are supplied by
the game, not bundled by this mod. The existing Dependabot security-update
`dependency_not_found` issue and inaccessible alert details remain open; see
the [decision record](docs/compatibility.md#dependency-maintenance).

Report bugs with the Minecraft, Fabric Loader, Java and mod versions, steps to
reproduce and the relevant client log. Licensed under [MIT](LICENSE).
