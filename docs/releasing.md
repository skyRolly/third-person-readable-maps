# Maintenance and coordinated releases

## Branches and review

`main` owns coordination and release governance, not a Minecraft build.
`mc/1.21.11`, `mc/26.1-26.2` and `mc/26.3` each own their implementation,
Gradle and Fabric configuration, verification, distributable JAR and Linux /
Windows CI. PRs #3–#7 are merged. The maintenance heads and `main` still need
branch protections and independent reviews configured before publication. The
current maintenance HEAD merge PRs #4, #7 and #5 have no submitted reviews; the
release verifier requires approval before merge, so each branch needs a new,
independently reviewed merge commit after protection is configured. See the
[architecture decision](coordination-architecture.md) for the evidence.

Submit each game-specific change to its maintenance branch. For a shared change,
identify all affected groups, open a reviewable PR for each applicable branch,
adapt game-specific rendering when necessary, and record whether it was applied,
modified or deferred. Reviewers verify feature equivalence; matching version
strings or patch hashes alone are insufficient. Update the shared `changes` list
and each group's `verified_changes` in the release plan. Keep the same mod
version in every branch; a coordinated release blocks on version drift or a
missing group. Independent small branches retain the established Loom,
namespace and rendering API boundaries.

## Dependency maintenance

The [monitoring record](dependency-monitoring.md) defines the actual responsibilities
of Dependabot, Gradle snapshots, GitHub Dependency Graph, native alerts and OSV.
The central weekly audit now compares hash-verified runtime manifests for every
advertised version as well as resolved Gradle packages. Its structured ledger
tracks individual advisory/package/version/group identities, changed scope,
resolved matches and incomplete scans. [Individual dispositions](security-advisories.md)
remain unresolved; none is an authorized risk acceptance. Do not force overrides
of game-managed libraries to silence matches.

Automatic Dependency Submission remains active but inaccessible to the available
integration: final disposition **C (blocked)**. An administrator must disable only
that managed submission toggle while retaining graph/alert/security-update
features. See [administrative controls](administrative-controls.md) for exact
observed states, payloads, reviewer prerequisites and activation/read-back steps.
The [maintenance report](maintenance-2026-11-04.md) and [1.0.0 release gate matrix](release-readiness-1.0.0.md)
separate proposed PR tests from integrated-source and live authorization evidence.

## The release commit and global tag

A release uses one `X.X.X` mod version and one annotated tag of exactly that
name, without a `v` prefix. The tag points to the approved **main** commit
containing `release/plan.json`. That plan pins a source branch and full commit for every
compatibility group. Each JAR declares the same mod version but has a distinct
Minecraft classifier. The plan version must match the reviewed
[`release/current-version.json`](../release/current-version.json); changing the
coordinated version requires a reviewed update to that file and the example
plan. The plan is an attestation reviewed alongside the source;
it must reference a checked-in report for each advertised Minecraft version,
including Java 21 runtime evidence for 1.21.11. Store each report at a simple
`release/evidence/<name>.json` path and include that path in the plan:

```json
"runtime_evidence": {
  "1.21.11": {"report": "release/evidence/mc-1-21-11.json"}
}
```

Each report has exactly these fields (replace placeholders with real values):

```json
{
  "group": "1.21.11",
  "minecraft": "1.21.11",
  "source_commit": "<40 lowercase hex characters, the plan source commit>",
  "artifact_sha256": "<64 lowercase hex characters, the tested installable JAR>",
  "installed_jar": "Account of installed JAR, launcher, loader, Java version and test date",
  "graphical": "Account of graphical checks, observations, environment and limitations"
}
```

Commit the reports with the plan and have reviewers inspect them and any linked
logs or media for authenticity, availability, ownership and relevance. Links in
reports are untrusted references, not automatically approved or fetched; arbitrary
URLs cannot be substituted for the repository report. Reviewers check both hands,
dominant arms, map data, missing data, motion and first-person behavior, and
record what was actually tested. Neither a URL nor a structurally valid report
proves a test happened. The build must produce the exact SHA-256 tested in every
report. The manifest embeds each report and its hash, source revision, artifact
hash and coordinator commit; its report path resolves in that commit. The
manifest marks the report as a human attestation and any external references as
unverified.

`release/plan.example.json` is intentionally invalid: it contains zero SHAs and
no runtime evidence. Create `release/plan.json` in a reviewed PR, using exact
approved branch heads and a synchronized version and change list. Commit it to
`main` through review. The current coordinated proposed version is `1.0.0`;
the independently reviewed branch updates have not yet been integrated, and no
coordinated release has been published. If a published identity appears before
release, select a new version through review. Never move, overwrite or delete
a published tag to repair a release; issue a new version instead.

## Validation and publication

1. Configure legacy branch protection for `main` and every maintenance branch:
   require a PR with at least one approval, stale-review dismissal, strict checks,
   administrator enforcement, no PR-review bypass actors (verified through REST or the applicable
   GraphQL branch-protection rule), no force pushes and
   no deletions. On `main`, require `Validate coordination` from the GitHub
   Actions app (ID 15368). On each `mc/*` branch, require both
   `Build (ubuntu-latest)` and `Build (windows-latest)` from that app. Pin
   every additional required check to its app as well. The head must be the
   merge commit of a PR into that branch with the required number of independent,
   non-dismissed approvals from currently write-authorized reviewers on the final
   PR head. The latest push run of the exact `ci.yml` on each pinned HEAD must
   succeed, with the role-specific jobs present and successful in its current
   attempt. The current required checks must also succeed. Rerun all jobs if a
   partial retry omits a required job. Workflow-run paths may be bare or
   include the exact triggering branch as `@<branch>` or `@refs/heads/<branch>`;
   the repository-qualified form must name this repository. Workflow ID, event,
   branch and pinned SHA are also checked independently. Unknown fields, other
   refs, filenames or repositories, and ambiguous checks fail closed.
2. Effective branch rulesets are currently unsupported and block authorization:
   their full review, status-check and bypass semantics cannot be established
   by this verifier. Use the legacy protection configuration above for these
   branches, or extend and validate the verifier before relying on rulesets.
   Configure `release-draft` and `release-publication` environments with required
   reviewers including an explicitly listed user, and self-review disabled; disable
   administrator bypass manually. Team-only reviewer configurations cannot be
   verified by this release tool.
   The write job also checks the run's actual independent environment approval.
   Because the approval API does not identify workflow attempts, release writes
   require attempt 1: dispatch a fresh workflow instead of re-running a failed
   job. Configure a read-only `RELEASE_AUDITOR_TOKEN` able to read branch protection,
   rulesets, environments, PR reviews, checks and Actions. Configure separately protected
   release tags and restrict credentials capable of modifying tags, releases,
   branch protections and environments. The authorization APIs fail closed if
   unavailable; the current repository setup is not assumed to provide them.
3. Dispatch **Coordinated release / dry-run** from the reviewed candidate ref.
   Non-publishing candidate plans may pin `candidate/*` or `maintenance/*` branches;
   strict release plans still require the authoritative `mc/*` branches.
   It verifies each candidate branch head, builds all pinned commits on Linux with JDK 25, runs each branch's build
   and Mixin/JAR verification, then verifies names, metadata, namespaces,
   bytecode, checksums and version synchronization. The resulting artifact is
   marked `candidate: true`; dry runs do not create tags or Releases.
4. After the plan and source branches are approved and their required runtime
   evidence exists, dispatch **prepare-draft** from `main`. The workflow checks
   protections, reviews, CI and branch heads, builds without write credentials,
   rechecks authorization after the `release-draft` environment review and immediately before each write, creates
   or verifies the one annotated tag at the plan commit, and prepares a draft.
   Existing tags at another commit, public releases, conflicting assets and
   incomplete bundles are rejected. Retrying an identical draft is safe.
5. Inspect the draft, notes, compatibility table, provenance manifest,
   `SHA256SUMS`, the JARs, and evidence. Then dispatch **publish** from the
   same unchanged `main` commit; the separately reviewed `release-publication`
   environment gates it. It rebuilds and checks the exact draft assets again.
   Any changed branch head, failed CI, missing review, missing report or conflicting
   tag blocks publication. The plan's release date and limitations appear in
   the draft; include breaking changes among the reviewed change notes.

Tag and release automation has not been exercised against the default branch or
GitHub-protected environments before review and integration. Repository rules,
secrets, environment approvals, manual graphical tests and the new coordination CI must
be verified by maintainers after integration. All three current maintenance heads
have successful hosted Linux and Windows CI; this does not supply runtime
attestations. GitHub does not provide a transaction spanning protection checks,
tag creation, asset uploads and release publication. A privileged actor can still change
state between the final API check and a write, or modify a draft after it was
inspected. The workflow rechecks before each write and checks draft metadata,
assets and tag immediately before publication, but cannot eliminate this race.
Restrict and monitor administrator, tag, release and environment permissions;
reviewers must inspect the exact draft and reports immediately before approval.
An existing changed draft is rejected rather than silently repaired.

## Adding a reviewed legacy group

`release/minecraft-runtime-requirements.json` records Mojang-declared runtimes
and metadata provenance. Update that reviewed inventory when adding a game
version; the plan rejects unknown versions and a mod Java target above a
member's game runtime. Each group declares a pinned `build_jdk` and expected
Mixin classes, and the release matrix selects that build JDK. Artifact checks
still enforce the declared runtime bytecode, required Mixins, namespace,
metadata, source, evidence and checksums. A build JDK can be newer than the
runtime target.

A candidate branch and static checks alone do not add release support. Add a
reviewed group to the compatibility configuration, plan, Dependabot and OSV
ledger only with its per-version runtime evidence and reviewed dependency
findings. Existing unresolved findings and all authorization gates remain.
