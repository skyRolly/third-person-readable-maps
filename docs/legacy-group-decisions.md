# Legacy compatibility-group decisions

These are candidate decisions, not proof that the final minimum partition or
complete support has been established. The release configuration remains
restricted to the three integrated groups until a port has the required
runtime, review, security and administrative evidence.

| Candidate | Explicit versions | Shared JAR / API evidence | Runtime evidence | Decision |
|---|---|---|---|---|
| 1.21.9–1.21.10 | 1.21.9, 1.21.10 | One candidate; descriptors and all referenced game classes/members checked on both clients | All clients joined local worlds; main, off and both maps smoke-tested; both also have left/stone/missing-data and first-person comparisons; full acceptance outstanding | Draft [#13](https://github.com/skyRolly/third-person-readable-maps/pull/13); full acceptance pending |
| 1.21.4–1.21.8 | 1.21.4, 1.21.5, 1.21.6, 1.21.7, 1.21.8 | One candidate; descriptors, game and JOML references checked on all five | All clients joined local worlds; main, off and both maps smoke-tested; all five also have left/stone/missing-data and first-person comparisons; full acceptance outstanding | Draft [#14](https://github.com/skyRolly/third-person-readable-maps/pull/14); full acceptance pending |
| 1.21.2–1.21.3 | 1.21.2, 1.21.3 | One candidate; descriptors, game and JOML references checked on both | All clients joined local worlds; main, off and both maps smoke-tested; both also have left/stone/missing-data and first-person comparisons; full acceptance outstanding | Draft [#16](https://github.com/skyRolly/third-person-readable-maps/pull/16); full acceptance pending |
| 1.21–1.21.1 | 1.21, 1.21.1 | One candidate; descriptors, game and JOML references checked on both | All clients joined local worlds; main, off and both maps smoke-tested; both also have left/stone/missing-data and first-person comparisons; full acceptance outstanding | Draft [#17](https://github.com/skyRolly/third-person-readable-maps/pull/17); full acceptance pending |
| 1.20.5–1.20.6 | 1.20.5, 1.20.6 | One candidate; descriptors, game and JOML references checked on both | All clients joined local worlds; main, off and both maps smoke-tested; both also have left/stone/missing-data and first-person comparisons; full acceptance outstanding | Draft [#18](https://github.com/skyRolly/third-person-readable-maps/pull/18); full acceptance pending |
| 1.19.4–1.20.4 | 1.19.4, 1.20, 1.20.1, 1.20.2, 1.20.3, 1.20.4 | One Java 17 candidate; descriptors, game and JOML references checked on all six | All clients joined local worlds; main, off and both maps smoke-tested; all also have left/stone/missing-data and first-person comparisons; full acceptance outstanding | Draft [#19](https://github.com/skyRolly/third-person-readable-maps/pull/19); full acceptance pending |
| 1.19.3 | 1.19.3 | Java 17; Mixin, game and JOML linkage checked | Local world; main/off/both maps, left-hand and opposite stone, missing data and controlled first-person comparison smoke-tested on Java 17 | Draft [#22](https://github.com/skyRolly/third-person-readable-maps/pull/22); full acceptance pending |
| 1.17–1.19.2 | 1.17, 1.17.1, 1.18, 1.18.1, 1.18.2, 1.19, 1.19.1, 1.19.2 | One Java 16 candidate; descriptors and game linkage checked on all eight | All clients joined local worlds; main, off and both maps smoke-tested; 1.17, 1.17.1 also have left/stone, untagged-map and first-person comparison evidence; see per-version results for inconclusive comparisons; missing-data null path and full acceptance outstanding | Draft [#20](https://github.com/skyRolly/third-person-readable-maps/pull/20); 1.18+ itself requires Java 17 |
| 1.15–1.16.5 | 1.15, 1.15.1, 1.15.2, 1.16, 1.16.1, 1.16.2, 1.16.3, 1.16.4, 1.16.5 | One Java 8 candidate; descriptors and game linkage checked on all nine | All clients joined local worlds; main, off and both maps smoke-tested; all also have left/stone, untagged-map and first-person comparison evidence; see per-version results for inconclusive comparisons; missing-data null path and full acceptance outstanding | Draft [#21](https://github.com/skyRolly/third-person-readable-maps/pull/21); full acceptance pending |
| 1.14–1.14.4 | 1.14, 1.14.1, 1.14.2, 1.14.3, 1.14.4 | One Java 8 candidate; required Mixin, game references and all declared LWJGL OpenGL variants checked on all five | Revised JAR lighting-state probe passed; ordinary right/left hand smoke and first-person comparisons recorded on 5/5 versions; see evidence for inconclusive comparisons; forced-null diagnostic 2/5 versions; ordinary missing-data cases and full acceptance outstanding | Draft [#23](https://github.com/skyRolly/third-person-readable-maps/pull/23); full visual and OpenGL-state acceptance pending |

The 1.21.9 JAR fails descriptor checks on adjacent 1.21.8 and 1.21.11, and
Fabric Loader rejects it on 1.21.8. The 1.21.2–1.21.3 JAR fails the 1.21.4
Mixin descriptor check. The 1.21–1.21.1 JAR fails resource-location and
vertex-consumer references on 1.20.6. The 1.19.4–1.20.4 JAR fails map-ID and
renderer references on 1.20.5. The 1.19.3 JAR fails linkage on 1.19.2 and its Mixin descriptor on 1.19.4; the 1.17–1.19.2 JAR lacks old quaternion/vector classes on 1.19.3. The 1.15–1.16.5 JAR fails its 1.14.4 Mixin descriptor and game references on 1.17. The 1.14–1.14.4 JAR fails its Mixin descriptor on 1.15. These results reject the **unchanged candidate
JARs** across those boundaries; they do not prove that every possible future
shared implementation is impossible.

The first 1.21.4-built JAR failed on 1.21.5–1.21.8 because quaternion and
component-getter JVM signatures changed. The revised candidate rotates both
matrices as vanilla does and accesses the map ID via typed-component iteration.
It passes per-client linkage checks and partial installed-client smoke tests;
complete hand, movement, multiplayer and independent human testing remain.
Every additional group adds a maintained branch, Linux and Windows builds,
per-version runtime acceptance, OSV inventory, and release artifact. No
hypothetical consolidation justifies skipping those checks.

The [inventory](legacy-version-inventory.md) covers all 42 targeted stable
releases. Pre-1.14 samples are not listed in Fabric game/intermediary metadata
and are outside this target; this does not characterize every third-party
loader.

## Partition and alternatives

The present proposal uses **10 new candidate JARs and maintenance groups** for
42 historical versions, plus the three existing groups. All 42 have static
linkage checks; installed-client smoke coverage is listed per version in the
[inventory](legacy-version-inventory.md). None of these partial smoke tests is
full release acceptance. Each additional group costs one branch, two platform
builds, a dependency inventory and a release artifact.

A branch per major version would miss the observed splits inside 1.19 and 1.21
and would unnecessarily separate the currently shared 1.15–1.16.5 and
1.17–1.19.2 ranges. Reusing an unchanged neighboring candidate across the
boundaries above fails the recorded checks. A single artifact containing several
conditionally selected, still-required implementations could be investigated
later, but its build/remapping, selection and per-version runtime behavior have
not been demonstrated here. It is not ruled out as impossible, and reducing the
count would require testing the *same resulting JAR* on every declared version
without optional or silently failing injections. The current partition is the
smallest established by the implemented candidates and evidence, not a proof of
a global minimum.
