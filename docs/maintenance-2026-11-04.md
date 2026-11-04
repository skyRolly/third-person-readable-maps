# Maintenance harmonization report — 2026-11-04

**Handoff: ready for independent PR review, blocked from release.** Proposed
maintenance changes are open in PRs [#9](https://github.com/skyRolly/third-person-readable-maps/pull/9),
[#10](https://github.com/skyRolly/third-person-readable-maps/pull/10), and
[#11](https://github.com/skyRolly/third-person-readable-maps/pull/11). Coordination
changes are proposed separately against main. None is integrated or approved by
this task. No merge, auto-merge, tag write, Draft Release, or public Release was
performed. Mod version 0.0.2 is unchanged and unreleased.

## Verified baseline and branch maintenance matrix

A fresh fetch and ls-remote confirmed all supplied heads. There were no open PRs
before this round; PR #8 was merged into main at the stated SHA. Full tracked
trees, actual API responses and current-head CI job identities are preserved in
[the machine-readable evidence](maintenance-evidence-2026-11-04.json), rather than
inferred from an earlier worklog.

| Branch | Initial HEAD | Proposed HEAD / PR | Build CI | README | Dependencies | Outstanding issues |
| --- | --- | --- | --- | --- | --- | --- |
| main | b90ee78e9b1da6d1da2c2f5f93da765739716137 | maintenance/coordination-2026-11-04; exact final SHA in PR | Initial hosted coordination PASS; proposed 53 Python tests and workflow lint PASS; hosted proposal pending | Exact title/intro and coordination badge | Expanded existing central audit; reviewed ledger | Review, integrated schedule, admin/security/runtime gates |
| mc/1.21.11 | 1bbd3f41b97ea5d0b78ae1909e846462078bdf9d | 7779e3a89849cdaf3b08aa536b79d8c238fa1874 / #9 | Initial hosted Linux+Windows PASS; candidate local Linux PASS; candidate hosted queued | Standardized, branch badge | No version change; duplicate Dependabot config removed | Candidate Windows/hosted snapshot; reviewed merge; Java21 runtime/graphics reports |
| mc/26.1-26.2 | 6891b6080e4bea981f7a7399a061b32f95f3452e | e1bce43c0f370fb28bbf87ba974c8d1582c85fb0 / #10 | Initial hosted Linux+Windows PASS; candidate local Linux and four-version API PASS; hosted queued | Standardized, branch badge | No version change; four runtime manifests audited centrally | Candidate Windows/hosted snapshot; reviewed merge; all four runtime/graphics reports |
| mc/26.3 | 0839b2cc31ec2a57ffeae82a8b8f892a649f8eaf | dd43b41d3c4134430a57cc8eed0cc522249a614c / #11 | Initial hosted Linux+Windows PASS; candidate local Linux PASS; hosted queued | Standardized, branch badge | No version change; duplicate Dependabot config removed | Candidate Windows/hosted snapshot; reviewed merge; runtime/graphics reports |

Baseline push CI runs: main **41853117268**, 1.21.11 **41842279767**,
26.1–26.2 **41842370918**, 26.3 **41842321970**. The actual release verifier's
`check_ci` function passed on each exact initial HEAD against live workflow,
job/check identity and GitHub Actions app15368 data. New maintenance PR CI runs
are **41862276302**, **41862279700**, **41862283894** respectively; they were
queued at the recorded inspection. Queued jobs supply no successful execution
evidence and are not counted as PASS.

Branch relationships are intentionally not uniform: mc/26.3 is an ancestor of
main (main is 12 commits ahead at the baseline). Main diverges from mc/1.21.11
at 4810b1b113fedcd87c9e4d203e8d804fd19e0e74 (16/2 commits) and from mc/26.1-26.2
at f49e44585537155aaf3eee123173ae8efe4b8518 (14/2). The two 26.x branches diverge
at f49e445 (2/2). This is evidence for independent maintenance, not a reason to
merge main wholesale into game branches. Producing PR #5 originally targeted
the modernization branch; a new reviewed PR into mc/26.3 is required by the
current authorization contract.

## Findings by priority

- **P1 / release blockers:** no branch protection on any authoritative branch;
  no release environments; no eligible independent source reviewer other than
  the author in the collaborator inventory; no submitted reviews on PRs #4/#5/#7/#8.
  Auditor secret metadata and security/protection settings are inaccessible (403).
  No tag ruleset is listed. Live preflight rejects protection and environment
  prerequisites. Prepared payloads are not applied settings.
- **P1 / unresolved security:** 40 distinct advisories affect 105
  advisory/package/version/group combinations across Gradle and runtime scopes.
  Some source records are high/critical, but exploitability in the game client
  is not established. Every combination is individually traceable and remains
  Further investigation. No risk was accepted or unsafe override applied.
- **P2 / monitoring:** managed Automatic Dependency Submission still generates
  runs despite coordination-only main; final disposition C is blocked by
  settings access. Runtime manifests differ materially for 26.2, so the previous
  26.1-only snapshot was insufficient. Gradle Dependabot jobs observed only the
  wrapper, which limits claims about pinned Loader/Loom/Minecraft updates.
- **P2 / CI:** historical main/candidate/modernization triggers and main-based
  cache ownership predate the branch architecture. Proposed workflows target
  their actual maintenance base and reserve cache writes for branch pushes.
- **P3 / documentation:** unqualified/missing badges and historical candidate,
  unmerged-PR and submission descriptions were inconsistent. README titles,
  introductions, section order and current branch/release status are corrected.
- **P4 / verification:** local candidate builds, API checks, release regressions
  and candidate aggregation pass. Hosted proposal jobs remain queued and fresh
  source-bound graphical evidence is missing. Those are separate from code-test
  success and must not be bypassed.

## Complete tracked-tree review

Categories: game = required version difference; shared = synchronized convention;
historical = obsolete configuration; docs = documentation inconsistency;
validation = functional/monitoring/release concern. The full per-branch blob hashes
are in the evidence JSON. Each tracked path is covered below.

| Tracked files | Category | Action and rationale |
| --- | --- | --- |
| .gitattributes | Shared | Retain identical maintenance rules, including CRLF Windows scripts and binary JAR handling; main's absence of game-script rules is intentional |
| .gitignore | Shared | Add existing Python ignore patterns to 1.21.11 and26.3; all maintenance ignore files now agree. Main keeps coordination output patterns |
| LICENSE | Shared | Retain identical MIT license on all four branches |
| Build-Windows.bat | Shared | Retain identical supported external-working-directory entry point, CRLF and error propagation; absent on coordination-only main |
| settings.gradle | Shared | Retain identical repository/plugin conventions and project identity |
| gradlew, gradlew.bat, gradle/wrapper/gradle-wrapper.jar, gradle/wrapper/gradle-wrapper.properties | Shared / validation | Retain identical wrapper version9.8.2, integrity digest, retry/network settings and executables; no wrapper bytes changed in PRs |
| gradle/gradle-daemon-jvm.properties | Shared / game | Standardize comment, preserve toolchainVersion25 on all branches; runtime targets remain separate |
| gradle.properties | Game | Retain target versions, pinned Loom/Loader/mod identities and JDK discovery; no version change |
| build.gradle | Game / validation | Retain remapping Loom + release21 for1.21.11, standard Loom + release25 for26.x, mappings/remap/classifier differences and common verification application |
| gradle/verification.gradle | Game / validation | Retain target-specific metadata, mapping namespace, bytecode and Mixin signature/JAR checks; no weakened or deleted verifier |
| src/main/resources/fabric.mod.json | Game | Retain explicit game versions, Java and Loader constraints, mod ID, MIT and client-only metadata |
| src/main/resources/thirdpersonreadablemaps.mixins.json | Game | Retain Java21 versus25 compatibility level and required client Mixin behavior |
| src/main/java/tech/rolly/thirdpersonreadablemaps/ReadableMapSurface.java, src/main/java/tech/rolly/thirdpersonreadablemaps/mixin/ReadableMapLayerMixin.java | Game | No source change; identical older-group sources are acceptable. Preserve26.3 pose/rendering adaptations; no shared module or universal JAR |
| scripts/verify_supported_apis.py | Game / validation | Retain on shared26.x branch only; verifies every advertised version on both OSes, no duplicate CI invocation |
| .github/workflows/ci.yml | Historical / shared / validation | Maintenance triggers/cache/artifacts standardized; required job names and Windows verification retained; obsolete26.x Java21 submission-launcher probe removed |
| .github/dependabot.yml | Historical / validation | Remove redundant maintenance copies; retain main's seven weekly authoritative entries, no Gradle entry on main |
| README.md | Docs | All four exact titles/intros; maintenance structure and qualified badges; main remains coordination landing page |
| .github/workflows/dependency-audit.yml, scripts/scan_dependency_snapshot.py | Validation | Existing central workflow extended with runtime manifests, reviewed comparisons, explicit incomplete reports; reject OSV error-shaped responses |
| scripts/authorize_release.py, scripts/release_github.py, .github/workflows/release.yml | Validation | Retain fail-closed authorization and all write boundaries without edits; no parser relaxation for unsupported governance |
| scripts/release.py, tests/test_release.py | Validation | Permit maintenance/* only in non-publishing candidate plans, with regression proving strict plans still reject them |
| release/compatibility.json, release/plan.example.json | Game / governance | Retain unchanged compatibility and release-plan interface; no fabricated production plan/evidence |
| tests/test_authorize_release.py, tests/test_coordination.py | Validation | Retain existing authorization and coordination regression suite |
| docs/compatibility.md, docs/releasing.md, docs/coordination-architecture.md, docs/dependency-audit-2026-11-04.md | Docs / historical / governance | Update current status and link authoritative new records; preserve meaningful historical decisions and earlier evidence |

New central files: `scripts/audit_dependencies.py`, `tests/test_dependency_audit.py`,
`docs/security-advisories.{json,md}`, `docs/dependency-evidence/*.json`,
`docs/dependency-monitoring.md`, `docs/administrative-controls.md`, prepared
`docs/admin/branch-protection-{main,maintenance}.json`, and this dated report,
evidence JSON and release gate matrix. No unrelated formatting sweep was made.
The only deleted files are the three redundant branch-local Dependabot configs;
obsolete trigger/probe blocks were removed from otherwise retained workflows.

## Consequential decisions

| Decision | Evidence / alternatives | Selected action and reason |
| --- | --- | --- |
| Cache trust boundary | Old test treated main as only writer, now no Gradle project there. All PRs, including same-repo PRs, should be read-only | Write only on push to the exact mc branch; dispatch/PR/snapshot jobs read-only. Enforcement still needs branch protection |
| Trigger coverage | pull_request.branches matches base, not source; no historical candidate refs remain | Exact maintained PR base and push branch, plus dispatch. Candidate work gets CI through its PR, avoiding duplicate source-push builds |
| Java21 launcher probes |26.x runtime/build require25; probes existed for managed submission starting with21 | Remove probe and extra JDK setup, keep daemon criteria/JDK discovery; do not change1.21.11 release21 verification |
| Dependency ownership | Default-branch config with target-branch is authoritative; duplicated copies do not extend security-update scope | Remove copies; retain all seven weekly entries, graph/alerts/security updates; document actual parser gap |
| Snapshot jobs | Artifact retention provides per-commit inspection even with central weekly auditing | Retain both per-commit inspection and periodic security reporting, with distinct responsibilities; no extra Graph submission workflow |
| Runtime security coverage |26.2 changes libraries although same mod JAR links correctly | Extend existing audit with all advertised hash-verified manifests, not a new scan workflow |
| Advisory policy | Version matches alone do not prove exposure; game owns matched libraries | Individually record conditions/fixes/proof gaps; no overrides or auto risk acceptance. Known unresolved matches keep failing; new/changed/incomplete are distinct |
| Protection model | Verifier cannot prove effective branch rulesets, code-owner/last-push rules, team-only approvals or unreadable settings | Prepare supported legacy payloads; do not remove a legitimate stronger policy. Owner/admin access and reviewer selection remain blockers |
| Candidate dry run | Existing candidate parser allowed candidate/* only, but new reviewable heads use maintenance/* | Extend only candidate mode and regression-test strict rejection; preserve production source/evidence/protection contract |

P0 baseline and P1 authorization inspection preceded CI edits. Runtime dependency
comparison moved ahead of final documentation because its26.2 differences changed
what the audit could claim. No P3 cleanup was used to pass an unresolved P1 gate.

## README consistency

All four titles are exactly `# Third Person Readable Maps`; all four contain the
exact required introduction as one paragraph. All maintenance READMEs have the
same five ordered sections: requirements/installation, source build, validation/
contributions, dependency/security, compatibility/release status. Each badge and
CI link specifies its own encoded `mc/` branch. Main's badge explicitly denotes
coordination and pins main. Version-specific artifact/runtime/remapping details
remain accurate; no branch is called unapproved or stacked on an unmerged PR.

Relative README links were checked in each worktree; branch links use explicit
GitHub URLs. New central monitoring/ledger links are intentionally pending the
coordination PR's integration and are valid in the proposed combined tree. Main
links each maintained branch and explains contribution routing; it does not own
a game build. Differences in main's section structure and build-pointer summary
are intentional for its coordination role.

## Security advisory disposition summary

The [full ledger](security-advisories.md) and [structured records](security-advisories.json)
contain aliases, severity/vector source, ranges/fixed endpoints, origin, runtime
scope, specific applicability questions, disposition, follow-up owner and review
deadline for every available match. Forty unique advisory IDs are not the same
as package or combination counts. Across branches there are18 distinct affected
package/version pairs,30 group/package/version pairs and105 advisory/package/
version/group combinations. These may appear in several inventories without
being counted twice for the same group identity.

| Group | Gradle packages examined | Union of Gradle/runtime package versions examined | Affected group/package/version pairs | Advisory combinations | Unique advisories |
| --- | ---: | ---: | ---: | ---: | ---: |
|1.21.11|86|87|10|41|40|
|26.1–26.2|84|114|15|53|39|
|26.3|86|87|5|11|11|

Remediated:0. Verified directly actionable compatible mod fixes:0. Further
investigation:105 combinations. Formal risk acceptances:0. All matched runtime
libraries are game-owned; upstream coordination is needed if the named conditions
are reachable. That ownership does not turn unverified applicability into a
confirmed vulnerability or non-applicability finding. Severity labels include
critical/high source advisories and are not calibrated exploitability claims.

The earlier counts10/85,10/84,5/86 were package matches; the recovered1.21.11
snapshot has86 packages including Gradle core. New26.2 runtime scopes account
for13 additional advisory combinations compared with snapshot-only92. Raw OSV
records and full affected ranges are retained once per advisory. Native GitHub
alert details remain inaccessible; the git transport's41-alert warning is not a
substitute for individual native alert triage. The ledger enumerates all available
OSV matches, not inaccessible private alert metadata.

## Validation and release dry run

- Initial coordination suite:36 tests passed. Proposed full suite:53 tests
  passed, including release authorization, candidate-source restrictions and17
  new dependency-audit/candidate regressions. Simulated prepare/publish tests are
  code regressions only; no publishing mode was executed live.
- Actionlint1.7.7 passed on all four proposed workflow trees. The release binary
  checksum was verified. Read-only permissions, exact build identities, branch
  triggers, cache expressions, Windows external-directory entry point and both
  four-version checks were inspected; cache writes have not been live-exercised
  on unmerged maintenance pushes.
- Temurin25.0.5+8 (download SHA-256 verified) and Gradle9.8.2: all three clean
  Linux builds passed with warning-mode=fail. Mixin target, bytecode, metadata,
  classifier, license and mapping namespace checks passed. Local CA trust was
  configured for the session proxy after an initial trust failure, without source
  changes. Repeated clean builds compared byte-for-byte equal on all three JARs.
- Shared26.x API verification passed33 game/Blaze3D member references and the
  injection descriptor against26.1/26.1.1/26.1.2/26.2, using verified Mojang
  client hashes. Negative26.3 check rejected removed mulPose(Quaternionfc);
  negative1.21.11 check rejected the target descriptor.
- Actual local proposed scanner executions against the recovered exact-head
  snapshots and current runtime manifests completed with41/53/11 known matches,
  exit1 as required; no new/changed or false-clean result. Missing data, error
  responses, failed API calls, changed ranges/severity/groups/versions and stale
  baselines are regression-tested. Scheduled integrated execution remains NOT RUN.
- Non-publishing local release validation selected all three proposed commits,
  verified remote candidate head SHAs, validated three real JARs and generated a
  candidate:true manifest, provenance and SHA256SUMS. Strict production validation
  rejected candidate branches, and a separate approved-branch-shaped plan with
  empty reports rejected missing version-by-version runtime evidence. No tag or
  Release API was used. A final candidate rerun against the final coordination
  PR head is retained in the handoff evidence; hosted dry-run execution is NOT RUN.

Candidate JAR SHA-256 values (development validation, not public release assets):

| Group | SHA-256 |
| --- | --- |
|1.21.11|18e3a8dbd461b4bad2711cfe14282b96797f13bebabc8a2b644b6f482a27f930|
|26.1–26.2|75c244ef6440ff2622d8617a5c60288b956d1a1d80956a233e13bac1ced9c554|
|26.3|9f3bc6a3ee4477a3e7cc0f0ebb4c2ff25785ac3f608761f2dc502765f23e2e69|

These checks establish the proposed artifact contract, not approved merged
sources or installed graphical behavior. Historical installed-client smoke tests
are retained in the compatibility record; they do not attest the new source SHAs.
The complete monitoring matrix is in [dependency monitoring](dependency-monitoring.md),
the administrative initial/desired/final-state matrix and exact actions are in
[administrative controls](administrative-controls.md), and all27 release gates
are in the [dedicated readiness matrix](release-readiness-2026-11-04.md).

## Handoff decision

Ready for PR review. Integration requires human approval, working hosted checks
and owner-controlled protection activation. Further live release authorization
verification is blocked by the documented administrative, source-history,
security-disposition and runtime-evidence prerequisites. Draft preparation and
public publication are not ready and were not attempted.
