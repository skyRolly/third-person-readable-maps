# Administrative release controls — inspected 2026-11-04

No administrative setting was changed in this maintenance round. Account-level
`permissions.admin: true` does not grant this integration every permission: the
REST protection, secrets, alert, security-update, and code-security-configuration
endpoints returned HTTP 403. Available connector tools have no protection or
security-settings mutation capability. No connected browser-control tool is
available for inspecting the settings UI. These are external prerequisites,
not grounds to relax release authorization.

## Verified inventory and final disposition

| Control | Scope | Initial state | Desired state | Final state | Evidence / blocker |
| --- | --- | --- | --- | --- | --- |
| Legacy branch protection | main | Missing | Enforced PR review and coordination check | BLOCKED: unchanged | Branch `protected: false`, GraphQL `branchProtectionRule: null`; protection REST 403 |
| Legacy branch protection | mc/1.21.11 | Missing | Enforced PR review and both build checks | BLOCKED: unchanged | Same three observations |
| Legacy branch protection | mc/26.1-26.2 | Missing | Enforced PR review and both build checks | BLOCKED: unchanged | Same three observations |
| Legacy branch protection | mc/26.3 | Missing | Enforced PR review and both build checks | BLOCKED: unchanged | Same three observations |
| Effective branch rulesets | All four branches | None | Use supported legacy protection unless verifier is extended | Verified empty; no change | Ruleset inventory and each effective branch-rules endpoint returned `[]` |
| Required checks | All four branches | Not enforced | Strict, app-pinned checks below | BLOCKED: not configured | Actual CI job names verified; protection missing |
| Eligible independent source reviewers | All four branches | No eligible independent collaborator listed | At least one independent writer/maintainer/admin | Requires owner decision | skyRolly: admin, also PR author; ZDN-1942: triage, insufficient for source approval |
| Approved source PR history | Current four heads | No submitted reviews on producing PRs #4/#7/#5/#8 | Current-head approval before merge | FAIL: new independent reviews/merges required | Reviews API returned `[]`; open PRs do not repair history |
| release-draft environment | Repository | Missing | Explicit independent user reviewer, prevent self-review, no admin bypass | BLOCKED: unchanged | Environments API: `total_count: 0` |
| release-publication environment | Repository | Missing | Separate independent deployment approval | BLOCKED: unchanged | Same inventory; reviewer selection is an owner decision |
| RELEASE_AUDITOR_TOKEN | Repository secret | Inaccessible, not proven absent | Read-only credential for all verifier APIs | BLOCKED: metadata 403 | No secret values inspected; current CLI credential is insufficient |
| Release tag protection | Tags | Rulesets inventory empty; legacy endpoint 404 | Immutable tags and controlled creation credentials | Requires owner policy decision; not configured | 404 is not proof of protection; deprecated tag API cannot establish protection |
| Automatic Dependency Submission | Repository | GitHub-managed workflow still active | Disable managed Gradle submission, retain graph/alerts/security updates | **C — blocked by settings access** | New managed runs were queued on maintenance PR pushes; no supported settings read/write access |
| Dependency Graph | Default branch | Available; game dependencies remain visible | Retain graph; do not claim non-default alert equivalence | Available, revision binding UNVERIFIED | SBOM GET succeeded; creator includes Automatic Dependency Submission, but no source SHA/ref to prove current indexing |
| Dependabot alerts | Default branch | Active-alert warning observed, details inaccessible | Keep enabled, review individual native alerts | BLOCKED for settings/details | Git push reports 41 alerts (1 critical, 15 high, 24 moderate, 1 low); alerts endpoint 403 |
| Dependabot security updates | Default branch | Inaccessible | Keep enabled | BLOCKED: current toggle unverified | `automated-security-fixes` GET 403 |
| Dependabot version updates | All maintained branches | Active weekly jobs | Retain central weekly configuration | Configured; wrapper/Actions runs verified | See [monitoring](dependency-monitoring.md); broader pinned-version discovery has a gap |

Tags and Releases list endpoints both returned `[]`; 0.0.2 has not been published.
Repository-level Actions/default-token permission settings also returned403 and
remain unverified; the checked-in workflow permission blocks are separately
inspectable and do not prove those administrative defaults.

API observations are retained in [the maintenance evidence](maintenance-evidence-2026-11-04.json).
No API permission failure was treated as a successful read-back or a missing secret.

## Supported branch protection and activation sequence

The existing verifier accepts legacy protection, not effective branch rulesets.
It also deliberately rejects code-owner review and last-push approval rules,
review bypass allowances, ambiguous/unpinned checks, and unreadable settings.
No such legitimate extra policy was found and removed. If the owner needs one,
extend and independently test the verifier first; do not disable that policy.
Team-only environment reviewers remain unsupported; list an independent user.
Tag-only rulesets do not apply to branches and can coexist with legacy protection.

1. The repository owner must select an independent source reviewer and give that
   person write, maintain, or admin permission. Do not automatically promote the
   currently listed triage collaborator. Confirm their availability and that
   they are independent of the author and release dispatcher. The owner must
   retain an authorized administrator recovery path for broken checks; recovery
   is an auditable administrative policy change, not a release bypass.
2. Confirm current `ci.yml` produces `Validate coordination` on main and exactly
   `Build (ubuntu-latest)` and `Build (windows-latest)` on each maintenance branch,
   published by GitHub Actions app **15368**. Inspect current push jobs/check runs,
   not only similarly named PR jobs. The baseline runs are recorded in the
   maintenance report. No required check is being invented for this cleanup.
3. With a separately authorized credential that can read/write Administration,
   read the current protection again. If it is still absent and there are no
   effective branch rulesets, apply the reviewed payloads below. If policy has
   changed, reconcile it instead of overwriting stronger requirements.

   ```sh
   gh api --method PUT repos/skyRolly/third-person-readable-maps/branches/main/protection \
     --input docs/admin/branch-protection-main.json
   # Run once for each of mc%2F1.21.11, mc%2F26.1-26.2, mc%2F26.3:
   gh api --method PUT 'repos/skyRolly/third-person-readable-maps/branches/mc%2F1.21.11/protection' \
     --input docs/admin/branch-protection-maintenance.json
   ```

   These are prepared payloads, **not applied configuration**. They require one
   independent approval, stale-review dismissal, administrator enforcement,
   strict app-pinned checks, no review bypass, no force push, and no deletion.
   Merge commits remain possible; linear history is not imposed. The absence of
   push restrictions does not bypass required PR reviews/checks.
4. Read each protection endpoint back; verify every payload field, `checks`
   publisher IDs and `contexts` correspondence. Query GraphQL for the applicable
   `branchProtectionRule`, `requiresCodeOwnerReviews`, `requireLastPushApproval`
   and zero `bypassPullRequestAllowances.totalCount`. Read effective branch rules
   and repository/parent rulesets again. Verify write access for the independent
   reviewer and an owner-operated recovery path. Do not exercise force-push,
   deletion, or bypass to test enforcement.
5. Have the independent reviewer inspect and approve the final heads of the
   maintenance PRs and the coordination PR. Merge only through the owner’s
   normal review process. Codex leaves them open. If a PR is updated or rebased,
   require fresh approval. After each merge, require successful push CI on the
   exact new maintenance/main head. Existing unreviewed merge commits cannot be
   retroactively authorized by adding a review after merge.
6. If release-plan/runtime-evidence commits advance main later, that main head
   also needs an eligible independently approved PR merge and successful
   `Validate coordination`. An approval on this cleanup is not approval of a
   future release plan or arbitrary later source commits.

## Environments, auditor credential and tags

An administrator must create both named environments under Settings → Environments.
For each, explicitly select an independent **user** reviewer, enable **Prevent
self-review**, disable administrator bypass, and restrict deployment branches
to main. Read back the environment ID and required-reviewer configuration. The
release tool also requires an actual first-attempt dispatch approval by a listed
user other than both actor and triggering actor. A configuration read-back or
simulated unit test cannot prove that approval. Do not run a publishing mode to
test configuration. The current user/triage permissions inventory does not
establish whom the owner authorizes to approve deployments.

Create `RELEASE_AUDITOR_TOKEN` using an owner-approved credential with read access
to Administration/protection, rulesets, environments, PRs/reviews, collaborators,
checks/statuses, and Actions/approval history. Use minimum supported read scopes;
check the credential's actual REST and GraphQL responses, since repository role
alone was insufficient here. Confirm secret metadata through the supported
secret-list endpoint or owner UI, then perform a non-writing API preflight with
that credential. Never print its value or substitute the write token for the
independent audit credential. Do not infer absence from a denied metadata read.

For tags, the owner must select a creation policy that preserves the release
workflow's authorized tag-creation path. A tag-only active ruleset for all tags
can deny **updates** and **deletions** without bypass, while leaving initial
creation possible for authorized repository writers. If creation must also be
restricted to a dedicated GitHub App, provision that identity and adapt/test the
release credential before activating the rule; the current workflow writes with
`github.token`, which must not silently be locked out. Read back the tag ruleset,
its scope, enforcement and bypass actors. No tags need to be created, modified,
or deleted for this inspection. Tag-creation identity is a repository-owner
policy decision, not permission to add a broad bypass.

## Automatic Dependency Submission — final disposition C

Exact intended action: Settings → Security and quality → Advanced Security →
Dependency graph → **Automatic dependency submission → Disabled**. The managed
Gradle workflow was still being generated during this round. Its settings toggle
cannot be read or changed through the available integration. There is no verified
supported API capability here for changing only that toggle; broad security-feature
changes would be unsafe. No change was attempted or claimed.

Before disabling, verify the central audit and maintenance snapshot jobs remain
available. They use JDK 25, generate artifacts without `contents: write`, and do
not depend on managed submission. Central weekly version-update jobs are also
independent. Retain **Dependency Graph**, **Dependabot alerts**, and **Dependabot
security updates**. Default-branch alert coverage is not equivalent to maintained
game branches regardless of snapshot submission.

Expected result: managed Gradle submission stops being generated; the graph and
alert features remain enabled; maintenance snapshot generation, weekly version
updates, and OSV reporting continue. Read the settings back and record a dated
screenshot/account by the administrator. Check a subsequent ordinary approved
push for absence of newly generated managed-submission runs and inspect the
explicit jobs. Do not use absence of one run alone as proof of the toggle. Check
graph SBOM availability and alert/security-update settings independently; do not
assert an indexed maintenance SHA from the SBOM's package list.

The change is reversible by re-enabling only automatic submission if needed,
but re-enabling without a Gradle project on main does not solve the architecture
gap. There is no release authorization to proceed until remaining controls and
independent approvals are verified.
