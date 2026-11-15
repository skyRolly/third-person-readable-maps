# Hierarchy and Mixin linkage review — 2026-11-15

The initial coordinator proposal is `e2d333f6c6d72134bbd0178838029d57bbdaa975`.
The [previous worklog](wrapper-nest-review-2026-11-14.md), [candidate source
index](../version-consistency-1.0.0/current-heads.json), [compatibility evidence](../compatibility-1.0.0-validation.md), [security scans](../dependency-evidence/osv-rescan-2026-11-14/wrapper-hardening/), and [release gates](../release-readiness-1.0.0.md) retain their original observations and source identities.

At refresh there were 24 open PRs: 14 broader drafts, three ready security-only proposals, and seven dependency-update PRs; none had auto-merge enabled. All product and security-only Linux/Windows checks had passed on the previously observed heads. Coordination's ordinary check passed and its live prerequisite check failed. The three existing maintenance branches remain 0.0.2; the ten legacy targets remain placeholders.

The refreshed review API returned one `COMMENTED` automated Devin review on each of #34–#36, each saying no issues were found on the then-current head. These are bot comments, not independent human approvals; #35 subsequently advanced for its CI cleanup. No inline review comments or issue-discussion comments were returned for the 24 open PRs. All 14 target branch APIs reported `protected: false`; the [dated read-back](../admin/branch-rules-observation-2026-11-15.json) also records visible effective rules.

All 13 proposed product heads have the same `game_linkage.py` (`6b8990801e97`), `jvm_linkage.py` (`2106170ce5bf`), shared JVM test (`fa4c160eaf8a`), linkage contract (`d728cd9d16bf`), and Wrapper verifier (`cb0122a0de2f`) blobs. Their packaged-entry-point fixtures have two namespace-specific variants. The following findings are under active investigation; no runtime failure of the current JARs is inferred from a verifier defect.

| Finding | Reported PRs | Initial applicability | Investigation |
|---|---|---|---|
| Direct hierarchy access and kind | #14, #16, #19, #20, #22 | Shared parser and resolver on all 13 product proposals | Determine which candidate and transformed-Mixin declarations are JVM-relevant; test presence, accessibility, kind, finality and supported ancestry. |
| Mixin private helper `invokespecial` | #32, #33 | Shared early owner guard on all 13 product proposals | Compare original owner with transformed target while retaining cross-Mixin, collision and private-access checks. |
| Main protection payload | Coordination #15 | Final documented main payload lacks one check required by release authorization | Prepare separate baseline and final policies and a non-bypass migration procedure; do not change repository settings. |
| Duplicate Python setup | Security #35 | Two identical setups in one build job | Check whether the second setup is required before its existing four-version API check. |

The 0.0.2 security proposals are separate from product upgrades. The 26.1–26.2 integrated branch uses an older verifier, so its applicability must be assessed separately. Historical screenshots will be examined where they support a current decision, not relabeled as fresh acceptance evidence.

## Decisions and focused validation

The thirteen product proposals now carry the same hierarchy and effective-owner changes. Direct candidate superclass and interface declarations are validated independently of ordinary descriptors. The model checks missing, inaccessible, wrong-kind and final supertypes, duplicate interfaces and cycles. Sealed candidate classes and sealed parents are rejected within this bounded model; it does not claim general module, class-loader, platform-class or arbitrary Mixin verification. Same-package access across differently identified candidate/game/library origins is conservatively rejected because identical runtime loader identity is not established. Java platform hierarchy outside the supported candidate subset remains subject to the configured Java target and runtime JVM.

The Mixin path checks the target hierarchy and the supported superclass and contributed interfaces in the transformed target context. For a non-constructor `invokespecial`, the early guard now compares effective owner and caller; subsequent checks still reject a different Mixin, target collisions, non-private members and different effective declaring classes. This does not authorize arbitrary `invokespecial` or change final-field rules. Actual Mixin transformation of an additional artificial helper fixture remains outside the static fixture's evidence.

Both intermediary and official packaged-entry-point fixture suites reproduce the old inaccessible-interface false acceptance and private-helper false rejection, then exercise corrected results and controls. Compiled hierarchy fixtures also compare the result with actual JVM class loading. Existing descriptor-only, nestmate, final-field, inherited-library, Mixin injection, and Wrapper checks are preserved. Full product suites on representative 1.14, 1.21.4 and 26.1 groups passed locally; the per-group final clean builds, complete 48-version verifier sweep and exact-head hosted CI are being recorded separately. A verifier defect alone does not establish a current artifact runtime failure.

The original main branch-protection payload contained only `Validate coordination`; strict release authorization requires that check and `Validate live release prerequisites`, both from GitHub Actions. The final payload now lists both. A separate baseline payload retains only the check available on current `main`; applying it is not release authorization. The staged administrator instructions retain reviews and administrator enforcement while adding the second check only after the proposed workflow is integrated and has produced it. No administrative settings were changed. The ten placeholder targets need their own effective protections before their respective ports are integrated; protection alone does not activate a port.

Security PR #35 advanced to `ceac175977fc8edd4369ce530566630604b181be` solely to remove a second identical Python setup within one build job. Its existing four-version API verifier, Wrapper preflight and 0.0.2 product scope remain. #34 and #36 retain their prior heads. The integrated 26.1–26.2 implementation has a different older verifier that resolves member names and descriptors without the new hierarchy/access guarantees; this establishes an independent coverage limitation, not a demonstrated 0.0.2 runtime defect. The broader correction belongs to the already open #32 proposal; the narrow security patch remains independently reviewable.

The [Netty advisory follow-up](../dependency-evidence/netty-high-review-2026-11-15.json) records two high-severity advisories and 28 source-scoped retained matches with proposed upstream-dependent remediation and further reachability investigation. These are not accepted risks or fixes. The existing scans remain failing, and separately scanned unmerged proposals must not be counted as additional integrated findings.

## Current cross-branch applicability and evidence

The two shared verifier mechanisms were present in every proposed 1.0.0 group below. Both fixes and the shared regression files were propagated to each proposal; the two packaged-entry-point fixture variants remain namespace-specific. The current artifact inventory found no non-constructor `invokespecial` from a Mixin in any of the 13 retained JARs, and the strengthened hierarchy check passed their advertised versions. The issues are verifier weaknesses, not evidence that these artifacts crashed.

| Group | PR | Initial head | Corrected head | Hierarchy and Mixin regression |
|---|---|---|---|---|
| 1.14-1.14.4 | [#23](https://github.com/skyRolly/third-person-readable-maps/pull/23) | `4238f7e72b6c` | `a795f4dc8065` | Shared correction; 48-version sweep and adapter fixtures |
| 1.15-1.16.5 | [#21](https://github.com/skyRolly/third-person-readable-maps/pull/21) | `2ccfa1bd66fa` | `ae4c0786f5ba` | Shared correction; 48-version sweep and adapter fixtures |
| 1.17-1.19.2 | [#20](https://github.com/skyRolly/third-person-readable-maps/pull/20) | `4ed3f218eea6` | `55c20451c8e9` | Shared correction; 48-version sweep and adapter fixtures |
| 1.19.3 | [#22](https://github.com/skyRolly/third-person-readable-maps/pull/22) | `685cd693b4fa` | `37c6809247fe` | Shared correction; 48-version sweep and adapter fixtures |
| 1.19.4-1.20.4 | [#19](https://github.com/skyRolly/third-person-readable-maps/pull/19) | `8ea00a53fc0a` | `76f0952bb6b2` | Shared correction; 48-version sweep and adapter fixtures |
| 1.20.5-1.20.6 | [#18](https://github.com/skyRolly/third-person-readable-maps/pull/18) | `ec9ba516a200` | `43aa1c678d7e` | Shared correction; 48-version sweep and adapter fixtures |
| 1.21-1.21.1 | [#17](https://github.com/skyRolly/third-person-readable-maps/pull/17) | `78084b69ff0a` | `c9a63a72f67c` | Shared correction; 48-version sweep and adapter fixtures |
| 1.21.11 | [#31](https://github.com/skyRolly/third-person-readable-maps/pull/31) | `e1ca4915cac0` | `d7f5bb77abe6` | Shared correction; 48-version sweep and adapter fixtures |
| 1.21.2-1.21.3 | [#16](https://github.com/skyRolly/third-person-readable-maps/pull/16) | `38d2ebdc7092` | `557d55ff7f6f` | Shared correction; 48-version sweep and adapter fixtures |
| 1.21.4-1.21.8 | [#14](https://github.com/skyRolly/third-person-readable-maps/pull/14) | `7fba2607ceb3` | `db33c8bd0afc` | Shared correction; 48-version sweep and adapter fixtures |
| 1.21.9-1.21.10 | [#13](https://github.com/skyRolly/third-person-readable-maps/pull/13) | `9f3624b38216` | `832667c27967` | Shared correction; 48-version sweep and adapter fixtures |
| 26.1-26.2 | [#32](https://github.com/skyRolly/third-person-readable-maps/pull/32) | `ec38b73e0206` | `11aca8017655` | Shared correction; 48-version sweep and adapter fixtures |
| 26.3 | [#33](https://github.com/skyRolly/third-person-readable-maps/pull/33) | `f44db59120f1` | `7058605d2dcf` | Shared correction; 48-version sweep and adapter fixtures |

The ten legacy targets remain 1.21.11 placeholders, not integrated ports; the three existing 0.0.2 branches and narrow security PRs do not contain this shared verifier. The 26.1–26.2 0.0.2 branch has a different older member-presence verifier with weaker access/hierarchy coverage. The bot update PRs change action or Wrapper versions and do not supply this shared correction. Coordination owns no game verifier. [Current source, artifact, test and inventory evidence](../version-consistency-1.0.0/hierarchy-2026-11-15/) records exact hashes and scoped limitations.

All 13 clean Linux builds passed and reproduced the previous JAR hashes. The new committed verifier passed all 48 advertised versions against those byte-identical retained JARs; nine adjacent unsupported-version controls were rejected. Representative full Python suites passed on a Java 8-era intermediary group, the two-Mixin intermediary group, and an official-namespace group. The [non-publishing rehearsal](../legacy-dry-run-1.0.0-2026-11-14/hierarchy-2026-11-15/) bound the 13 final proposal heads and artifacts and rejected 18 controls, including three checks by the rehearsal harness rather than the production aggregator. Hosted checks and approved merged-source evidence remain distinct.

The [paired 1.20.5 item-loading test](../component-map-id-item-loading-2026-11-13/1.20.5-2026-11-15/) ran the exact proposed 1.0.0 JAR and a no-Mod control in separate copied worlds. Both preserved explicit zero and seven, coerced the tested fractional, overflowing and NaN numbers to zero, and did not retain an identity for the string or missing cases. Map-zero terrain appeared in the selected fractional case. The selected provisional contract is to render the typed identity Minecraft provides, preserving explicit zero without mutating stacks or changing the global codec. The [paired 26.3 native-format probe](../component-map-id-item-loading-2026-11-13/26.3-native-format-2026-11-15/) subsequently loaded newly seeded 26.3 player data without a world-upgrade step and observed the same saved identities and map-zero terrain. Its baseline world had previously been upgraded. Owner acceptance, other loading paths, instrumented remote data delivery, hardware GPU and full graphical acceptance remain open.

## Security-first integration simulation

Read-only merge-tree simulations against the corrected heads reported conflicts in `.github/workflows/ci.yml` and `README.md` for each security/product pair. Using the corresponding proposed 1.0.0 version for those two conflict paths in a temporary index produced the exact product tree shown below. The Wrapper verifier, its tests and `Build-Windows.bat` are byte-identical between each pair. This is a candidate resolution plan, not a merge or a substitute for review after the security patches are integrated.

| Security PR | Product PR | Simulated resolved tree |
|---|---|---|
| #34 | #31 | `b73d6dd8c2351b438fe807a0ca0d244a6b157274` |
| #35 | #32 | `b5e0a56acc4b0d142eb6f73a2b509f5a090166c6` |
| #36 | #33 | `d0dea21adc96e5baed72318b9557af2b62e5cc69` |

The latest coordinator push run [43702709325](https://github.com/skyRolly/third-person-readable-maps/actions/runs/43702709325), on `19195e6cf04088fff5ce754090a8fc2c465d68b8`, passed ordinary validation and failed the separate live gate because `mc/1.21.11` lacks the required release API verifier. The security-only proposals alone do not satisfy that 1.0.0 prerequisite. GitHub-managed Automatic Dependency Submission remains active; its administrator setting remains inaccessible to this credential. The latest Maintenance Dependency Audit remains run [42630819979](https://github.com/skyRolly/third-person-readable-maps/actions/runs/42630819979), with completed scans and 105 unresolved integrated findings, not an OSV infrastructure failure.

The product-source inventory contains 23 distinct Java blob/path pairs across the 13 proposals. The rendering paths, hand-state capture, map-ID lookup, pose restoration and version-specific API changes were reviewed by blob identity and comparison; no additional runtime defect was established by that inspection. The earlier open-PR inventory covers every current PR diff and its historical evidence categories. Relevant map-ID and foreground captures were inspected for these decisions, but every archived screenshot was not individually re-reviewed; the original large foreground anomaly remains unexplained. A passing build is not full visual acceptance.

The three open Gradle Wrapper 9.9.0 bot proposals #28–#30 passed the coordinator's canonical Wrapper checksum verifier at their current heads. The setup-java and Wrapper bot changes remain separate and must be rebased or recreated and revalidated after the target security and 1.0.0 changes. Their old-base CI does not establish compatibility with the future combined trees; no broad historical Gradle upgrade is proposed. The [dependency continuity index](../version-consistency-1.0.0/hierarchy-2026-11-15/dependency-continuity.json) records unchanged build inputs without relabeling earlier source-bound reports as new resolutions.
