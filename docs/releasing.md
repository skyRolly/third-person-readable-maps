# Maintenance and coordinated releases

## Branches and review

`main` owns the release plan and workflows and continues to build its current
game implementation. The intended maintained branches are `mc/1.21.11` and
`mc/26.3`, each with its own exact game target, source, dependencies and Linux /
Windows CI. The existing `mc/1.21.11` starts at approved main commit `4810b1b`;
its proposed build changes are in PR #4. Protect and review the branches before
treating their new history as approved. PR #3 is unmerged: the 26.3 candidate in PR #5 is stacked on its
head, not silently incorporated into approved history. Review and integrate the
central changes first, preserve the approved 1.21.11 line in its maintenance
branch, then resolve any changes shared with PR #3 and review that port and its
stacked candidate. Create the 26.3 maintenance branch only from approved history.
Never merge automatically.

For a change, identify both groups, make a reviewable PR to each applicable
branch, adapt game-specific rendering where needed, and record whether each
change was applied, modified or deferred. Reviewers verify feature equivalence;
matching version strings or patch hashes alone are insufficient. Update the
shared `changes` list and each group's `verified_changes` in the release plan.
A coordinated release blocks on version drift or a missing group. A shared
module was considered, but the two Loom modes, namespaces and rendering APIs
already differ; independent small branches plus reviewed cherry-picks are less
complex here.

The proposed default-branch `.github/dependabot.yml` includes scheduled Gradle
and Actions version updates for `mc/1.21.11`. After `mc/26.3` exists, add
equivalent entries for that branch, e.g.:

```yaml
- package-ecosystem: gradle
  directory: /
  target-branch: mc/26.3
  schedule:
    interval: weekly
```

Add an equivalent `github-actions` entry for `mc/26.3`. Keep the default-branch entries and security
updates enabled. Version updates targeting non-default branches do not change the
separate default-branch behavior of Dependabot security updates.

## The release commit and global tag

A release uses one `X.X.X` mod version and one annotated tag of exactly that
name, without a `v` prefix. The tag points to the approved **main** commit
containing `release/plan.json`. That plan pins a source branch and full commit for every
compatibility group. Each JAR declares the same mod version but has a distinct
Minecraft classifier. The plan is an attestation reviewed alongside the source;
it must link to actual installed-JAR and graphical evidence for each advertised
Minecraft version, including Java 21 runtime evidence for 1.21.11. A URL is not
a machine proof of the test. Reviewers must inspect it and check hands,
dominant arms, map data, missing data, motion and first-person behavior.

`release/plan.example.json` is intentionally invalid: it contains zero SHAs and
no runtime evidence. Create `release/plan.json` in a reviewed PR, using exact
approved branch heads and a synchronized version and change list. Commit it to
`main` through review. `0.0.2` is the first candidate because there are no
existing tags or releases and PR #3 already uses it; if a published identity
appears before release, use a new version. Never move, overwrite or delete a
published tag to repair a release; issue a new version instead.

## Validation and publication

1. Give `main` and each maintenance branch protection requiring at least one
   approving PR review, stale-review dismissal, required CI, and enforcement for
   administrators. The selected head must be the merge commit of a reviewed PR
   into that branch with successful push CI for **both** `Build (ubuntu-latest)`
   and `Build (windows-latest)`.
2. Configure GitHub environments `release-draft` and `release-publication`, each
   with required reviewers. Configure the repository secret
   `RELEASE_AUDITOR_TOKEN` as a read-only GitHub App or fine-grained token able
   to read branch protection, environments, PR reviews and Actions runs. The
   workflow fails closed if these APIs or protections are unavailable. Configure
   branch/tag rules so unauthorized actors cannot create or move release tags.
3. Dispatch **Coordinated release / dry-run** from the reviewed candidate ref.
   It verifies each candidate branch head, builds both pinned commits on Linux with JDK 25, runs each branch's build
   and Mixin/JAR verification, then verifies names, metadata, namespaces,
   bytecode, checksums and version synchronization. The resulting artifact is
   marked `candidate: true`; dry runs do not create tags or Releases.
4. After the plan and source branches are approved and their required runtime
   evidence exists, dispatch **prepare-draft** from `main`. The workflow checks
   protections, reviews, CI and branch heads, builds without write credentials,
   rechecks authorization after the `release-draft` environment review, creates
   or verifies the one annotated tag at the plan commit, and prepares a draft.
   Existing tags at another commit, public releases, conflicting assets and
   incomplete bundles are rejected. Retrying an identical draft is safe.
5. Inspect the draft, notes, compatibility table, provenance manifest,
   `SHA256SUMS`, the two JARs, and evidence. Then dispatch **publish** from the
   same unchanged `main` commit; the separately reviewed `release-publication`
   environment gates it. It rebuilds and checks the exact draft assets again.
   Any changed branch head, failed CI, missing review, missing proof or conflicting
   tag blocks publication. The plan's release date and limitations appear in
   the draft; include breaking changes among the reviewed change notes.

Tag and release automation has not been exercised against the default branch or
GitHub-protected environments before review and integration. Repository rules,
secrets, environment approvals, hosted Windows and manual graphical tests must
be verified by maintainers after integration. The auditor token only checks
GitHub's exposed protection state; reviewers and repository administrators must
also govern ruleset bypasses and token permissions. The workflow itself does not
make an unprotected repository safe.
