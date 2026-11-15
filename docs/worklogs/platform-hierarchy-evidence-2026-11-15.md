# Platform hierarchy and evidence lifecycle review — 2026-11-15

This record continues the [hierarchy review](hierarchy-review-2026-11-15.md).
The proposal HEADs at the start of this review are the historical source
identities in its dated build and rehearsal records. All 24 pull requests
remained open on refresh; the 14 development proposals remained drafts, the
three 0.0.2 Wrapper-security proposals were ready for review, and none had
auto-merge enabled. Previous runtime observations, artifact hashes, scans and
rehearsals retain their original identities.

| Finding | Scope established at refresh | Consequence under investigation |
|---|---|---|
| Default Object-based Mixin platform ancestry, reported on #20 | All 13 product proposals have identical `game_linkage.py` blob `3a2cb922953a`; both namespace adapters call it. The 0.0.2 security proposals lack this verifier. | A valid class target whose hierarchy reaches an unresolved Java platform superclass can be rejected. The earlier 48-version artifact sweep passed; this is not evidence of a current runtime crash. |
| Historical/current evidence coupling, independently identified | Coordination proposal #15 | A dated observation is compared to a mutable current-head index, making legitimate later changes fail an unrelated historical integrity test. |
| Shared-copy synchronization | All product proposals | Local digest tables detect unsynchronized changes within a branch but cannot alone prove cross-branch identity if code and its local digest both change. |

The source, tests and actual packaged-verifier entry points are under review.
The chosen platform-boundary rule must remain local to the validated Mixin
hierarchy; it must not broaden the general subtype or protected-access rules.
Strict release authorization, the staged protection policy, and the security-
first integration sequence remain in force. No merge, administrative change,
tag, draft release, publication or approval is implied by this investigation.

The adjacent platform audit found one additional conservative boundary. A
compiled game class extending `RuntimeException` can call its inherited
`getMessage()` on the JVM, but when the symbolic owner is that game class both
packaged verifier adapters reject the reference before or during bounded member
resolution: they do not load platform member metadata. This is a real false
rejection for a future valid pattern, not an observed failure of the current
artifacts. The chosen disposition is an explicit, tested fail-closed contract
restriction rather than guessing platform member accessibility or introducing
a full platform resolver. Direct platform-owned references remain delegated to
the configured runtime. Compiled fixtures execute on the JVM and exercise both
actual packaged verifier paths; the restriction is synchronized across all 13
product contracts. The additional source changes contain only fixtures and
verification documentation, and their local digest manifests.

## Disposition and validation

The former rule rejected compiled targets directly or indirectly extending `RuntimeException`, and enum and record targets, in both actual packaged verifier paths; an ordinary Object-derived target passed. The correction treats only the default Object Mixin parent specially, after target and reachable non-platform hierarchy validation. Explicit non-Object ancestry still requires the existing bounded lookup; `is_subclass`, protected access and unresolved platform ancestry were not broadened. Missing targets and non-platform parents, interface targets, cycles, inaccessible supertypes, wrong-kind supertypes and unrelated explicit parents remain rejected. Enum and record fixtures establish only the static hierarchy model, not general transformation correctness. The production adapter fixtures reproduce the prior guard and exercise both namespace variants.

All 13 sources now carry the same shared fix, contract and regression fixtures. The 1.14, 1.21.11 and 26.3 representative complete Python suites passed (62, 59 and 59 tests before the final three added negative cases); the final focused packaged-entry-point fixtures passed for both adapter types. Hosted Linux and Windows CI passed for the preceding intermediate heads; the additional fixture-only heads have queued new checks. The current 48-version static sweep and nine adjacent-version rejections have passed against earlier JAR bytes. Final-source clean builds and hosted artifact checks are in progress; earlier runtime observations remain historical.

| Group | PR | Initial source | Current proposed source |
|---|---|---|---|
| 1.14-1.14.4 | [#23](https://github.com/skyRolly/third-person-readable-maps/pull/23) | `a795f4dc8065000ae4d03e1552481e7918221465` | `fd498ecb3a4dbc09ec458d4b004ee18afb84267c` |
| 1.15-1.16.5 | [#21](https://github.com/skyRolly/third-person-readable-maps/pull/21) | `ae4c0786f5babb3c5fdb5a64573f1024ccde7870` | `96f5c87093416cb9e1c5d3eacbb64fc236fe6044` |
| 1.17-1.19.2 | [#20](https://github.com/skyRolly/third-person-readable-maps/pull/20) | `55c20451c8e9176c3e3886df8bc8929f3801da0b` | `7c7b65d7395e14d5d0d49ed8eadb3899f3872b3f` |
| 1.19.3 | [#22](https://github.com/skyRolly/third-person-readable-maps/pull/22) | `37c6809247fe8cd280e211ad36ca4403432b0c05` | `b0353abf9dc93b774a4fcd2e94c98040fd643813` |
| 1.19.4-1.20.4 | [#19](https://github.com/skyRolly/third-person-readable-maps/pull/19) | `76f0952bb6b27a5af82b4127eb847babe4d134f7` | `97afd9aaf5ed3a305c82bbdd48a8fffb94725037` |
| 1.20.5-1.20.6 | [#18](https://github.com/skyRolly/third-person-readable-maps/pull/18) | `43aa1c678d7e8d1d44c286f937c9ce2929ae0722` | `1dc18e3cb0993fe1ab742d425d5cb74ef9ab12ca` |
| 1.21-1.21.1 | [#17](https://github.com/skyRolly/third-person-readable-maps/pull/17) | `c9a63a72f67c469b302bb99ec34502efb900b03c` | `e80def340550064cbc8ec7250b6b588c2ece1a43` |
| 1.21.11 | [#31](https://github.com/skyRolly/third-person-readable-maps/pull/31) | `d7f5bb77abe622110e2b0d9942d19d10097c09ac` | `03f500e1ea528084024406ed1b85ace18fcf5be3` |
| 1.21.2-1.21.3 | [#16](https://github.com/skyRolly/third-person-readable-maps/pull/16) | `557d55ff7f6fcbc63c4e2ae596df05cee02af040` | `9137a6fcf4fe8fcc92a5f0e6006a5f93a93194fb` |
| 1.21.4-1.21.8 | [#14](https://github.com/skyRolly/third-person-readable-maps/pull/14) | `db33c8bd0afc8c0e4d0a658e580ae4329ea3d40f` | `a1e3a10365f1966b12b5bb431ec9f8371f4e595b` |
| 1.21.9-1.21.10 | [#13](https://github.com/skyRolly/third-person-readable-maps/pull/13) | `832667c27967226478ac11d2728061c04915577e` | `d20a2f0f25f5d680c5092379790d5b724282641d` |
| 26.1-26.2 | [#32](https://github.com/skyRolly/third-person-readable-maps/pull/32) | `11aca8017655fbea4bb735bbc53a661835f4d699` | `b7efb599c8f14e4664c9d2d7372bb0dfe4f1d7af` |
| 26.3 | [#33](https://github.com/skyRolly/third-person-readable-maps/pull/33) | `7058605d2dcf31638a6c8564a94130693bfd9e0c` | `409ecaaf9cfa5782c2965cc538a7188a925b12fc` |

The previous 0.0.2 maintenance sources and security-only PRs do not contain this shared verifier. Their older verifier contracts are distinct; no current runtime failure is inferred. The 0.0.2 patches retain their independently reviewable scope. A fresh read-only conflict simulation produced the following hypothetical resolved trees by taking the proposed 1.0.0 README and workflow at the two conflicting paths. The Wrapper verifier, its tests and Windows entry point are identical in each pair. No merge was performed.

| Security PR → product PR | Resolved tree equals product tree |
|---|---|
| #34 → #31 | `b4b0bb2fd2f19e36208530bc6dfac0954c14773a` |
| #35 → #32 | `5fd3e5f76aa76f0b9a95e922c15b358eab17b03e` |
| #36 → #33 | `110044c96c655d06f2152f8bf47c1572ce7078d5` |

The dated hierarchy test now validates the dated candidate plan rather than `current-heads.json`. Dated security scans likewise compare their own source-bound records instead of the evolving maintenance registry. The generic [current evidence validator](../../scripts/validate_current_evidence.py) checks source, JAR and log identities, continuity, static coverage, hosted checkouts, the candidate rehearsal, retained scan scope and pending conditions; it cannot authorize a release. The [cross-branch comparison](../../scripts/check_shared_verifier_sync.py) reads the actual pinned Git blobs, not merely each branch’s self-declared digest table. A clean public fetch of the 13 pinned commits passed. It is an equivalence check at the selected pins, not proof of independent review or live branch identity.

The preceding non-publishing rehearsal aggregated 13 artifacts covering 48 versions and rejected 15 existing controls plus three separately identified harness controls. A final-source rehearsal is pending; no candidate result is strict release authorization. Changes from each retained security scan source to the current product source contain only the linkage scripts, fixtures and contract; the current index retains each actual scan source. This is dependency-input continuity, not a fresh resolution or a new scan.

## Product, security and integration decisions

Paired candidate/no-Mod tests at 1.20.5, 1.21.4 and 26.3, the 1.21.11 load probe, and the 19-version codec sweep support preserving the typed map ID supplied by Minecraft, including explicit zero. The tested malformed numeric values normalize before the renderer receives them. No additional Mod-specific discrepancy is established by these controls; broader decoding intervention has compatibility and global-behavior costs and is not recommended without a separately reviewed design. Owner acceptance remains PENDING REVIEW, as do unmodified-artifact multiplayer and graphical acceptance. The instrumented LAN repeat observed ID 2 transition from unavailable to available; it did not instrument packets or establish the original observation’s cause. The original large foreground anomaly remains unexplained.

The [critical Netty TLS review](../dependency-evidence/advisory-dispositions/netty-critical-tls-2026-11-15.json) advances ten retained candidate matches, four integrated matches and four separately scoped unmerged-proposal matches. Game runtime remediation is proposed as upstream-dependent; build-scope applicability remains under investigation. None is a fix or an accepted risk. The overall retained scan counts remain 385 candidate and 105 integrated, with another 105 separately scoped unmerged-proposal matches.

At refresh all 14 target branches reported unprotected, visible rulesets were empty and no human PR approval was returned. GitHub-managed Automatic Dependency Submission remained active; its settings toggle requires administrator action and read-back. On the last completed #15 run at `55ec2b1b733d37b5921296e3313f67d1ae907fc1`, ordinary coordination validation succeeded and the live prerequisite failed because integrated 1.21.11 lacks the release verifier. The staged baseline/final protection policy and security-first integration sequence remain appropriate; checks against simulated merged trees do not change the live status.

The refreshed collaborator list returned two accounts; visibility or technical
write access is not an owner appointment or submitted independent approval.
The environments API returned zero visible environments. Auditor-secret and
security-alert settings returned HTTP 403, and the tag-protection endpoint
returned HTTP 404, which does not establish whether another tag ruleset exists.
An administrator must inspect and read back the actual environment, credential,
tag and managed-submission controls. No browser settings surface was available.
