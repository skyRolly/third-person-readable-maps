# Late review follow-up, 2026-11-16

This worklog is chronological. Earlier investigation-status statements describe their time of observation; the final 2026-11-21 section records the later correction and validation. Current source and release status are in the [handoff](../pr-integration-handoff-1.0.0.md).

After the platform hierarchy and evidence-lifecycle changes had passed their recorded checks, four automated inline review comments appeared on the open proposals. The broader product and coordination PRs were returned to draft while these comments are investigated. The exact prior product heads and their successful checks remain recorded in `version-consistency-1.0.0/current-heads.json` and `current-validation/`; their historical results must not be attributed to later commits.

* [#32 inherited runtime-library resolution](https://github.com/skyRolly/third-person-readable-maps/pull/32#discussion_r4580545542): the adapter's preliminary game-only member scan can reject a game-owned reference whose member is inherited from a metadata-selected runtime library before the composite verifier runs. Preliminary investigation found the scan in all 13 product adapters. Confirm with packaged fixtures and repair without excluding references or weakening access checks.
* [#23 rendering state](https://github.com/skyRolly/third-person-readable-maps/pull/23#discussion_r4580551260): the 1.14 vanilla map renderer changes blend and alpha state, while the current Mod restores texture and lighting only. Verify the actual 1.14 client behavior and restore the incoming state with a targeted runtime diagnostic.
* [#23 map background](https://github.com/skyRolly/third-person-readable-maps/pull/23#discussion_r4580551177): determine whether the 1.14 family actually supplies the proposed checkerboard asset and whether vanilla uses it, before changing the product.
* [#18 historical runtime record](https://github.com/skyRolly/third-person-readable-maps/pull/18#discussion_r4580543832): the branch-local smoke record does not prominently identify its older 0.0.2 artifact. Preserve the original source and digest and distinguish it from later 1.0.0 evidence.

These observations are investigation status, not claims of completed corrections, current-artifact crashes in every group, fresh runtime acceptance, or release approval. The 0.0.2 security-only proposals and Dependabot proposals retain their separate scope. No merge, tag or release action is authorized.

## Findings established during reproduction

The first production-adapter fixture compiled a game-owned subclass of a metadata-selected `org.joml.Api`, compiled a candidate that invokes its inherited method and field, and successfully executed that candidate on the JVM. The prior intermediary and official entry points both rejected it in their game-only constant-pool scan (`missing game members` / `missing game references`). The correction moves the presence scan inside each selected platform classpath and uses the same composite candidate/game/library lookup as instruction validation. Fixtures also replace the library after candidate compilation with missing, static or private methods and fields, and check a platform-specific missing variant; the JVM and verifier reject the invalid examples. Direct platform-owned or platform-inherited members whose declaration cannot be resolved remain subject to the existing documented bounded restriction.

The checkerboard suggestion does not apply to 1.14–1.14.4: [all five exact official client JARs](1.14-official-map-textures-2026-11-16.json) were checked against Mojang metadata size and SHA-1; each contains `map_background.png` and no checkerboard map texture. The 1.14 first-person map renderer binds that background. Introducing a reference to a nonexistent asset would be a regression; this observation does not make claims about later game versions.

The separate 1.14 state concern is real: inspection of the vanilla 1.14 MapRenderer bytecode showed `enableBlend`, `blendFuncSeparate`, `disableAlphaTest`, and subsequent unconditional `enableAlphaTest`/`disableBlend`; decoration drawing also changes current color. The candidate previously restored lighting and texture binding but not those states. A build of the corrective source and an in-game test-only state probe are in progress; the on-disk old artifact remains unchanged. Full graphical, GPU, multiplayer and independent acceptance remain separate requirements.

The #18 smoke record is historical: its source `32164d846089ce67d5c0a10ba351796207312b02`, SHA-256 `8c02fa2fc1b565e8154926642ac4fa260b28f59aeca8a49f9958a8d39050cdfd`, and retained log identify version 0.0.2. Separate later 1.0.0 smoke observations for both versions identify source `c0efb70ad1e01298c96441d18bc68f0b2674d6d6` and artifact `d0d37fb74198d8b930597eb4c615c6e09d43034ae7e1bfe34b6b12c4583c190a`. The branch record now identifies the historical version without rewriting either source identity.

## Correction heads and state diagnostic

The 13 existing product PR branches were updated in place and kept in draft during verification. The exact source heads are recorded in [current-heads.json](../version-consistency-1.0.0/current-heads.json); current build and hosted-check claims remain pending until refreshed. No release or merge action occurred.

The [1.14 controlled probe](1.14-state-regression-2026-11-16/result.json) ran eight draws per artifact in an installed 1.14 local world on an Xorg dummy display with Mesa software rendering. The old artifact changed all four seeded blend/alpha/factor/color values; the corrected preview preserved them, along with texture unit, binding and lighting. The probe was a test-only Mixin loaded beside the unchanged on-disk artifacts. This is a targeted diagnostic, not full graphical, hardware-GPU, multiplayer or independent acceptance. The corrected preview SHA-256 matches the independently clean-built artifact from proposed source `290e9f9bba2d15d9f0c907cdae40ce9706381b2e`; the execution itself used the preview bytes.

## 2026-11-21 dependency and workflow refresh

The seven earlier Dependabot PRs #24–#30 have closed without merging and have been replaced by open #37–#43. #37–#40 pin `actions/setup-java` 6.3.0 at `d1374f8ac74474200d16ef8ecee22c7ae7a51880`, matching the upstream tag. #41–#43 propose Gradle 9.9.1; each proposed Wrapper JAR and distribution checksum matched Gradle's published checksums under the canonical preflight. Their successful checks apply to the older 0.0.2 bases, not the future security/product integration trees.

Gradle subsequently published 9.9.2 and upstream advisories including critical [GHSA-3cfg-jpcr-gfp3](https://github.com/gradle/gradle/security/advisories/GHSA-3cfg-jpcr-gfp3) and high [GHSA-gqrr-4j89-5267](https://github.com/gradle/gradle/security/advisories/GHSA-gqrr-4j89-5267), both affecting 9.8.2 and fixed in 9.9.1, plus high advisories [GHSA-99wf-vhq9-wm2x](https://github.com/gradle/gradle/security/advisories/GHSA-99wf-vhq9-wm2x), [GHSA-7f7r-77ff-fr6f](https://github.com/gradle/gradle/security/advisories/GHSA-7f7r-77ff-fr6f), [GHSA-4mf6-7pm2-6wm8](https://github.com/gradle/gradle/security/advisories/GHSA-4mf6-7pm2-6wm8) and [GHSA-35pj-rg5r-8rpv](https://github.com/gradle/gradle/security/advisories/GHSA-35pj-rg5r-8rpv), affecting 9.9.1 and fixed in 9.9.2. All 13 proposed product Wrappers are at 9.8.2. Static inspection of their tracked Gradle configuration found no declared version catalogs, project-set daemon-registry path, SFTP repository or explicit TestKit runner; plugin/runtime behavior and any untrusted source still require separate consideration. No exploitation or accepted risk is inferred. The existing OSV query for `pkg:maven/org.gradle/gradle-core@9.8.2` returned no advisories on 2026-11-21 despite the upstream records, so the retained scanner results do not establish that these advisories are absent. The fixed 9.9.2 toolchain is undergoing isolated compatibility testing before any update decision.

The newer [scheduled maintenance audit run 43879250114](https://github.com/skyRolly/third-person-readable-maps/actions/runs/43879250114) initially completed the 1.21.11 and 26.3 scans with 41 and 11 unresolved findings, while the 26.1–26.2 snapshot was incomplete after Maven Central returned HTTP 403 during Gradle resolution. A targeted retry of that job completed at source `453cf35695cf07be4072f77895cdbafbed617870` and reported 53 known unresolved findings; the security gate remains failed. The earlier 403 is retained as an incomplete infrastructure attempt, not a completed passing or failing advisory scan.

The proposed coordinator now includes a separate source-bound upstream Gradle
advisory check. It reads the canonical Wrapper distribution from the exact
checked-out commit, queries Gradle's repository advisory feed, rejects unknown
range syntax or incomplete responses, and reports matches without accepting
risk. The maintenance and legacy-candidate audit jobs retain the OSV report and
run this supplementary check even when the OSV step fails; the strict release
build also runs it before Gradle. A failed upstream query is incomplete, not a
passing security result. This check supplements OSV; it does not claim complete
coverage of all dependency or build-tool advisories. The [captured upstream
records](../dependency-evidence/gradle-build-tool-advisories-2026-11-21.json)
are separate from the retained source-bound OSV counts.

All 13 isolated product builds passed with the checksum-verified Gradle 9.9.2
Wrapper. Each resulting JAR differs from its preceding clean build only in the
`Fabric-Gradle-Version` field of `META-INF/MANIFEST.MF`; every other uncompressed
entry is byte-identical. Those are different artifact hashes, so the old runtime
observations remain attached to their original JARs rather than being relabeled
as exact-artifact executions. The three independent 0.0.2 security proposals
are being tested separately before the update is applied to their existing PRs.

The existing 13 product PRs and three narrow 0.0.2 security PRs now propose
the checksum-verified Gradle 9.9.2 Wrapper. This is a directly related build-tool
security correction, not a Mod version or rendering redesign. The security PRs
remain at 0.0.2 and were returned to draft for fresh checks and independent
review. The [current source pins](../version-consistency-1.0.0/current-heads.json)
and candidate monitoring entries have advanced; new-head validation remains
pending until its results are recorded.

### Local build credential isolation

The first 9.9.2 compatibility and initial final-build subprocesses inherited the
workspace `GH_TOKEN` environment variable. That credential was capable of the
repository push and PR-update operations used in this task; its full effective
permissions and lifetime were not established. `RELEASE_AUDITOR_TOKEN` was not
present. The source and build configuration had been reviewed, but a build or
plugin could read inherited environment variables, and the investigation cannot
prove that no network disclosure occurred. A literal-value scan found no token in
the 25 captured build logs; this does not rule out disclosure by other means.
The initial final-build run was stopped, its preliminary results retained, and
all final build and verification subprocesses are being rerun with credential-like
variables and authentication sockets removed. The repository owner or credential
administrator should assess the exposure and rotate or revoke the credential if
appropriate; no credential value is recorded here.

## 2026-11-21 final proposal validation

The shared game/library preliminary resolution correction is present in all 13
proposal heads. Both namespace production entry points passed their eight-test
compiled fixture suites at the current source. The bounded verifier still
rejects game-owned references inherited from unresolved platform classes; this
is an explicit supported-subset limitation, not proof of complete JVM linkage.
All 13 current product JARs passed a credential-stripped clean build, exact
metadata inspection, the packaged verifier for all 48 advertised versions, and
nine adjacent-version negative controls. All 16 product and security-only PRs
passed Linux and Windows hosted jobs; the actual PR merge commits had the same
tree as their heads, and all 32 downloaded archives and JAR hashes matched the
local clean builds. The [current evidence selection](../version-consistency-1.0.0/current-evidence.json)
binds those observations to the actual sources and retains historical evidence
separately. The 13-group non-publishing rehearsal passed, including 15
production-related controls and three separately identified harness controls.

All 13 final product JARs have new hashes. Compared with each immediately
preceding 9.8.2 clean build, only the Gradle version field in the manifest
changed; every other uncompressed entry matched. The comparison is recorded
[here](../version-consistency-1.0.0/current-validation/artifact-content-comparison.json).
The preceding 1.14 build already included the rendering-state correction; the
old 1.14 runtime artifact preceded that correction. The current 9.9.2 JAR
`2e7ad78a5d80ca4739139dfc33605428df229269155fd14b80151517034fb00d`
then passed eight seeded draws in a [fresh instrumented 1.14 software-GL
diagnostic](1.14-state-regression-2026-11-16/gradle-992-2026-11-21.json).
The separate test Mixin changed the loaded renderer in memory, and the
disposable Xorg server faulted on shutdown after the client completed. This
does not establish unmodified-artifact, hardware-GPU, multiplayer or human
visual acceptance. Other previous runtime observations remain historical and
are not relabeled as observations of the new hashes.

A fresh Gradle dependency resolution and OSV scan was performed for each
current product source with the resolution subprocess stripped of credentials.
The [compressed source-bound evidence](../dependency-evidence/current-build-security-2026-11-21.json.gz)
contains the original snapshots, reports and logs. The ten legacy candidates
have 385 failing occurrences (382 known, three changed against the retained
baseline); the three maintenance proposals have 105 separately scoped known
occurrences. The integrated scan has 105 unresolved occurrences separately;
these are not added to the proposal count. Disappeared findings remain subject
to review, and no risk was accepted. The upstream Gradle advisory review is
separate: 9.8.2 matched seven published advisories; the proposed 9.9.2 matched
none on the captured upstream feed. The result does not prove that every
possible Gradle or game dependency advisory is absent.

The security-first merge simulations were repeated on the final PR heads. Each
pair still conflicts in README and CI. Selecting the reviewed 1.0.0 versions
of those two paths in the temporary index produced exactly the product trees:
`e7a988d5343108c87c3c3a70e0445b9098220add` (#34/#31),
`fe29d5d047c59f2f8bb62798bfce9b32e5f3b7fd` (#35/#32), and
`6c3d75201be0e7b89c43ce82c6b8e2652df5fb5b` (#36/#33). The shared Wrapper
verifier, its tests and the Windows entry point match within each pair. These
are simulations, not merges or review approvals.

The coordinator's ordinary validation passed at code commit
`ab0198e43e1d9082d93365092a028bbb9bbf694e`; the separate live prerequisite
failed because the integrated 1.21.11 source lacks the required 1.0.0 release
API verifier. The final live check must be read at the actual PR head. The
security, owner map-ID decision, independent review, administrator protections,
strict approved-source runtime and publication gates remain open.

A fresh [administrator read-back](../admin/branch-rules-observation-2026-11-21.json)
reports all 14 targets unprotected, no visible repository/parent rulesets or
release environments, no releases, and managed Automatic Dependency
Submission active. No administrative setting was changed. The 17 development
and security PRs were marked ready for independent review; no approval or
merge was supplied. After independently downloading the three prior hosted
0.0.2 security artifacts, an [entry-level comparison](../version-consistency-1.0.0/current-validation/security-artifact-content-comparison.json)
found only the `Fabric-Gradle-Version` manifest field changed in the new
security JARs. Their artifact hashes remain distinct.
