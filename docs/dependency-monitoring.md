# Dependency monitoring and coverage

Verified on 2026-11-04 against the initial maintained heads recorded in the
[maintenance report](maintenance-2026-11-04.md). Proposed maintenance PRs do not
change dependency versions or build resolution. Their hosted results must be
assessed separately from the existing merged branches.

## Responsibilities

| Mechanism | Responsibility | Limit |
| --- | --- | --- |
| Gradle resolution | Resolve each maintenance build's actual configurations | Does not prove every installed-runtime or build-plugin dependency is represented |
| Maintenance CI snapshot job | Generate and retain a per-source dependency snapshot for 14 days; validate wrapper | `generate-and-upload` does not submit to GitHub; permissions are read-only |
| Weekly central audit | Independently resolve each current maintenance head, retain its snapshot for 14 days and full advisory report for 30 days | Scheduled workflow only runs once this proposal is integrated on main; no historical successful scheduled run is claimed |
| Runtime manifests | Hash-verify authoritative Mojang metadata for all six supported game versions and query each listed Maven package/version | Includes all platform variants conservatively; classifier normalization does not audit native binary internals or unknown/non-Maven advisories |
| Dependabot version updates | Weekly wrapper and Actions updates on each mc branch; Actions on main | Observed Gradle jobs discovered only the wrapper, not all pinned Loader/Loom/Minecraft properties |
| Dependency Graph / native alerts | Default-branch dependency indexing and GitHub security alerts | An SBOM or non-default snapshot upload does not establish current maintenance-commit indexing or equivalent non-default security updates |
| Advisory ledger | Individual applicability review, stable identities, scope fingerprints, review expiry and follow-up | Reviewed unresolved findings are not risk acceptance or release approval |

`main/.github/dependabot.yml` is authoritative. GitHub reads configuration from
the default branch; `target-branch` selects manifests and PR bases for **version**
updates. Security updates always use the default branch and do not inherit those
non-default target options. The seven existing entries provide Gradle and Actions
for each maintenance branch and Actions on main, without a Gradle entry on main.
The three branch-local copies supply no additional supported coverage and are
removed in the proposed maintenance PRs. Schedules, limits and security features
are not disabled.

References checked during this round: [Dependabot configuration location](https://docs.github.com/en/code-security/how-tos/secure-your-supply-chain/manage-dependencies-security/configure-dependabot-security-updates),
[target-branch semantics](https://docs.github.com/en/code-security/reference/supply-chain-security/dependabot-options-reference#target-branch-),
[Gradle snapshot generation versus submission](https://github.com/gradle/actions/blob/main/docs/dependency-submission.md),
and [managed submission](https://docs.github.com/en/code-security/how-tos/secure-your-supply-chain/secure-your-dependencies/submit-dependencies-automatically).

## Per-branch monitoring matrix

PASS below refers only to the named mechanism. An expected audit failure caused
by unresolved advisories proves detection, not security clearance.

| Branch | Dependabot version updates | Dependency snapshots | GitHub graph submission | OSV scanning | Verified security coverage | Gaps |
| --- | --- | --- | --- | --- | --- | --- |
| mc/1.21.11 | Weekly configured; wrapper and Actions jobs succeeded at initial HEAD; no update needed | PASS: hosted run 41842279767 resolved, generated and retained artifact 13329208928; SHA/ref checked | Explicit CI does not submit; historical managed run succeeded; current indexed SHA UNVERIFIED | PASS detection: live proposed scanner, 86 Gradle packages and 53 runtime packages; 41 known unresolved matches, exit 1 | Version-level OSV coverage for represented packages; default-branch native alert details BLOCKED | Native binaries, omitted build-plugin dependencies, game reachability; current GitHub indexing unverified |
| mc/26.1-26.2 | Weekly configured; wrapper and Actions jobs succeeded at initial HEAD; no update needed | PASS: hosted run 41842370918, artifact 13329339275; SHA/ref checked | Explicit CI does not submit; historical managed run succeeded; current indexed SHA UNVERIFIED | PASS detection: 84 Gradle packages; runtime 53/53/53/57 for 26.1/26.1.1/26.1.2/26.2; 53 unresolved matches, exit 1 | Every advertised runtime manifest now queried locally with the proposed workflow's scanner | Prior 26.1-only snapshot missed changed 26.2 versions; scheduled integrated execution still pending; native/build-plugin gaps |
| mc/26.3 | Weekly configured; wrapper and Actions jobs succeeded at initial HEAD; no update needed | PASS: hosted run 41842321970, artifact 13330047089; SHA/ref checked | Explicit CI does not submit; historical managed run succeeded; current indexed SHA UNVERIFIED | PASS detection: 86 Gradle packages and 56 runtime packages; 11 unresolved matches, exit 1 | Version-level OSV detection for represented packages; default-branch alerts are not equivalent coverage | Same indexing, native binary, build-plugin and reachability limitations |

For each branch, the artifact was actually downloaded and its snapshot `sha` and
`ref` matched the maintained source. Resolution is also verified by clean local
candidate builds. Snapshot retention is verified from workflow policy and the
retrievable, non-expired hosted artifact. No local snapshot artifact is claimed
to populate the graph. The available SBOM endpoint returned a game dependency
inventory matching the former main build, including 1.21.11 mapped Minecraft and Netty 4.2.7; its metadata did not
bind the inventory to a source SHA/ref. Per-maintenance indexing is therefore
UNVERIFIED, not PASS. Native alert and security-update APIs returned 403.

## Effective version-update evidence

| Branch | Gradle run / inspected job | Actions run / inspected job | Observed result |
| --- | --- | --- | --- |
| mc/1.21.11 | 41853128695 / 126654493249 | 41853127855 / 126654487797 | Correct source SHA; wrapper 9.8.2 and all five referenced Actions current |
| mc/26.1-26.2 | 41853128170 / 126654488133 | 41853128298 / 126654491559 | Correct source SHA; wrapper 9.8.2 and all six referenced Actions current |
| mc/26.3 | 41853128945 / 126654492353 | 41853132293 / 126654504372 | Correct source SHA; wrapper 9.8.2 and all five referenced Actions current |

The jobs successfully fetched each branch and read its files. No open dependency
PR is expected for versions reported current. The earlier wrapper PR #2 shows
updates can be proposed, but does not prove that every custom pinned Gradle
property is understood. All three inspected Gradle logs checked **only the
wrapper**. Broader automatic version proposals for Loader/Loom/Minecraft are not
verified. Do not refactor working game dependency notation based on an untested
parser assumption. Maintainers must review stable upstream releases and pinned
`gradle.properties` during weekly dependency review; build and compatibility
checks remain mandatory for any update. Resolved security auditing covers the
represented runtime gap; it does not claim to solve build-plugin advisories.

## Runtime differences and individual findings

The hash-verified Mojang lists have 107 library entries on each of 26.1, 26.1.1,
and 26.1.2, with identical coordinates. Minecraft 26.2 has 131 entries, including
Netty 4.2.15 instead of 4.2.7, Log4j 2.26.0 instead of 2.25.2, and Guava
33.6.0-jre instead of 33.5.0-jre. Classifier normalization produces 53, 53, 53,
and 57 unique Maven package/version pairs. Static API compatibility does not
make those inventories identical. The proposed audit adds version-specific
runtime scopes to the existing central job rather than creating a second scan
workflow. The [inventory records](dependency-evidence/) retain coordinates,
manifest URL/hash, and maintenance source SHA; the [ledger](security-advisories.md)
records every advisory/package/version/group combination and review question.

A later runtime can resolve an older match without resolving the entire shared
compatibility group. For example, LZ4 1.10.1 resolves GHSA-cmp6-m4wj-q63q compared
with 1.21.11's 1.8.1, while other LZ4 advisories remain. Netty 4.2.15 resolves
several earlier Netty advisories but still has later ones. The ledger does not
collapse these observations into a whole-group clean bill of health.

## Recurring comparison and failure policy

`audit_dependencies.py` consumes the resolved snapshot, enumerates the configured
runtime versions, queries OSV, fetches every matched advisory's full data, and
compares against `docs/security-advisories.json`. The original strict snapshot
scanner remains available as a standalone tool and supplies the paginated OSV
query implementation.

- Identity is compatibility group + canonical Maven package/version + advisory
  ID. Repository qualifiers do not change identity; different package versions
  and groups do. Runtime scopes are independently compared.
- New IDs, newly affected versions/groups/scopes, and changed affected ranges,
  severity vectors/label, aliases, vulnerability details or withdrawn state fail
  and need review. A version range or alias change cannot inherit old approval.
- Known **Further investigation**, Actionable, Fixed or Resolved upstream matches
  still present, awaiting-investigation records, and high/critical or unknown
  upstream risks fail. Current results remain failing: 41/53/11 combinations.
- Unchanged, reviewed **Not applicable** records remain visible without failure.
  Explicit **Risk accepted** records additionally require named authorization and
  a decision reference. Reviewed low/moderate **Upstream-dependent** records may
  warn without failure; this is a follow-up category, not acceptance of release
  risk. No current record uses these non-failing categories.
- Missing packages from a reviewed scope, empty/missing inventories, skipped
  snapshot entries, invalid source binding, missing advisory data, OSV API/error
  responses, malformed/duplicate ledger records, or expired reviews fail as
  **incomplete** (exit 2). Missing data never means clean or resolved. Legitimate
  dependency removals need an inventory-baseline review.
- Previously recorded matches absent from a complete scan are reported as
  **disappeared and needing review**, and keep the gate failing. A reviewed
  `Fixed` or `Resolved upstream` record may be reported as resolved only when
  its `resolution_review` records a reviewer and evidence reference and binds
  the exact source SHA and `inventory_sha256` emitted by the scan. The digest
  covers sorted package URLs in every Gradle/runtime scope, excluding ephemeral
  job timestamps. A changed source or inventory requires renewed review. Records
  remain in history; no risk is automatically accepted. Reviews expire within
  90 days, or earlier on changed inputs/before release.

Exit 0 means the reporting policy has no failing matches, **not** release approval;
exit 1 means findings need action; exit 2 means incomplete/invalid execution. The
workflow always retains available reports and writes a summary distinguishing
new/changed/known/resolved results. A snapshot-generation failure has an explicit
incomplete summary even if no JSON report could be generated. All unresolved
findings stay visible in full artifacts. The original fail-on-every-match policy
was considered, but cannot distinguish new scope from reviewed scope. Blanket
baseline suppression was rejected because it would hide unresolved serious risk.

Regression tests cover new advisories, versions, compatibility groups and runtime
scopes, existing reviewed findings, changed ranges/severity, resolved matches,
missing data, API errors, incomplete inventories and malformed/stale baselines.
Actual local OSV executions returned complete reports with expected failing
findings for every branch. An integrated scheduled run is still NOT RUN.

## Administrative disposition

Automatic Dependency Submission is **C — blocked by settings access**. It was
still generating managed runs during this round. The exact administrator action,
feature-preservation checks, reversibility and read-back procedure are in
[administrative controls](administrative-controls.md#automatic-dependency-submission--final-disposition-c).
No alert or graph setting was disabled and no graph-submission success is inferred
from an uploaded artifact.


## Focused integration follow-up — 2026-11-05

The [review-resolution record](review-resolution-2026-11-05.md) verifies the current
PR source snapshots and both OS artifacts. PR #9's retained snapshot and a local
warm-cache run omitted `net.fabricmc/intermediary@1.21.11`; the unchanged baseline
correctly reported an incomplete Gradle inventory. Re-running the same pinned
detector with `--refresh-dependencies` restored the exact reviewed package/version
set. The central weekly workflow now uses that option to make Loom re-resolve
cached mappings. This costs additional resolution/network time, without changing
pinned dependencies, cache write permissions, expected packages, or advisory policy.
Per-commit artifacts remain useful inspection records, but a successful upload
still does not prove inventory completeness, Graph indexing, or a clean scan.
No raw PR snapshot was rewritten to claim a different source/ref.

## Legacy candidate scan — 2026-11-05

The [candidate OSV report](dependency-evidence/legacy-candidate-osv-2026-11-05.json)
contains hash-verified Mojang runtime inventories for 1.21.4–1.21.10 and the
retained Gradle snapshots from PRs #13 and #14. The snapshots report PR merge
refs, not maintenance heads or proof of a GitHub Dependency Graph submission.
The scan queried 112 distinct package/version pairs and retained full advisory
records and stable group/package/advisory identities. It found **52** candidate
matches for 1.21.4–1.21.8 and **59** for 1.21.9–1.21.10. All are marked new,
unreviewed, and failing; none has been accepted or suppressed. Overlapping
matches are counted once per group and may refer to the same advisory.

This evidence covers candidate snapshots at their recorded SHAs, not the
unmerged baseline maintenance branches. It does not replace the authoritative
reviewed ledger, establish exploitability, audit native binary internals, or
prove a successful scheduled audit. Triage every finding and regenerate the
snapshots and ledger for the actual reviewed maintenance heads before adding
those groups to the authoritative audit matrix or release configuration.

The proposed Dependabot configuration retains updates only for `main` and the
three integrated maintenance implementations. The ten candidate `mc/*`
branches currently contain the 1.21.11 baseline and are not update targets.
The separate [maintenance target registry](../release/maintenance-targets.json)
records integrated source commits independently of release admission. CI
checks the recorded commit is an ancestor of the target branch and that its
current Minecraft metadata matches before an entry can be activated. After a
reviewed port is merged and maintenance auditing covers that group, a follow-up
coordination PR can add its target and both Dependabot ecosystems. Candidate
monitoring remains separate. Version updates are not an OSV audit or a
security-risk disposition.

Additional candidate PR-merge-ref scans are retained in
[1.21.2–1.21.3 evidence](dependency-evidence/legacy-candidate-1212-osv-2026-11-05.json)
and [1.19.4–1.21.1 evidence](dependency-evidence/legacy-candidate-more-osv-2026-11-05.json).
They recorded 45, 28, 28 and 42 unreviewed group-scoped matches respectively
for 1.21.2–1.21.3, 1.21–1.21.1, 1.20.5–1.20.6 and 1.19.4–1.20.4. All are
failing pending individual review; overlapping package/advisory identities
can occur across groups. Re-scan the eventual reviewed maintenance heads.

The [older candidate scan](dependency-evidence/legacy-candidate-older-osv-2026-11-05.json)
uses retained PR merge-ref Gradle snapshots and hash-verified runtime inventories
for all members of PRs #20–#22. It records 53 matches for 1.17–1.19.2,
27 for 1.15–1.16.5 and 24 for 1.19.3. Every group-scoped match is unreviewed
and failing; none is accepted. The same advisory may occur in multiple groups.

The [1.14 candidate scan](dependency-evidence/legacy-candidate-114-osv-2026-11-05.json)
contains 27 unreviewed, failing group-scoped matches; none is accepted.

The [unreviewed review index](legacy-security-triage-2026-11-05.md) groups the retained matches by candidate, severity and inventory scope without changing their failing status.

## Proposed scheduled legacy-candidate audit

### Candidate-to-maintenance transition

The candidate evidence remains the historical index even after a port is
integrated. Its optional `monitoring` field defaults to `{"state":"candidate"}`:
the scheduled audit checks the exact `candidate_head` on `candidate/mc-<group>`.
Changed, unreviewed heads fail the job; the workflow never follows a mutable
head automatically. GitHub currently deletes merged head branches automatically.
If a candidate branch has disappeared, the source check permits continued scans
of the pinned candidate commit only when GitHub identifies the matching PR as
merged into the correct maintenance branch, that branch is still at the merge
commit, and the merge and candidate have identical Git trees. A missing,
unmerged, changed, or mismatched source fails visibly. This temporary scan is
still labeled candidate evidence; it is not a current maintenance snapshot.
If the maintenance branch advances, the temporary path fails until the reviewed
transition is recorded, rather than silently following the new head.

After a port is reviewed and integrated, a coordination PR can register its
actual merged maintenance commit in `release/maintenance-targets.json` and
set `monitoring` to `{"state":"integrated-transition","source_sha":"<commit>"}`.
The transition audit checks the exact registered `mc/<group>` commit, the
declared game versions and its own source-bound snapshot. This preserves
monitoring even when the merged candidate branch is deleted and does not imply
release admission or advisory approval. The retained candidate baseline is
still compared by advisory and inventory identity; missing packages and
disappeared findings require review. A squash merge need not retain the old
candidate commit as an ancestor, so this transition instead relies on the
reviewed integrated registry pin and verified maintenance metadata.

Only after authoritative maintenance auditing includes the exact group,
runtime inventories and reviewed ledger can the evidence record be marked
`{"state":"retired-authoritative"}`. The old candidate evidence remains
historical; it is not relabeled as a maintenance scan. The audit matrix is
allowed to become empty only after every such handoff is validated. A missing
registry entry, unpinned change, missing authoritative ledger scope or absent
maintenance audit matrix entry fails closed.

The separate [candidate workflow](../.github/workflows/candidate-dependency-audit.yml)
selects every group from the checked-in candidate evidence, checks out its
`candidate/mc-*` branch, and rejects a moved head. It generates a read-only
Gradle snapshot, validates the snapshot's actual ref and SHA and the source's
exact Fabric version list, and scans the hash-verified Mojang runtime inventory
for **every** declared game version. Unknown snapshot entries, source drift,
missing data, malformed advisories and network/API errors make the job
incomplete. The [unreviewed baseline](candidate-advisory-baseline.json) pins the retained
scan reports by SHA-256 and validates every group, source, runtime scope,
package and advisory fingerprint. Each baseline source must be an ancestor of
the exact checked-out candidate head; an unrelated or force-pushed history fails. The audit detects new, changed and known
matches, plus previously observed matches no longer returned by OSV. Every
current match remains unreviewed and failing, and disappeared matches also
fail until investigated. Missing inventory entries, modified reports and a
baseline older than 90 days fail closed. This workflow does not write the
reviewed ledger, accept risk, submit a Dependency Graph snapshot, or authorize
a release. Reports are retained for 30 days.

A local live execution used the [retained PR-merge-ref snapshot](dependency-evidence/candidate-audit-114-snapshot-2026-11-05.json)
for candidate commit `4ed41c5ff3a0bbd2a4eece0afc9de6c5e98ef0a8` and all five
1.14 runtime manifests. The [full report](dependency-evidence/candidate-audit-114-live-2026-11-05.json)
contains 27 unreviewed failing matches and the audit exited 1 as intended.
A [subsequent baseline comparison](dependency-evidence/candidate-audit-114-baseline-live-2026-11-05.json)
identified all 27 as known and still failing, with no disappeared matches.
The snapshot ref is preserved as `refs/pull/23/merge`; it is not relabeled as a
maintenance branch. The workflow is proposed on this PR: a hosted scheduled run
has **not** occurred. It starts only after coordination changes are integrated
on the default branch. Update the evidence pin when a candidate head changes;
retire a candidate entry only after its actual maintained head is covered by the
authoritative reviewed audit and ledger. A deleted branch qualifies for the
narrow merged-candidate continuation above only while its integration can be
proved; other missing or moved sources fail visibly rather than appearing clean.
