# Legacy compatibility-group decisions

These are candidate decisions, not an assertion that the mathematically
smallest partition or complete support has been established. Release
configuration remains restricted to the three integrated groups until a port
has the necessary runtime, review, and dependency-audit evidence.

| Candidate | Versions | Shared JAR | API evidence | Runtime evidence | Decision |
|---|---|---|---|---|---|
| 1.21.9–1.21.10 | 1.21.9, 1.21.10 | One candidate, identical SHA-256 | 2 Mixin descriptors, 27 classes and 39 references resolve on each official client | Installed local worlds and partial graphics on both | Draft [PR #13](https://github.com/skyRolly/third-person-readable-maps/pull/13); human acceptance and security integration remain |
| 1.21.4–1.21.8 | 1.21.4–1.21.8 | One candidate, identical SHA-256 | 2 Mixin descriptors, 28 classes, 44 game and 2 JOML references checked on each client | Local world and partial main-hand terrain smoke on all five | Draft [PR #14](https://github.com/skyRolly/third-person-readable-maps/pull/14); full runtime and human acceptance remain |
| 1.21.2–1.21.3 | 1.21.2, 1.21.3 | Undetermined | Mapping excerpts show a render-state method with an ItemStack and baked model | NOT RUN | Unverified |
| 1.20.5–1.21.1 | 1.20.5, 1.20.6, 1.21, 1.21.1 | Undetermined | Mapping excerpts show an entity/ItemStack arm signature; component and map APIs also need comparison | NOT RUN | Investigate together; no split accepted |
| 1.19.4–1.20.4 | 1.19.4 and 1.20–1.20.4 stable patches | Undetermined | Similar mapped arm signatures do not establish stable intermediary references | NOT RUN | Investigate a Java 17 artifact and potential adjacent consolidation |
| 1.15–1.19.3 | All stable releases in those families | Undetermined | Many arm descriptors resemble one another, but map, model and runtime APIs changed | NOT RUN | Investigate Java and mapping boundaries before partitioning |
| 1.14.x | 1.14–1.14.4 | Undetermined | 1.14.4 mappings show a different arm descriptor; 1.14–1.14.3 require Yarn | NOT RUN | Investigate independently |

The 1.21.9 candidate is incompatible with neighboring 1.21.8 and 1.21.11
without adaptation: the checked Mixin descriptors differ, and Fabric Loader
rejects 1.21.8 through explicit metadata. That is evidence against using the
current unchanged candidate across the boundary, not proof no maintainable
future shared implementation exists. The immediate-buffer/submit boundary is
similarly a reason to test a split, not proof that all possible shared JARs are
impossible. Each additional group adds a maintained branch, Linux and Windows
builds, runtime acceptance per version, OSV inventory, and a release artifact.
No savings from a hypothetical consolidation justify omitting those checks.

The [version inventory](legacy-version-inventory.md) covers all 42 targeted
stable releases. Pre-1.14 samples are not listed in Fabric game/intermediary
metadata and are outside this target, not claimed unsupported by every possible
third-party loader.

The first 1.21.4-built candidate failed on 1.21.5–1.21.8 because quaternion and component getter JVM signatures changed. The revised candidate rotates both matrices as vanilla does and accesses the map ID via typed-component iteration. It passes per-client linkage checks; the alternative still requires complete installed-client and graphical testing before the group is accepted.
