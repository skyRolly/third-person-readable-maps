# 1.0.0 cross-branch review resolution

This records the 2026-11-12 proposed heads. **A** means confirmed affected;
**D** means a different implementation whose equivalent invariant must still
be verified; **N** means the specific mechanism is not present, with the
evidence stated below. None of these labels is release acceptance.

| Group | Ordinary member linkage (#13, #16, #18) | Game/math/library coverage (#20) | Texture state (#23) | Missing map identity (#23) |
|---|---|---|---|---|
| 1.14–1.14.4 | A: old name/descriptor lookup omitted operation staticness | D: previous verifier separately checked LWJGL; current verifier checks actual operations and metadata-pinned libraries | A: direct texture bind changed incoming binding; corrected and probed on 1.14 | A: game lookup treated absent/non-numeric identity as zero; guard and 1.14 probe |
| 1.15–1.16.5 | A: same lookup defect | D: no direct JOML/LWJGL references in this packaged JAR; game classes checked | N: buffered render types, no direct equivalent GL bind or lighting toggle; state contract still requires gameplay review | A: same fallback in the 1.15 API; guard and 1.15 probe |
| 1.17–1.19.2 | A: same lookup defect | D: packaged legacy Mojang vector/quaternion classes are intermediary `net/minecraft/class_1158` etc., which the old game-class filter included; operation and descriptor coverage still strengthened | N: buffered renderer, no direct equivalent GL bind or lighting toggle; gameplay review remains | D: representative game `getMapId`/`getSavedData` returns null for absent identity; verify full runtime matrix |
| 1.19.3 | A: same lookup defect | A: old JOML member scan did not establish descriptor-only class existence | N: buffered renderer; gameplay state ownership remains to be tested | D: representative NBT API null-checks identity; verify full runtime matrix |
| 1.19.4–1.20.4 | A: same lookup defect | A: old JOML member scan did not establish descriptor-only class existence | N: buffered renderer; gameplay state ownership remains to be tested | D: representative NBT API null-checks identity; verify full runtime matrix |
| 1.20.5–1.20.6 | A: same lookup defect | A: old JOML member scan did not establish descriptor-only class existence | N: buffered renderer; gameplay state ownership remains to be tested | D: map identity is a nullable data component; verify full runtime matrix |
| 1.21–1.21.1 | A: same lookup defect | A: old JOML member scan did not establish descriptor-only class existence | N: buffered renderer; gameplay state ownership remains to be tested | D: nullable map-ID component; verify full runtime matrix |
| 1.21.2–1.21.3 | A: same lookup defect | A: old JOML member scan did not establish descriptor-only class existence | N: buffered renderer; gameplay state ownership remains to be tested | D: nullable map-ID component; verify full runtime matrix |
| 1.21.4–1.21.8 | A: same lookup defect | A: old JOML member scan did not establish descriptor-only class existence | N: buffered renderer; gameplay state ownership remains to be tested | D: nullable map-ID component; verify full runtime matrix |
| 1.21.9–1.21.10 | A: same lookup defect | A: packaged JOML descriptor classes had no separate JOML verification | N: queued renderer; gameplay state ownership remains to be tested | D: nullable map-ID component; verify full runtime matrix |
| 1.21.11 | D: singleton had Gradle compile checks but no independent packaged-JAR linkage verifier; added one | D: JOML descriptor classes now checked against declared runtime library | N: queued renderer; gameplay state ownership remains to be tested | D: nullable map-ID component; verify full runtime matrix |
| 26.1–26.2 | A: official-namespace verifier also resolved ordinary members by kind/name/descriptor | A: `com/mojang/math/Axis` and JOML descriptor classes require explicit game/library resolution | N: queued renderer; gameplay state ownership remains to be tested | D: nullable map-ID component; verify full runtime matrix |
| 26.3 | D: singleton had Gradle compile checks but no independent packaged-JAR linkage verifier; added one | D: official game supplies `com/mojang/math/Axis`; now verified in packaged references | N: queued renderer; gameplay state ownership remains to be tested | D: nullable map-ID component; verify full runtime matrix |

The old resolver's success on a static-to-instance fixture is explicitly
reproduced in `tests/test_jvm_linkage.py`; the current check rejects it. The
15 fixtures also exercise access, inherited public and protected members,
interfaces, constructors, method handles, missing descriptor classes,
libraries, Mixin target staticness and supported injection points, plus Java
8/16/17/21/25 class files. All 13 proposed artifacts passed their actual
version-specific game and dependency checks; nine historical adjacent-version
negative controls were rerun against the new artifacts and rejected for
missing targets, classes or members. Each product branch records its digest.

The resolver uses the actual consuming instructions and mapped names, and
checks exact Minecraft client and game-library artifacts against Mojang metadata.
It accounts for the target class when validating transformed Mixin references.
Unsupported Mixin annotations and injection points fail closed. Java platform
APIs and Mixin callback internals rely on the compiler `--release` target and
declared Fabric/Mixin build dependencies. This is not a complete JVM verifier:
protected receiver dataflow, all `invokespecial` selection cases, complex
transformation semantics and arbitrary runtime-generated linkage remain outside
the proven scope. These limits must not be read as complete linkage proof.

The 1.14 state fix restores the previous active texture unit and bound texture
through Minecraft's state manager, and restores the previous lighting state in
`finally`. [Controlled before/after probes](https://github.com/skyRolly/third-person-readable-maps/blob/83f3a34a5a984d2ac88398465679b7dffd60e20d/docs/verification/1.0.0-state-probe.md)
cover eight calls in each of two seeded-state runs on software rendering, not
all hands, exception paths, subsequent entities or hardware GPUs. The early
map-ID guards preserve an explicitly numeric zero and avoid looking up map zero
for absent, empty or nonnumeric identity. [1.14](https://github.com/skyRolly/third-person-readable-maps/blob/83f3a34a5a984d2ac88398465679b7dffd60e20d/docs/verification/1.0.0-mapid-probe.md)
and [1.15](https://github.com/skyRolly/third-person-readable-maps/blob/f566285f448411f0abc4a61c86a1036300547495/docs/verification/1.0.0-mapid-probe.md)
controlled tests include zero, nonzero, absent, malformed and unavailable IDs.
They do not prove naturally delayed client data in multiplayer.

The old large foreground shape was not reproduced in one 1.21.4 candidate and
no-mod comparison. Its cause remains **inconclusive**; repeat matched captures
with the same game, world, camera, perspective, pose, motion, renderer and frame
timing. Full graphical acceptance is still required on the new artifacts.

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
