# Administrative release controls — inspected 2026-11-04

This is the dated administrative evidence, not a current release approval.
The proposed coordinated version is now 1.0.0; see the [current gate matrix](release-readiness-1.0.0.md)
for refreshed branch-protection observations and remaining requirements.

On 2026-11-13 UTC, read-only branch API responses still reported
`protected: false` for `main`, `mc/1.21.11`, `mc/26.1-26.2` and `mc/26.3`.
The effective-rules endpoint returned zero rules for each, and the visible
repository/parent ruleset list was empty. No settings were changed. On
2026-11-13 the [GitHub-managed Automatic Dependency Submission runs](dependency-evidence/automatic-submission-2026-11-13.json)
completed successfully on all 13 advanced product heads; the inspected 26.3
run shows its `submit-dependency-snapshot` step succeeded. Inaccessible settings
prevent confirming the current toggle or indexed alert scope. The existing
administrator action and independent read-back below remain necessary.

No administrative setting was changed in this maintenance round. Account-level
`permissions.admin: true` does not grant this integration every permission: the
REST protection, secrets, alert, security-update, and code-security-configuration
endpoints returned HTTP 403. Available connector tools have no protection or
security-settings mutation capability. No connected browser-control tool is
available for inspecting the settings UI. These are external prerequisites,
not grounds to relax release authorization.

## Review correction and current evidence

No administrative, collaborator-permission or credential change is authorized
or performed in this focused review.

The original collaborator response already records `ZDN-1942` with
`role_name: write`, `permissions.push: true`, `permissions.triage: true`, and
`permissions.admin: false`. The earlier triage-only conclusion was an
**interpretation error**, not evidence that permissions changed. Write includes
triage capabilities. The [historical API record](maintenance-evidence-2026-11-04.json)
is preserved byte-for-byte; its original observations have not been rewritten.
Fresh collaborator-list and effective-permission reads, collected starting
2026-11-05 00:55:16 (UTC+08:00; raw evidence retains UTC), again report Write. The [correction evidence](review-resolution-evidence-2026-11-05.json)
keeps both observations and the original file digest.

`ZDN-1942` is **potentially eligible for independent source review**. GitHub
required-review policy counts eligible approvals from repository writers (or a
required code owner), and `authorize_release.py` accepts current `write`,
`maintain`, or `admin` permission. The verifier additionally requires a non-author
APPROVED review on the exact PR head before merge, enough current approvals for
the configured count, and no outstanding changes requested. Permission alone
cannot satisfy any of those review-record checks.

All four PRs are authored by `skyRolly`; all currently proposed commits have
`skyRolly` as GitHub-associated author and committer. The latest inspected PR CI
actor and triggering actor are also `skyRolly`. The general public event page
lacked matching PushEvents, but the dedicated repository activity endpoint
independently identifies `skyRolly` for the maintenance source-branch creations
and the inspected coordination pushes. Matching refs and after-SHAs are retained
in the correction evidence; the final correction push is rechecked in the handoff.
These account observations support potential technical eligibility; they do not
prove personal independence, absence of involvement or
conflicts, reviewer availability, or the owner's authorization. No additional
owner policy disqualifying this account was found in the accessible repository
records; that is not an affirmative owner appointment. No review has been
submitted on PRs #9–#12. Do not request or submit an approval on another person's
behalf, or infer an approval from this correction.

The same person could technically serve as a deployment reviewer: GitHub requires
at least read access, and this verifier requires an explicitly listed user other
than both the deployment actor and triggering actor. Source-review permission
does not appoint an environment reviewer. Both environments remain absent; owner
authorization, independence/conflict confirmation and a separate actual approval
for each release stage remain required. If that person initiates or re-runs the
release dispatch, they cannot supply its independent deployment approval. Any
stronger owner separation-of-duties policy must also be respected.

References: [GitHub required reviews](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches#require-pull-request-reviews-before-merging)
and [environment reviewers](https://docs.github.com/en/actions/reference/workflows-and-actions/deployments-and-environments#required-reviewers).

## Verified inventory and final disposition

| Control | Scope | Initial state | Desired state | Final state | Evidence / blocker |
| --- | --- | --- | --- | --- | --- |
| Legacy branch protection | main | Missing | Enforced PR review and coordination check | BLOCKED: unchanged | Branch `protected: false`, GraphQL `branchProtectionRule: null`; protection REST 403 |
| Legacy branch protection | mc/1.21.11 | Missing | Enforced PR review and both build checks | BLOCKED: unchanged | Same three observations |
| Legacy branch protection | mc/26.1-26.2 | Missing | Enforced PR review and both build checks | BLOCKED: unchanged | Same three observations |
| Legacy branch protection | mc/26.3 | Missing | Enforced PR review and both build checks | BLOCKED: unchanged | Same three observations |
| Effective branch rulesets | All four branches | None | Use supported legacy protection unless verifier is extended | Verified empty; no change | Ruleset inventory and each effective branch-rules endpoint returned `[]` |
| Required checks | All four branches | Not enforced | Strict, app-pinned checks below | BLOCKED: not configured | Actual CI job names verified; protection missing |
| Eligible independent source reviewers | All four branches | Historical Write access was misclassified as triage-only | Eligible, independent, available and owner-authorized reviewer | PENDING REVIEW: ZDN-1942 is potentially eligible; not appointed | Historical and fresh reads report Write; account differs from author/commit identities; independence/availability/owner authorization and actual approval remain unverified |
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

1. The repository owner must confirm an authorized and available independent
   source reviewer. ZDN-1942 already has Write and is a potential candidate;
   no promotion is implied or needed to establish that technical permission.
   Confirm independence from the author and changes, and any conflicts. This
   record does not select or appoint that collaborator. Any permission change
   for another account needs separate owner authorization. The owner must
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
test configuration. The current Write-access evidence does not establish whom
the owner authorizes to approve deployments or whether they are independent of
the future deployment actors.

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
