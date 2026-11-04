# Maintenance and coordinated releases

## Branches and review

`main` owns the release plan and workflows and continues to build its current
game implementation. The intended maintained branches are `mc/1.21.11`,
`mc/26.1-26.2` and `mc/26.3`, each with its own game targets, source, dependencies and Linux /
Windows CI. The existing `mc/1.21.11` starts at approved main commit `4810b1b`;
its proposed build changes are in PR #4. Protect and review the branches before
treating their new history as approved. PR #3 is unmerged: the 26.3 candidate in PR #5 is stacked on its
head, not silently incorporated into approved history. Review and integrate the
central changes first, preserve the approved 1.21.11 line in its maintenance
branch, then resolve any changes shared with PR #3 and review that port and its
stacked candidate. The 26.1–26.2 port in PR #7 is reviewed against a separate candidate
base at PR #3’s head; do not merge it into the 26.3 modernization branch.
Create both 26.x maintenance branches only from approved history.
Never merge automatically.

For a change, identify all groups, make a reviewable PR to each applicable
branch, adapt game-specific rendering where needed, and record whether each
change was applied, modified or deferred. Reviewers verify feature equivalence;
matching version strings or patch hashes alone are insufficient. Update the
shared `changes` list and each group's `verified_changes` in the release plan.
A coordinated release blocks on version drift or a missing group. A shared
module was considered, but the two Loom modes, namespaces and rendering APIs
already differ; independent small branches plus reviewed cherry-picks are less
complex here.

The proposed default-branch `.github/dependabot.yml` includes scheduled Gradle
and Actions version updates for `mc/1.21.11`. After the 26.x branches exist, add
equivalent entries for each branch, e.g.:

```yaml
- package-ecosystem: gradle
  directory: /
  target-branch: mc/26.1-26.2
  schedule:
    interval: weekly
```

Add `github-actions` coverage for that branch and both ecosystems for `mc/26.3`.
Keep the default-branch entries and security
updates enabled. Version updates targeting non-default branches do not change the
separate default-branch behavior of Dependabot security updates.

## The release commit and global tag

A release uses one `X.X.X` mod version and one annotated tag of exactly that
name, without a `v` prefix. The tag points to the approved **main** commit
containing `release/plan.json`. That plan pins a source branch and full commit for every
compatibility group. Each JAR declares the same mod version but has a distinct
Minecraft classifier. The plan is an attestation reviewed alongside the source;
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
hash and coordinator commit; its report path resolves in that commit.

`release/plan.example.json` is intentionally invalid: it contains zero SHAs and
no runtime evidence. Create `release/plan.json` in a reviewed PR, using exact
approved branch heads and a synchronized version and change list. Commit it to
`main` through review. `0.0.2` is the first candidate because there are no
existing tags or releases and PR #3 already uses it; if a published identity
appears before release, use a new version. Never move, overwrite or delete a
published tag to repair a release; issue a new version instead.

## Validation and publication

1. Configure legacy branch protection for `main` and every maintenance branch:
   require a PR with at least one approval, stale-review dismissal, strict checks,
   administrator enforcement, no PR-review bypass actors (the API must expose empty user, team and app
   lists), no force pushes and
   no deletions. Require exactly named `Build (ubuntu-latest)` and
   `Build (windows-latest)` checks from the GitHub Actions app (ID 15368); pin
   every additional required check to its app as well. The head must be the
   merge commit of a PR into that branch with the required number of independent,
   non-dismissed approvals from currently write-authorized reviewers on the final
   PR head and the latest push CI run and
   its current attempt successful on both operating systems. The current
   required checks must also succeed. Rerun all jobs if a partial retry does not
   provide both jobs in the latest attempt. Unknown API fields and ambiguous
   checks fail closed.
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
   job. The read-only `RELEASE_AUDITOR_TOKEN` to read branch protection, rulesets,
   environments, PR reviews, checks and Actions. Configure separately protected
   release tags and restrict credentials capable of modifying tags, releases,
   branch protections and environments. The authorization APIs fail closed if
   unavailable; the current repository setup is not assumed to provide them.
3. Dispatch **Coordinated release / dry-run** from the reviewed candidate ref.
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
secrets, environment approvals, hosted Windows and manual graphical tests must
be verified by maintainers after integration. GitHub does not provide a transaction spanning protection checks, tag creation,
asset uploads and release publication. A privileged actor can still change
state between the final API check and a write, or modify a draft after it was
inspected. The workflow rechecks before each write and checks draft metadata,
assets and tag immediately before publication, but cannot eliminate this race.
Restrict and monitor administrator, tag, release and environment permissions;
reviewers must inspect the exact draft and reports immediately before approval.
An existing changed draft is rejected rather than silently repaired.
