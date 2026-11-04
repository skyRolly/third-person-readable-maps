# 0.0.2 release-readiness gates — 2026-11-04

**Decision: ready for PR review; blocked from release.** All improvements are
proposed in open PRs and are not integrated maintenance state. No merge,
auto-merge, tag, Draft Release, or public Release was performed. The mod version
and game compatibility matrix are unchanged.

PASS means the named scope was verified. FAIL means an executed check/configuration
fails the requirement. BLOCKED identifies an external prerequisite. NOT RUN means
no execution evidence exists. PENDING REVIEW means independent approval is missing.
None of the latter four statuses counts as PASS. The [review-resolution record](review-resolution-2026-11-05.md)
updates completed candidate CI and corrects the reviewer-permission interpretation.
Candidate tests are evidence for the proposed trees, not protection, approval,
integration, or production-release authorization.

| Gate | Required evidence | Status | Source / result | Remaining action / owner |
| --- | --- | --- | --- | --- |
| 1. Coordination-only main | Main has governance/tools and no Gradle/game project | PASS | Fetched b90ee78; full tree inventory and coordination tests | Preserve architecture — code/reviewer |
| 2. Three authoritative maintenance branches | Actual remote refs and independent build projects | PASS | All supplied baseline SHAs verified; each has complete Gradle/Fabric project | Review separate cleanup PRs — independent reviewer |
| 3. Unified version 0.0.2 | Build properties and JAR metadata agree | PASS | All three local candidate JARs and existing properties verified | Recheck final merged artifacts — code |
| 4. Compatibility matrix | Exact game groups, Loader, namespace and toolchain contracts | PASS | Unchanged release/compatibility.json and branch verification | Maintain six explicit game targets — code |
| 5. Linux build verification | Clean builds for all groups on release source SHAs | PENDING REVIEW | All three current candidate heads passed hosted Linux CI and local checks; exact runs are in the review-resolution evidence | After eligible human review/integration require push CI on each new exact maintenance head — code/reviewer |
| 6. Windows build verification | Both maintenance build identities successful on final heads | PENDING REVIEW | All three current candidate heads passed hosted Windows CI; no candidate runner blocker remains | After eligible human review/integration require both push build checks on each new exact maintenance head — code/reviewer |
| 7. Java runtime and bytecode | JDK25 build; Java21 APIs/bytecode for 1.21.11, Java25 for 26.x | PASS | Gradle release flags, toolchain criteria, verifyModJar and central artifact inspection | Installed Java21 runtime evidence remains gate 9 — runtime tester |
| 8. Four-version API verification | Shared JAR checked against hash-verified 26.1/26.1.1/26.1.2/26.2 clients | PASS | 33 game/Blaze3D references and Mixin descriptor passed on all four; 1.21.11/26.3 negative checks rejected | Both candidate hosted OS checks passed; repeat against final approved release JAR — code |
| 9. Installed-client/graphical verification | Six version-specific reports bound to exact source/artifact, full hand/arm/data/motion matrix | BLOCKED | Historical smoke tests exist, but no approved reports for proposed source SHAs/artifact digests | Test all six versions, including Java21 for 1.21.11, and submit evidence — runtime tester |
| 10. Dependency scanning and disposition | Complete inventories, advisory details and defensible reviewed outcomes | FAIL | Detection passed; 40 unique advisories / 105 group-package-version-advisory combinations remain Further investigation; no accepted risks | Resolve named applicability questions, upstream follow-ups and security approval; run integrated weekly audit — security reviewer/maintainer |
| 11. Effective branch protection | Enforced policies on all four branches with read-back | FAIL | protected:false, GraphQL rules null, effective branch rules [] | Owner confirms independent reviewer availability/authorization; administrator applies/read-backs payloads — owner/admin |
| 12. Required-check identities | Strict app-pinned required checks, not just successful jobs | FAIL | Current actual jobs verified with live verifier; no enforced required checks | Apply strict GitHub Actions app15368 check configuration — administrator |
| 13. Independent GitHub source approvals | Eligible non-author approvals on current PR head before merge | PENDING REVIEW | Producing baseline PRs #4/#5/#7/#8 lack eligible reviewed history; PRs #9–#12 have no submitted reviews; ZDN-1942 has verified Write and is potentially eligible | Confirm independence/availability/owner authorization and obtain actual exact-head reviews — owner/reviewer |
| 14. Reviewed maintenance revisions | Independently approved PR merges into each mc branch | PENDING REVIEW | PRs #9/#10/#11 exist, unmerged/unapproved | Human review and merge after protection, then exact-head push CI — reviewer/owner |
| 15. Coordination HEAD approval | Approved PR merge for exact main plan/coordinator head | PENDING REVIEW | PR #8 has no submitted reviews; proposed coordination changes need approval | Review coordination PR; later release-plan changes also need eligible reviewed merge — reviewer/owner |
| 16. Protected release environments | Both named environments exist with verifiable policies | FAIL | Environment inventory empty; individual GETs404 | Create/read-back release-draft and release-publication — administrator |
| 17. Independent deployment reviewers | Listed user, prevent-self-review, no admin bypass, actual independent approval | BLOCKED | Environments/reviewers absent; Write-access collaborator is only a potential candidate, not an appointed approver | Owner confirms independence and designates environment users; later actual first-attempt dispatch approval — owner/admin/reviewer |
| 18. Auditor credential | Supported secret metadata and read-only API functional access | BLOCKED | Secrets endpoint403; current credential cannot read protection/security settings | Configure/verify RELEASE_AUDITOR_TOKEN without exposing value — administrator |
| 19. Git tag protection | Verified tag immutability and authorized creation path | BLOCKED | No rulesets listed; deprecated tag API404; creation-identity policy undecided | Select supported tag-only ruleset/credential policy; read back without tag writes — owner/admin |
| 20. Release-plan pinning | Reviewed release/plan.json pins current approved mc heads, all groups/version/change attestations | PENDING REVIEW | Only example plan integrated; local candidate plan pins exact proposed heads, source verification passed | After source integration, submit real plan in reviewed main PR — maintainer/reviewer |
| 21. Runtime-evidence binding/review | Reports match source commit, game version and artifact digest | BLOCKED | Strict validator rejects missing version-by-version reports; no reports invented | Commit authentic reports and obtain independent review — runtime tester/reviewer |
| 22. Artifact provenance | Three artifacts tied to pinned sources and coordinator, candidate flag correct | PASS | Non-publishing local aggregation emits provenance for actual proposed artifacts | Rebuild from approved integrated sources for production — code/reviewer |
| 23. JAR/checksum integrity | Correct classifiers/metadata/namespace/bytecode and SHA-256 | PASS | All three candidate JARs inspected; checksum bundle verified; repeat clean builds byte-identical | Repeat production verification on final approved inputs — code |
| 24. Non-publishing dry run | Group/source/artifact verification and rejection of incomplete production evidence | PASS | Local candidate run with actual built JARs and remote source-SHA checks; strict missing-evidence rejection passed; no write API used | Hosted dry run with reviewed integrated plan still NOT RUN — code/reviewer |
| 25. Live GitHub release authorization | Protection, reviews, CI, environment, auditor and runtime evidence all qualify | FAIL | Live current-head CI identity checks pass; protection/environment preflight rejects actual configuration | Complete gates11–21 and perform non-writing full authorization preflight — admin/reviewer/code |
| 26. Actual Draft Release preparation | All source/plan/runtime/security/admin gates satisfied and independent draft deployment approval | BLOCKED | Preconditions unsatisfied; no draft created, mode not dispatched | Owner resolves blockers and separately authorizes preparation in a later task — owner/reviewer |
| 27. Actual public publication | Verified approved draft, immutable sources/assets and separate publication approval | BLOCKED | No draft, release authorization, or publication approval | Complete earlier gates; separate later publication authorization — owner/reviewer |

## Integration and activation order

1. Owner confirms an eligible independent source reviewer and their availability;
   ZDN-1942 already has Write but independence and owner authorization still need
   confirmation. Administrator verifies current state and, under separately
   authorized administration, enables/read-backs protection. This focused review
   does not authorize administrative changes or collaborator promotion.
2. Review the coordination and maintenance PRs. The centralized Dependabot
   configuration is already integrated, so branch-local-file removal has no
   dependency on new scanner code. After approval, integrate PR #12 into main
   first, verify its main push check and central links, then integrate PRs #9–#11
   in any order after their own approvals. No merge is performed by this task.
3. Human maintainers integrate approved PRs and verify exact merged-head push CI.
   If checks or refs change, rerun review/validation; do not use earlier head
   approvals for a later commit.
4. Administrator finishes environments, tag policy, auditor metadata/API access
   and Automatic Dependency Submission disposition A. Independently triage
   unresolved advisories; complete the runtime matrix and a source-pinned plan.
5. Independently review the final main plan/evidence commit, run a hosted
   non-publishing dry run, and re-evaluate every gate. This maintenance round does
   not authorize prepare-draft or publish.

The [administrative report](administrative-controls.md) provides exact settings,
payloads, permissions, read-back steps and recovery considerations. The
[maintenance report](maintenance-2026-11-04.md) records branch changes, tests,
intentional differences, monitoring and security evidence. A passing simulated
publication test validates a control in code; it supplies no live approval.
