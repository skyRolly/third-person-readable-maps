# Legacy compatibility-group decisions

These are candidate decisions, not proof that the final minimum partition or
complete support has been established. The release configuration remains
restricted to the three integrated groups until a port has the required
runtime, review, security and administrative evidence.

| Candidate | Explicit versions | Shared JAR / API evidence | Runtime evidence | Decision |
|---|---|---|---|---|
| 1.21.9–1.21.10 | 1.21.9, 1.21.10 | One candidate; descriptors and all referenced game classes/members checked on both clients | Both local worlds and partial map smoke | Draft [#13](https://github.com/skyRolly/third-person-readable-maps/pull/13); full acceptance pending |
| 1.21.4–1.21.8 | 1.21.4, 1.21.5, 1.21.6, 1.21.7, 1.21.8 | One candidate; descriptors, game and JOML references checked on all five | All five local worlds and partial map smoke | Draft [#14](https://github.com/skyRolly/third-person-readable-maps/pull/14); full acceptance pending |
| 1.21.2–1.21.3 | 1.21.2, 1.21.3 | One candidate; descriptors, game and JOML references checked on both | Both local worlds and partial map smoke | Draft [#16](https://github.com/skyRolly/third-person-readable-maps/pull/16); full acceptance pending |
| 1.21–1.21.1 | 1.21, 1.21.1 | One candidate; descriptors, game and JOML references checked on both | Both local worlds and partial map smoke | Draft [#17](https://github.com/skyRolly/third-person-readable-maps/pull/17); full acceptance pending |
| 1.20.5–1.20.6 | 1.20.5, 1.20.6 | One candidate; descriptors, game and JOML references checked on both | Both local worlds and partial map smoke | Draft [#18](https://github.com/skyRolly/third-person-readable-maps/pull/18); full acceptance pending |
| 1.19.4–1.20.4 | 1.19.4, 1.20, 1.20.1, 1.20.2, 1.20.3, 1.20.4 | One Java 17 candidate; descriptors, game and JOML references checked on all six | All six local worlds and partial map smoke | Draft [#19](https://github.com/skyRolly/third-person-readable-maps/pull/19); full acceptance pending |
| 1.19.3 | 1.19.3 | Java 17; Mixin, game and JOML linkage checked | Local world; main, off and both maps smoke-tested on Java 17 | Draft [#22](https://github.com/skyRolly/third-person-readable-maps/pull/22); full acceptance pending |
| 1.17–1.19.2 | 1.17, 1.17.1, 1.18, 1.18.1, 1.18.2, 1.19, 1.19.1, 1.19.2 | One Java 16 candidate; descriptors and game linkage checked on all eight | 1.17 and 1.19.2 local worlds; main, off and both maps smoke-tested; other versions NOT RUN | Draft [#20](https://github.com/skyRolly/third-person-readable-maps/pull/20); 1.18+ itself requires Java 17 |
| 1.15–1.16.5 | 1.15, 1.15.1, 1.15.2, 1.16, 1.16.1, 1.16.2, 1.16.3, 1.16.4, 1.16.5 | One Java 8 candidate; descriptors and game linkage checked on all nine | 1.15 and 1.16.5 local worlds and partial map smoke on Java 8; other versions NOT RUN | Draft [#21](https://github.com/skyRolly/third-person-readable-maps/pull/21); full acceptance pending |
| 1.14–1.14.4 | 1.14, 1.14.1, 1.14.2, 1.14.3, 1.14.4 | One Java 8 candidate; older four-argument arm descriptor, immediate GL path and game linkage checked on all five; Yarn mappings | 1.14.4 local world and partial map smoke on Java 8; other versions NOT RUN | Draft [#23](https://github.com/skyRolly/third-person-readable-maps/pull/23); full visual and OpenGL-state acceptance pending |

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
