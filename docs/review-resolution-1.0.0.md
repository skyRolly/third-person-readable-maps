# 1.0.0 cross-branch review resolution

This records the 2026-11-12 proposed heads and later diagnostic evidence. **A** means confirmed affected;
**D** means a different implementation whose equivalent invariant must still
be verified; **N** means the specific mechanism is not present, with the
evidence stated below. None of these labels is release acceptance.
The [source-head transition](source-head-transition-2026-11-13.md) identifies
the subsequent verifier-only product commits and the evidence requiring refresh.

| Group | Ordinary member linkage (#13, #16, #18) | Game/math/library coverage (#20) | Texture state (#23) | Missing map identity (#23) |
|---|---|---|---|---|
| 1.14–1.14.4 | A: old name/descriptor lookup omitted operation staticness | D: previous verifier separately checked LWJGL; current verifier checks actual operations and metadata-pinned libraries | A: direct texture bind changed incoming binding; corrected and probed on 1.14 | A: absent identity fell back to zero; invalid numeric tags also coerced to other IDs. Bounded numeric guard added. |
| 1.15–1.16.5 | A: same lookup defect | D: no direct JOML/LWJGL references in this packaged JAR; game classes checked | N: buffered render types, no direct equivalent GL bind or lighting toggle; state contract still requires gameplay review | A: same absent-ID fallback and malformed numeric coercion; bounded numeric guard added. |
| 1.17–1.19.2 | A: same lookup defect | D: packaged legacy Mojang vector/quaternion classes are intermediary `net/minecraft/class_1158` etc., which the old game-class filter included; operation and descriptor coverage still strengthened | N: buffered renderer, no direct equivalent GL bind or lighting toggle; gameplay review remains | A: absent identity returns null, but numeric coercion can select an unrelated ID; bounded numeric guard added. |
| 1.19.3 | A: same lookup defect | A: old JOML member scan did not establish descriptor-only class existence | N: buffered renderer; gameplay state ownership remains to be tested | A: `getMapId` reads any numeric tag through `getInt`; bounded numeric guard added. |
| 1.19.4–1.20.4 | A: same lookup defect | A: old JOML member scan did not establish descriptor-only class existence | N: buffered renderer; gameplay state ownership remains to be tested | A: same numeric coercion in inspected game bytecode; bounded numeric guard added. |
| 1.20.5–1.20.6 | A: same lookup defect | A: old JOML member scan did not establish descriptor-only class existence | N: buffered renderer; gameplay state ownership remains to be tested | A at the game-codec boundary for both versions: malformed numbers can become zero before the renderer sees the component; item-loading behavior and remedy remain open. |
| 1.21–1.21.1 | A: same lookup defect | A: old JOML member scan did not establish descriptor-only class existence | N: buffered renderer; gameplay state ownership remains to be tested | A at the game-codec boundary for both versions; item-loading behavior and remedy remain open. |
| 1.21.2–1.21.3 | A: same lookup defect | A: old JOML member scan did not establish descriptor-only class existence | N: buffered renderer; gameplay state ownership remains to be tested | A at the game-codec boundary for both versions; item-loading behavior and remedy remain open. |
| 1.21.4–1.21.8 | A: same lookup defect | A: old JOML member scan did not establish descriptor-only class existence | N: buffered renderer; gameplay state ownership remains to be tested | A at the game-codec boundary for all five versions; item-loading behavior and remedy remain open. |
| 1.21.9–1.21.10 | A: same lookup defect | A: packaged JOML descriptor classes had no separate JOML verification | N: queued renderer; gameplay state ownership remains to be tested | A at the game-codec boundary for both versions; item-loading behavior and remedy remain open. |
| 1.21.11 | D: singleton had Gradle compile checks but no independent packaged-JAR linkage verifier; added one | D: JOML descriptor classes now checked against declared runtime library | N: queued renderer; gameplay state ownership remains to be tested | A: a controlled [actual item-loading probe](component-map-id-item-loading-2026-11-13/host-inventory-attempt/) observed malformed numeric IDs become zero and map-zero terrain displayed; bounded remedy remains open. |
| 26.1–26.2 | A: official-namespace verifier also resolved ordinary members by kind/name/descriptor | A: `com/mojang/math/Axis` and JOML descriptor classes require explicit game/library resolution | N: queued renderer; gameplay state ownership remains to be tested | A at the game-codec boundary for all four versions; item-loading behavior and remedy remain open. |
| 26.3 | D: singleton had Gradle compile checks but no independent packaged-JAR linkage verifier; added one | D: official game supplies `com/mojang/math/Axis`; now verified in packaged references | N: queued renderer; gameplay state ownership remains to be tested | A at the game-codec boundary; item-loading behavior and remedy remain open. |

The old resolver's success on a static-to-instance fixture is explicitly
reproduced in `tests/test_jvm_linkage.py`; the current check rejects it. The
16 fixtures also exercise access, inherited public and protected members,
interfaces, constructors, method handles, missing descriptor classes,
libraries, Mixin target staticness and supported injection points, plus Java
8/16/17/21/25 class files. All 13 proposed artifacts passed their actual
version-specific game and dependency checks; nine [adjacent-version negative
controls](negative-verifier-followup-2026-11-13/) were rerun against the
advanced source heads and rebuilt artifacts, and rejected for missing targets,
classes or members. Each product branch records its digest.

The resolver uses the actual consuming instructions and mapped names, and
checks exact Minecraft client and game-library artifacts against Mojang metadata.
It accounts for the target class when validating transformed Mixin references.
The latest product PR heads also check access to classes consumed by bytecode
class instructions and class constants, and reject abstract instantiation and
constructor handles. A controlled fixture distinguishes this from the previous
presence-only check; a prototype passed on all 48 previously built artifacts.
Unsupported Mixin annotations and injection points fail closed. Java platform
APIs and Mixin callback internals rely on the compiler `--release` target and
declared Fabric/Mixin build dependencies. This is not a complete JVM verifier:
protected receiver dataflow, all `invokespecial` selection cases, access to
classes referenced only by descriptors, final-field write
restrictions, complex transformation semantics and arbitrary runtime-generated
linkage remain outside the proven scope. The current [artifact inventory](dependency-evidence/high-advisories-2026-11-12/mod-class-reference-inventory.json)
found no `putfield` or `putstatic` instructions targeting external owners in
the 13 packaged JARs; unsupported Mixin member annotations, including shadow
fields, fail closed. A [fresh exact-artifact inventory](artifact-linkage-inventory-2026-11-13/)
also found no external or inherited non-constructor `invokespecial` in these
13 JARs. A separate [archived-source trace](protected-access-trace-2026-11-14/)
found no protected game or game-library member resolutions on any of the 48
versions under this verifier's resolution model. These observations do not extend the verifier to future artifacts or
prove accessibility for descriptor-only classes. These limits must not be read as
complete linkage proof.

The 1.14 state fix restores the previous active texture unit and bound texture
through Minecraft's state manager, and restores the previous lighting state in
`finally`. [Controlled before/after probes](https://github.com/skyRolly/third-person-readable-maps/blob/341d33664272c2a19aa419e3d33f01b1954df991/docs/verification/1.0.0-final-mapid-state-probe.md)
cover eight calls in each of two seeded-state runs on software rendering, not
all hands, exception paths, subsequent entities or hardware GPUs. The early
map-ID guards preserve numeric integral IDs, including an explicit zero, while
rejecting absent, nonnumeric, fractional, non-finite and out-of-range identity.
Controlled before/after tests on the prior source heads' 1.0.0 artifacts cover [1.14](https://github.com/skyRolly/third-person-readable-maps/blob/341d33664272c2a19aa419e3d33f01b1954df991/docs/verification/1.0.0-final-mapid-state-probe.md),
[1.15](https://github.com/skyRolly/third-person-readable-maps/blob/7bf2ae372fac4d6e478f3a523db963886e05900f/docs/verification/1.0.0-numeric-mapid-probe.md),
[1.17](https://github.com/skyRolly/third-person-readable-maps/blob/96060a2c1c5267eae102f24cf3a78d6646d4dbce/docs/verification/1.0.0-numeric-mapid-probe.md),
[1.19.3](https://github.com/skyRolly/third-person-readable-maps/blob/c3ac7d261b4289451c8b27df96fae7a316ba75ed/docs/verification/1.0.0-numeric-mapid-probe.md), and
[1.19.4](https://github.com/skyRolly/third-person-readable-maps/blob/4c78b44bd8ac1a758f3c04987530b9fda844127b/docs/verification/1.0.0-numeric-mapid-probe.md).
Each used a local single-player software-rendered scene; no diagnostic proves
naturally delayed client data in multiplayer. A later [1.21.11 two-client LAN
observation](multiplayer-smoke-2026-11-14/) captured the remote map blank before
the observer held the same map ID and with terrain afterward. Its client cache
was not instrumented, so it does not establish the cause of the initial blank
or close the naturally unavailable-data requirement.

For the component-based 1.20.5 family, inspection of the SHA-1-verified
1.20.5 client (`c6b92b2374a629f20802bb284f98a4ee790e950a`) shows `MapId`
stores an `int` and constructs its codec with `Codec.INT.xmap`. The runtime's
DataFixerUpper 7.0.14 (Mojang SHA-1 `db3485dc1e6b712bd81170d5ce6dca2fb2f8bd86`)
`Codec.INT` reads a numeric value and applies
`Number.intValue`; `NbtOps` accepts numeric tags. Thus a malformed fractional
or out-of-range serialized value can already be coerced before this mod sees
the typed component. Once that happens, a resulting zero is indistinguishable
from an explicit valid map-zero component inside the renderer. The renderer
checks a missing component and does not create data, but it cannot reconstruct
the original serialized type. Changing game-wide component decoding would
affect other behavior and needs a separately reviewed design and runtime tests;
it is not claimed fixed by the NBT-era guard. A separate [controlled codec
probe](dependency-evidence/component-mapid-codec-2026-11-12/) used the actual
SHA-1-verified 1.21.11 and 26.1.2 client classes and their metadata-selected
DataFixerUpper 9.0.19. On Java 25, explicit integer zero and seven decoded to
zero and seven; double 0.5, long 4294967296 and double NaN each decoded to zero;
a string was rejected. A later [19-version codec sweep](dependency-evidence/component-mapid-codec-2026-11-13/)
executed the exact game's codec on every component-era version in the proposed
matrix and observed the same results. A later [controlled 1.21.11 host-world
probe](component-map-id-item-loading-2026-11-13/host-inventory-attempt/)
observed the fractional and overflowing input values load and save as zero,
with terrain shown while the fractional item was selected. The isolated codec
sweep does not prove the other versions' complete item-loading or rendering
paths. A bounded remedy and those remaining paths need review before closing
this case.

The old large foreground shape was not reproduced in one 1.21.4 candidate and
no-mod comparison. Its cause remains **inconclusive**; repeat matched captures
with the same game, world, camera, perspective, pose, motion, renderer and frame
timing. A later [1.20.6 candidate/no-mod comparison](foreground-comparison-1.20.6-2026-11-13/)
did not show the large shape in four walking frames, but the runs were not
frame-synchronized and did not reproduce the original viewpoint. Additional
[1.21.1, 1.21.5 and 1.21.10 comparisons](foreground-comparisons-2026-11-13/)
also did not show the large historical shape in their limited frames. Small
green and dark-green objects were seen in both candidate and no-mod runs, but
the runs were not synchronized and their identity and relationship to the
original shape were unknown. A later [1.21.11 dropped-item control](foreground-item-entities-2026-11-13/)
removed particular small shapes after clearing item entities in candidate and
no-Mod scenes; its nearest queried item was wheat seeds. It did not reproduce
the original large shape, whose cause remains **inconclusive**. Repeat each
original observation with matched conditions and investigate any repeatable
candidate/no-mod difference. Full graphical acceptance is still required on
the new artifacts.

Coordination PR #15 previously added update targets for branches containing the
1.21.11 placeholder. The proposed configuration now targets only the three
integrated groups and `main`; a separate registry, source metadata and remote
ancestry checks gate later activation. Candidate audit transitions retain exact
source pins and unreviewed historical advisory records. A merged, automatically
deleted candidate may temporarily remain scanned only under the exact-tree
checks in `verify_candidate_source.py`; this remains candidate evidence.
The maintenance audit's observed 105 unresolved matches correctly failed, but
a separate absent-advisory comparison defect was also corrected: disappearance
now requires explicit source- and inventory-bound resolution review before the
gate can pass. See the [security review](security-review-2026-11-12.md).
