# 1.0.0 release-readiness gate matrix — updated 2026-11-16

**Not release-ready.** Version 1.0.0 is the coordinated proposal, not a
publication authorization. The [2026-11-04 gate history](release-readiness-2026-11-04.md)
and [historical 0.0.2 evidence](historical-0.0.2-2026-11-05/) remain intact.
The [November 13 gate snapshot](https://github.com/skyRolly/third-person-readable-maps/blob/1d47857ae681c5493914a032788d80e644466c02/docs/release-readiness-1.0.0.md)
remains available at its original commit.
The ten legacy `mc/*` targets are placeholders until their ports are reviewed
and integrated; an open PR is not an integrated branch.
The [current evidence selection](version-consistency-1.0.0/current-evidence.json) identifies the updated proposal heads. Final clean-build, CI and rehearsal evidence is being refreshed. The 1.14 correction changes the JAR; its earlier runtime observations remain historical and cannot establish current-artifact acceptance.

| Gate | Status | Evidence and remaining action |
|---|---|---|
| Coordination-only architecture | PASS | `main` owns coordination and no game Gradle project. Preserve that separation. |
| Compatibility grouping | PENDING REVIEW | Ten proposed legacy groups and proposals for three existing maintenance groups cover 48 explicit versions. No new split is proposed; independent acceptance remains. |
| Version synchronization | PENDING REVIEW | All 13 proposed product heads and the proposed coordinator use 1.0.0. The actual integrated branches remain 0.0.2 until reviewed PRs merge. |
| Wrapper build security | PENDING REVIEW | Canonical preflight remains in place. Final-head hosted runs and independent review are pending. |
| Verification implementation | PENDING REVIEW | Discriminating JVM and packaged-entry-point fixtures cover the shared corrections. The bounded contract explicitly rejects unproven platform-member inheritance and other unsupported patterns; independent review remains required. |
| Current artifact static compatibility | PENDING REVIEW | The corrected verifier has completed the 48-version sweep; final clean-artifact identity and source-bound evidence are being reconciled. |
| Proposed-head Linux CI | NOT RUN | New proposed heads are queued for Linux CI; previous-head passes do not certify them. |
| Proposed-head Windows CI | NOT RUN | New proposed heads are queued for Windows CI; previous-head passes do not certify them. |
| Coordination CI | BLOCKED | Coordination tests and workflow lint now run independently of a separate live-release prerequisite job. The latter remains blocked while integrated maintenance sources lack the proposed verifier and version; strict release authorization requires both checks and rechecks the live sources. |
| Installed-client startup | PENDING REVIEW | Earlier local-world observations retain their original source and artifact identities. The corrected 1.14 JAR has a targeted instrumented software-GL diagnostic; full current-artifact and approved-source acceptance remains open. |
| Rendering-state and map-ID correctness | PENDING REVIEW | Targeted legacy probes support the texture, lighting and NBT guards. All 19 component-era codecs normalize the tested malformed numbers to zero before rendering; paired candidate/no-Mod loading controls found matching behavior. No additional Mod-specific discrepancy is established by those controls. Remaining synchronization, graphical and independent acceptance requirements are tracked separately. |
| Owner acceptance of map-ID contract | PENDING REVIEW | The proposed contract preserves the typed ID supplied by Minecraft, including valid zero; owner review and any decision about broader decoding changes remain outstanding. |
| Foreground anomaly investigation | BLOCKED | A [dropped-item control](foreground-item-entities-2026-11-13/) explains particular small shapes in one 1.21.11 scene. The large historical shape did not recur in limited candidate/no-mod comparisons; its original conditions were not reproduced and its cause remains unresolved. |
| Full graphical acceptance | NOT RUN | Controlled probes and partial screenshots do not cover all hands, poses, state restoration and first-person behavior on all final artifacts. Independent assessment is required. |
| Hardware-GPU testing | NOT RUN | Existing fresh diagnostic clients used Xorg/Mesa software rendering. |
| Multiplayer testing | BLOCKED | A later [instrumented 1.21.11 LAN repeat](multiplayer-smoke-2026-11-14/instrumented-2026-11-15/) observed the renderer's map-ID-2 lookup return no data before the host gave that map to the observer and data in the same second as the give command. Packets were not instrumented; the earlier observation, other versions, broader interactions and independent multiplayer acceptance remain open. |
| Security advisory disposition | FAIL | The retained scans report 385 failing candidate and 105 failing integrated occurrences, plus 105 separately scoped unmerged-proposal occurrences. The [critical Netty TLS review](dependency-evidence/advisory-dispositions/netty-critical-tls-2026-11-15.json) advances 10 candidate, four integrated and four separately scoped unmerged-proposal matches; it establishes neither reachability nor a fix. Earlier Log4j and Netty investigations remain open; no risk is accepted. |
| Dependency monitoring | BLOCKED | Proposal-head inventories and audits were refreshed, and placeholder Dependabot targets are absent. The lifecycle transition and authoritative monitoring for each eventual merged source require reviewed activation; unresolved findings continue failing. |
| Effective branch protection | FAIL | On [2026-11-15](admin/branch-rules-observation-2026-11-15.json) the branch API reported `protected: false` for all 14 existing and intended targets; visible effective branch rules and repository/parent rulesets were empty. Detailed legacy protection settings were inaccessible. Administrator action and read-back are required. |
| Independent source approvals | PENDING REVIEW | The 13 product PRs are ready for review; the coordinator's review status follows its final ordinary CI. All remain unmerged and eligible independent reviewers must approve the final heads. |
| Reviewed and integrated source HEADs | PENDING REVIEW | No requested source PR was merged in this round. Integrate only after protection and independent review. |
| Exact merged-head CI | NOT RUN | No final merged heads exist yet. Require the Linux, Windows and coordination checks on the exact resulting commits. |
| Release environments | BLOCKED | The refreshed environments API returned zero visible environments. An administrator must create or verify the protected draft and publication environments and independent reviewers, then read the settings back. |
| Independent deployment approval | BLOCKED | No deployment has been requested or approved. |
| Auditor access | BLOCKED | Configure and verify the read-only auditor credential through the administrator without exposing its value. |
| Tag protection | BLOCKED | A tag-only policy and authorized creation path require administrator review and read-back. No tag was created. |
| Runtime evidence | BLOCKED | Strict reports must bind every game version to the reviewed source commit and actual artifact SHA-256; local partial probes are insufficient. |
| Provenance and checksums | PENDING REVIEW | Previous candidate provenance is historical; final proposed-source and artifact evidence is being refreshed. |
| Non-publishing rehearsal | NOT RUN | A fresh rehearsal is required for the updated proposal sources and changed 1.14 artifact; prior rehearsal remains historical. |
| Live release authorization | FAIL | Security, integration, protection, review and runtime gates above are unsatisfied. |
| Draft preparation readiness | BLOCKED | The owner has not authorized draft creation, and prerequisite gates are unsatisfied. |
| Public publication readiness | BLOCKED | No approved draft or separate publication authorization exists. |

## Safe future integration sequence

1. Establish and read back baseline protection and eligible independent
   reviewers. Review the narrow 0.0.2 security PRs #34–#36 first. Protect each
   intended legacy target before its port is integrated; protection alone does
   not activate the placeholder or its dependency monitoring.
2. After independent approval and owner-controlled integration of #34–#36,
   update #31–#33 from their new bases without rewriting history, resolve the
   documented conflicts, and obtain fresh review and exact-head checks. After
   their integration, refresh source-bound security evidence and recheck the
   coordinator's live prerequisites. Integrate #15 under the baseline main
   policy, then require and read back both final main checks before any strict
   release authorization. See [the staged protection procedure](administrative-controls.md).
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
