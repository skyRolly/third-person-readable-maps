# 1.0.0 release-readiness gate matrix — 2026-11-13

**Not release-ready.** Version 1.0.0 is the coordinated proposal, not a
publication authorization. The [2026-11-04 gate history](release-readiness-2026-11-04.md)
and [historical 0.0.2 evidence](historical-0.0.2-2026-11-05/) remain intact.
The ten legacy `mc/*` targets are placeholders until their ports are reviewed
and integrated; an open PR is not an integrated branch.
The product PR heads advanced again during the [source-head transition](source-head-transition-2026-11-13.md);
checks and evidence on the preceding heads do not certify the new sources.

| Gate | Status | Evidence and remaining action |
|---|---|---|
| Coordination-only architecture | PASS | `main` owns coordination and no game Gradle project. Preserve that separation. |
| Compatibility grouping | PENDING REVIEW | Ten proposed legacy groups plus three integrated groups cover 48 explicit versions. No new split is proposed; independent acceptance remains. |
| Version synchronization | PENDING REVIEW | All 13 proposed product heads and the proposed coordinator use 1.0.0. The actual integrated branches remain 0.0.2 until reviewed PRs merge. |
| Static API verification | FAIL | The advanced product heads passed their recorded version-specific checks and controlled fixtures, but protected receiver dataflow, some `invokespecial` cases and other properties remain unproven. See the [review matrix](review-resolution-1.0.0.md). |
| Proposed-head Linux CI | PASS | All 13 new product heads passed `Build (ubuntu-latest)` on 2026-11-13; [exact-head checks](hosted-builds-verifier-followup-2026-11-13.json) are recorded. Repeat for changed and merged heads. |
| Proposed-head Windows CI | PASS | All 13 new product heads passed `Build (windows-latest)` on 2026-11-13; [exact-head checks](hosted-builds-verifier-followup-2026-11-13.json) are recorded. Repeat for changed and merged heads. |
| Coordination CI | BLOCKED | Local tests pass; the latest hosted check fails at the live integrated-verifier prerequisite. The three maintenance PRs must be integrated after review, then their exact merged heads and security evidence recorded before rerunning the check. |
| Installed-client startup | PASS | All 48 versions joined local worlds with the [proposed source-bound 1.0.0 JARs](runtime-smoke-verifier-followup-2026-11-13/) on Linux software rendering. The successful 26.2 and 26.3 retries saved and exited normally; prior failed or recovered attempts remain historical. This is a startup and short-walking check, not full graphical acceptance. |
| Rendering-state and map-ID correctness | FAIL | Targeted legacy probes support the texture, lighting and NBT guards, but all 19 component-era game codecs coerce the tested malformed numbers to zero. A [1.21.11 local-world probe](component-map-id-item-loading-2026-11-13/host-inventory-attempt/) also observed actual item loading and displayed map-zero terrain. Other item-loading paths and a bounded, independently reviewed remedy remain open. |
| Foreground anomaly investigation | BLOCKED | A [dropped-item control](foreground-item-entities-2026-11-13/) explains particular small shapes in one 1.21.11 scene. The large historical shape did not recur in limited candidate/no-mod comparisons; its original conditions were not reproduced and its cause remains unresolved. |
| Full graphical acceptance | NOT RUN | Controlled probes and partial screenshots do not cover all hands, poses, state restoration and first-person behavior on all final artifacts. Independent assessment is required. |
| Hardware-GPU testing | NOT RUN | Existing fresh diagnostic clients used Xorg/Mesa software rendering. |
| Multiplayer testing | NOT RUN | Remote-player and naturally unavailable map-data behavior require a multiplayer environment. |
| Security advisory disposition | FAIL | A [November 14 OSV re-query](dependency-evidence/osv-rescan-2026-11-14/) retained 490 unresolved, failing occurrences. The [individual worklist](dependency-evidence/current-security-worklist-2026-11-13.json) has no accepted risk; review each disposition and rescan approved merged heads. |
| Dependency monitoring | BLOCKED | Placeholder Dependabot targets are removed from the proposal, and source-bound snapshots and the [November 14 re-query](dependency-evidence/osv-rescan-2026-11-14/) cover the ten advanced candidate heads. Their findings remain unresolved; the transition to merged maintenance heads still needs independent review and fresh inventories. No risk is accepted. |
| Effective branch protection | FAIL | On [2026-11-14](admin/branch-rules-observation-2026-11-14.json) the branch API reported `protected: false` for `main` and all three existing maintenance branches; effective branch rules returned zero for each and the visible repository/parent ruleset list was empty. Administrator action and read-back are required. |
| Independent source approvals | PENDING REVIEW | The product and coordination PRs remain draft and unmerged; eligible independent reviewers must approve the final heads. |
| Reviewed and integrated source HEADs | PENDING REVIEW | No requested source PR was merged in this round. Integrate only after protection and independent review. |
| Exact merged-head CI | NOT RUN | No final merged heads exist yet. Require the Linux, Windows and coordination checks on the exact resulting commits. |
| Release environments | BLOCKED | Verify protected draft and publication environments and independent reviewers; previously unavailable settings are documented in administrative controls. |
| Independent deployment approval | BLOCKED | No deployment has been requested or approved. |
| Auditor access | BLOCKED | Configure and verify the read-only auditor credential through the administrator without exposing its value. |
| Tag protection | BLOCKED | A tag-only policy and authorized creation path require administrator review and read-back. No tag was created. |
| Runtime evidence | BLOCKED | Strict reports must bind every game version to the reviewed source commit and actual artifact SHA-256; local partial probes are insufficient. |
| Provenance and checksums | PENDING REVIEW | The new candidate aggregation and checksums identify all advanced product heads. Review them and repeat against final integrated, approved heads. |
| Non-publishing rehearsal | PENDING REVIEW | The [new local 13-group rehearsal](legacy-dry-run-1.0.0.md) passed candidate aggregation and negative controls on the advanced heads. A hosted rehearsal against approved integrated heads remains NOT RUN. |
| Live release authorization | FAIL | Security, integration, protection, review and runtime gates above are unsatisfied. |
| Draft preparation readiness | BLOCKED | The owner has not authorized draft creation, and prerequisite gates are unsatisfied. |
| Public publication readiness | BLOCKED | No approved draft or separate publication authorization exists. |

## Safe future integration sequence

1. Establish and verify effective branch protections and eligible independent
   reviewers. Review the three separate 1.0.0 maintenance PRs and the ten legacy
   ports. Resolve findings before any integration.
2. After independent approval, integrate the three existing maintenance PRs,
   verify exact merged-head Linux and Windows checks, update the registry to
   those exact merged heads, and refresh their source-bound security evidence.
   Recheck the proposed coordinator's live prerequisites. Review and integrate
   coordination PR #15 without activating any legacy placeholder target.
3. Integrate a reviewed legacy port only with its candidate audit covered. The
   repository currently auto-deletes merged PR branches; the candidate audit
   can continue using the exact candidate commit only while the merged target
   has the identical tree and has not advanced. Promptly review a follow-up
   coordination PR that pins the actual merged maintenance commit, changes the
   group to `integrated-transition`, and activates that branch's Dependabot
   Gradle and Actions entries. Changed or unprovable source fails closed.
4. Keep the group in transition monitoring until an authoritative audit matrix,
   runtime inventories and reviewed ledger cover it. Release configuration
   admission is a separate reviewed decision after its acceptance gates pass.
5. Reconcile dependency-update PRs against updated targets, refresh all runtime
   evidence and advisory dispositions, run exact-merged-head CI and a fresh
   non-publishing rehearsal, then independently evaluate release authorization.
   A later owner instruction is required before draft or public release actions.

The [workflow API](dependency-evidence/automatic-submission-state-2026-11-14.json)
reported GitHub-managed Automatic Dependency Submission `active` on 2026-11-14.
It ran successfully on all 13
advanced product heads on [2026-11-13](dependency-evidence/automatic-submission-2026-11-13.json);
the separate settings toggle has not been independently read back.
The existing administrative disposition requires the administrator to disable
that managed submission while preserving Dependency Graph, Dependabot alerts
and security updates; verify the setting and subsequent run history separately
from the repository's Maintenance Dependency Audit. See
[administrative controls](administrative-controls.md).
