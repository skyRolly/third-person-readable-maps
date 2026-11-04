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
- Successfully scanned matches absent from current results are reported as
  resolved; records are retained for history. No risk record is automatically
  deleted, approved, or reclassified. Reviews expire within 90 days, or earlier
  on changed inputs/before release. The current review deadline is 2027-02-02.

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
