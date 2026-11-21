# Third Person Readable Maps

[![CI — coordination](https://github.com/skyRolly/third-person-readable-maps/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/skyRolly/third-person-readable-maps/actions/workflows/ci.yml?query=branch%3Amain)

A client-side Fabric mod that renders filled map contents on maps held in third-person view. Maps follow the holding arm, with layouts for the main hand, off hand, and occupied opposite hand, including left-handed players.

## Minecraft compatibility

Each row has its own maintained source branch and distributable JAR. The listed
Minecraft versions are explicit support targets, not promises for all versions
in a release family. The current coordinated mod version is `1.0.0`; its
branch updates are proposed for review and it has not been published as a
coordinated GitHub Release.

| Minecraft | Source branch | Java to play | Fabric Loader | Artifact |
| --- | --- | --- | --- | --- |
| 1.21.11 | [`mc/1.21.11`](https://github.com/skyRolly/third-person-readable-maps/tree/mc/1.21.11) | 21+ | 0.20.1+ | One intermediary/remapped JAR |
| 26.1, 26.1.1, 26.1.2, 26.2 | [`mc/26.1-26.2`](https://github.com/skyRolly/third-person-readable-maps/tree/mc/26.1-26.2) | 25+ | 0.20.1+ | One shared official-name JAR |
| 26.3 | [`mc/26.3`](https://github.com/skyRolly/third-person-readable-maps/tree/mc/26.3) | 25+ | 0.20.1+ | A separate official-name JAR |

The [compatibility record](docs/compatibility.md) describes the API boundaries,
static checks and installed-client tests. Further graphical testing remains a
release gate. Install only the JAR matching your game version in the client
instance's `mods` directory; map contents require the client to have received
the map data. Fabric API is not required; the server does not need the mod.

The [legacy inventory](docs/legacy-version-inventory.md) covers 1.14–1.21.10. Several [draft candidate ports](docs/legacy-group-decisions.md) are under review; they are not yet integrated support or release-ready artifacts. The [review handoff](docs/legacy-review-handoff.md) lists candidate heads, artifacts, evidence and remaining gates.

## Build or contribute

`main` is the coordination branch: it owns documentation, the compatibility
matrix, release plans, authorization, orchestration and validation. It is not
a Minecraft build. Submit game-specific changes to the appropriate `mc/*`
branch; submit shared coordination changes to `main`. Port applicable changes
to every affected maintenance branch in separate reviewed PRs and record any
adaptation or deferral in the release plan.

To build one version, check out its source branch, install JDK 25, set
`JAVA_HOME`, and run:

```sh
git checkout mc/1.21.11   # or mc/26.1-26.2, or mc/26.3
./gradlew --no-daemon clean build
```

On Windows use `gradlew.bat --no-daemon clean build` or `Build-Windows.bat`.
JDK 25 runs Gradle for all groups; the 1.21.11 build targets Java 21 bytecode
and runs on Java 21. The 26.x JARs require Java 25. The distributable is in
`build/libs/` and has `-mc<group>.jar` in its name. The proposed 1.0.0 changes
add `python3 scripts/verify_supported_apis.py --jar build/libs` to each product
branch to check its declared game targets. Each branch's CI retains Linux and
Windows builds and its game-specific checks; CI on `main` validates coordination
tools and workflows.

## Coordinated releases and dependencies

One reviewed `X.X.X` mod version is shared across all branches. A reviewed
plan pins each source commit and runtime evidence. One annotated tag without a
`v` prefix identifies the approved `main` coordination commit, and one GitHub
Release contains one JAR per admitted group, a provenance manifest and
checksums. Three groups are integrated today; the ten legacy candidates require
review and release admission before they can be included. The
[release guide](docs/releasing.md) describes required branch protections, CI,
independent approvals, runtime testing and dry runs. No release is automatic.

Dependabot version updates cover Gradle and Actions on all three maintenance
branches and Actions on `main`. Default-branch Dependabot alerts do not give
equivalent security coverage for non-default branches. A separate proposed
candidate audit fails on every unreviewed match. The [monitoring record](docs/dependency-monitoring.md)
explains actual coverage and the [advisory ledger](docs/security-advisories.md)
records unresolved findings.
The [1.0.0 release-readiness matrix](docs/release-readiness-1.0.0.md) and
[administrative controls](docs/administrative-controls.md) identify outstanding
protection, approval, credential and automatic-submission requirements.

Report bugs with the Minecraft, Fabric Loader, Java and mod versions, steps to
reproduce and the relevant client log. Licensed under [MIT](LICENSE).
