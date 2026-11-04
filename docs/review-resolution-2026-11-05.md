# PR #9–#12 review resolution — 2026-11-05

**Ready for independent human review; integration remains conditional on eligible
approval and repository controls. Release remains blocked.** This is a focused
correction to the proposed maintenance work. None of the PRs is merged, no
auto-merge is enabled, and no tag, Release, collaborator permission, environment,
secret or administrative security setting was changed.

The [review evidence](review-resolution-evidence-2026-11-05.json) preserves fresh
permission and PR/CI observations separately from the unchanged
[historical evidence](maintenance-evidence-2026-11-04.json). The supplied findings
were not present as submitted reviews or inline threads in the accessible GitHub
responses at inspection; resolution notes are posted to each PR conversation.
Those notes are not approval records.

## A. Review dispositions

| PR | Finding | Investigation result | Action | Verification |
| --- | --- | --- | --- | --- |
| #12 | Reviewer eligibility evidence conflicts | Confirmed: historical and fresh responses both report ZDN-1942 with Write; triage:true was incorrectly treated as the highest role | Correct administrative, readiness and maintenance reports; retain original evidence unchanged and add a dated correction record | Effective permission endpoint and collaborator list agree; original evidence digest unchanged; existing verifier accepts a hypothetical non-author current-head Write approval but rejects missing/stale/self approvals |
| #9 | Documentation links await coordination changes | Confirmed and satisfied by intended integration: two central files are introduced by #12 | Retain permanent main URLs; explicitly require #12 first in PR description/discussion; no README/source commit needed | Targets exist in the proposed coordination tree; merged main returns404 for the two new files and200 for the existing files |
| #10 | Documentation links await coordination merge | Same dependency as #9; four-version build and API checks are independent of the documentation | Same prerequisite and permanent-link resolution; no README/source commit needed | All four targets verified; current Linux/Windows API steps succeeded; local unsupported-version checks still reject1.21.11/26.3 |
| #11 | Equivalent dependency discovered during this review | The same monitoring/ledger links depend on #12 even though not separately flagged | Record equivalent prerequisite in description/discussion; preserve harmonized README | Same link and source-tree validation as #9/#10 |
| #12 | Additional integration check: cached mapping dependency absent from #9 snapshot | The retained PR snapshot and a local warm-cache detector run contain85 packages, missing net.fabricmc/intermediary@1.21.11; the86-package reviewed inventory correctly rejects them as incomplete | Add --refresh-dependencies to the central audit resolution command; retain all mandatory packages and advisory records | Same pinned detector with refresh restored the exact86-package baseline, with no version update; full refresh resolution is validated across the proposed sources. PR snapshots remain intact and are not re-labelled |

## B. Reviewer eligibility and independence

The original response records `role_name: write`, `permissions.push: true`,
`permissions.triage: true`, `permissions.admin: false`. A fresh effective-permission
GET and collaborator-list GET again return Write. The previous conclusion was an
interpretation error; these observations do not establish any intervening
permission change. The historical file's SHA-256 remains
`6d173711bd67a31c5f9a528c89bb3dbff546963c7840ece0570841e60b1b2a1c`.

ZDN-1942 is **potentially eligible for independent source review**. GitHub required
reviews accept eligible writers, and this repository's authorization implementation
accepts `write`, `maintain`, or `admin` with a qualifying non-author approval on
the exact source head before merge. All four PR authors are skyRolly; current PR
commits are associated with skyRolly as author/committer, and the inspected CI
actor/triggering actor is skyRolly. No current-head PushEvent was present in the
accessible public event page. The exact last git-push actor is therefore not
independently established; CI or commit identity is not a substitute for a push
audit record.

Distinct account identities do not prove personal independence or lack of
involvement/conflicts. Availability, owner authorization and any additional owner
policy need human confirmation. No accessible repository policy specifically
disqualifies this collaborator, but absence of such evidence is not an appointment.
No submitted review exists on any of PRs #9–#12 at inspection. No reviewer was
selected, requested or promoted by this task.

The same person could technically perform separate deployment reviews if the
owner explicitly lists them in the environment and confirms independence from
both the future run actor and triggering actor. GitHub's minimum environment
reviewer permission is read. The verifier imposes no additional rule requiring a
different person from the source reviewer, but separate actual approvals for the
release stages and any stronger owner separation policy remain mandatory. A
reviewer who triggers the release cannot independently approve that dispatch.
The missing environments are still a blocker, not satisfied by Write access.

Nine focused **offline fixture checks**, using the fresh Write response, exercised
these existing acceptance/rejection rules. They did not submit approvals or test
live deployment authorization. The production authorization code is unchanged.

## C. Documentation dependencies

| PR | Referenced document | Exists on merged main | Exists in #12 | Integration result |
| --- | --- | --- | --- | --- |
| #9 | docs/dependency-monitoring.md | No; HTTP404 | Yes | Resolves after #12 integration |
| #9 | docs/security-advisories.md | No; HTTP404 | Yes | Resolves after #12 integration |
| #9 | docs/compatibility.md | Yes; HTTP200 | Yes, revised | Permanent main URL remains authoritative |
| #9 | docs/releasing.md | Yes; HTTP200 | Yes, revised | Permanent main URL remains authoritative |
| #10 | docs/dependency-monitoring.md | No; HTTP404 | Yes | Resolves after #12 integration |
| #10 | docs/security-advisories.md | No; HTTP404 | Yes | Resolves after #12 integration |
| #10 | docs/compatibility.md | Yes; HTTP200 | Yes, revised | Permanent main URL remains authoritative |
| #10 | docs/releasing.md | Yes; HTTP200 | Yes, revised | Permanent main URL remains authoritative |
| #11 | docs/dependency-monitoring.md | No; HTTP404 | Yes | Resolves after #12 integration |
| #11 | docs/security-advisories.md | No; HTTP404 | Yes | Resolves after #12 integration |
| #11 | docs/compatibility.md | Yes; HTTP200 | Yes, revised | Permanent main URL remains authoritative |
| #11 | docs/releasing.md | Yes; HTTP200 | Yes, revised | Permanent main URL remains authoritative |

The four files describe shared coordination policy, not one branch's independent
configuration. Their monitoring limitations, unresolved advisory status and
version-specific compatibility remain explicit. Relative README links, permanent
central URLs, exact common title/introduction, maintenance heading order and
branch-specific badges were checked in the proposed combined file trees. No
candidate-branch URL was substituted. No README edit or new commit is needed on
#9–#11 to fix this integration-order finding.

## D. Safe future integration order

1. Confirm an independent, available and owner-authorized source reviewer. Existing
   Write access does not require automatic promotion. Under separately authorized
   administration, configure/read back the required protections and app-pinned
   checks without introducing bypasses. Obtain actual exact-head approvals.
2. **Integrate #12 into main first**, after its final-head Validate coordination
   check and independent review. Verify the resulting main push check and that
   the four permanent document URLs resolve on merged main.
3. **Integrate #9, #10 and #11 in any order** after their own independent reviews
   and current Linux/Windows checks. They otherwise remain independently
   buildable: no Java, Gradle/Fabric version, rendering, required job identity or
   compatibility change depends on the new coordination code. Central Dependabot
   configuration was already authoritative before these PRs.
4. Verify both required push jobs on every new maintenance merge head. A PR-head
   run cannot replace merged-head push evidence. Refresh any stale approvals after
   changes; do not retrofit approvals onto old unreviewed merge commits.
5. Complete the separate administrative, security, runtime-evidence and live
   authorization gates before any release activity. Cleanup integration is not
   authorization to prepare a draft or publish.

Local proposed integration uses detached exported merge trees; no protected
branch or approved merge commit is manufactured. Candidate release plans pin the
actual proposed maintenance refs/SHAs and are explicitly non-publishing. The
central weekly workflow continues to check out the real mc branches; it does not
claim those branches already contain unmerged improvements.

## E. Validation and source scope

| PR | Maintenance/coordination source at inspection | Hosted run, latest attempt1 | Result |
| --- | --- | --- | --- |
| #9 | 7779e3a89849cdaf3b08aa536b79d8c238fa1874 |41862276302| Linux, Windows and snapshot jobs SUCCESS |
| #10 | e1bce43c0f370fb28bbf87ba974c8d1582c85fb0 |41862279700| Linux, Windows, both four-version API steps and snapshot job SUCCESS |
| #11 | dd43b41d3c4134430a57cc8eed0cc522249a614c |41862283894| Linux, Windows and snapshot jobs SUCCESS |
| #12 | Originally reviewed8ef5e97b61ca817f8a85727322724000595e2533 |41864569719| Original head SUCCESS; review corrections require their own exact-head result |

All run identities were checked for source SHA, pull_request event, expected base,
ci.yml workflow, current attempt and named jobs. GitHub Actions publishes the
required checks. Downloaded Linux and Windows JARs for all three groups passed
metadata, namespace, license, bytecode and classifier inspection and were
byte-identical across operating systems. Cache logs confirm Gradle PR state was
read-only and entries were not saved. Snapshot uploads are retention evidence,
not Graph submission or security clearance.

Local focused checks include Python compilation, all53 coordination/release/audit
tests, workflow lint, strict JSON parsing, unchanged compatibility/build/security
contracts, README dependencies, and source/approval negative tests. The shared JAR
again passed all four advertised APIs and rejected1.21.11 and26.3. No game rebuild
was needed because the maintenance source heads and hosted artifacts are unchanged.
The final coordination commit and fresh CI result are recorded in the PR discussion
and handoff rather than treating run41864569719 as evidence for later commits.

The additional snapshot check reproduced a real warm-cache omission with the
same pinned dependency detector. The central workflow now re-resolves dependencies
with --refresh-dependencies, so the detector observes cached Loom mapping inputs.
This adds resolution/network work to the scheduled audit; it changes no pinned
version or game build. No package was removed from the expected inventory, and
no new ignored-package or advisory-suppression mechanism was added. An unchanged
incomplete PR snapshot is still rejected by the strict audit. Locally generated
proposed-integration snapshots identify the actual candidate SHA and a logical
future mc ref, with a local job identifier; they are explicitly fixtures, not
GitHub-indexed snapshots or evidence of current protected-branch contents.

All six supported runtime manifests, full OSV advisory records, stable identities,
changed/new/resolved handling and failure on incomplete scans remain in place.
The ledger still contains40 unique advisories and105 affected combinations, all
Further investigation, with zero accepted risks. Successful candidate aggregation
and checksum checks do not override strict production source/runtime requirements
or live protection and environment failures.

## F. Remaining gates and handoff

The categorical reviewer-absence blocker is replaced by conditional eligibility;
source approval stays **PENDING REVIEW**. Hosted Windows execution is no longer
blocked for the unchanged maintenance proposals; release-source Linux/Windows
readiness stays **PENDING REVIEW** until approved integration and new push checks.
Branch protection remains **FAIL**; environments are missing, auditor access and
tag policy remain blocked, and Automatic Dependency Submission remains disposition
**C**. Security disposition remains **FAIL** and source-bound graphical evidence
remains **BLOCKED**. Live release authorization has not passed.

See the reconciled [administrative controls](administrative-controls.md),
[maintenance handoff](maintenance-2026-11-04.md), and
[27 release gates](release-readiness-2026-11-04.md). Review notes and fresh CI
results are attached to the existing PRs. No independent approval, authorized
merge, repository setting change or release action is implied.
