# Legacy candidate review handoff

All entries below are **draft candidates**, not integrated support or release acceptance. The [version inventory](legacy-version-inventory.md) has one row per historical stable version; [candidate evidence](legacy-candidate-evidence.json) records JAR names, digests, source commits, static checks, runtime results and limitations. Every candidate currently passes its per-version static linkage checks.

| Group and PR | Explicit versions | Runtime Java | Candidate head | Versions with installed-world map smoke |
|---|---|---:|---|---|
| [1.14-1.14.4](https://github.com/skyRolly/third-person-readable-maps/pull/23) (#23) | 1.14, 1.14.1, 1.14.2, 1.14.3, 1.14.4 | 8 | `4efda773683abb558d29614bf5227c3cf8022bf2` | all |
| [1.15-1.16.5](https://github.com/skyRolly/third-person-readable-maps/pull/21) (#21) | 1.15, 1.15.1, 1.15.2, 1.16, 1.16.1, 1.16.2, 1.16.3, 1.16.4, 1.16.5 | 8 | `18f59f3f20faa89656e29ab836439f9f304fabcd` | all |
| [1.17-1.19.2](https://github.com/skyRolly/third-person-readable-maps/pull/20) (#20) | 1.17, 1.17.1, 1.18, 1.18.1, 1.18.2, 1.19, 1.19.1, 1.19.2 | 16 (1.17–1.17.1); 17 (1.18+) | `b216d231e84d8e224f19a405a54b889c3de74b25` | all |
| [1.19.3](https://github.com/skyRolly/third-person-readable-maps/pull/22) (#22) | 1.19.3 | 17 | `6405f8bbcf481bed760d7de73ca01d0f3e86e55c` | all |
| [1.19.4-1.20.4](https://github.com/skyRolly/third-person-readable-maps/pull/19) (#19) | 1.19.4, 1.20, 1.20.1, 1.20.2, 1.20.3, 1.20.4 | 17 | `4df429e9a32da098b9bebd52f70989aa445245b0` | all |
| [1.20.5-1.20.6](https://github.com/skyRolly/third-person-readable-maps/pull/18) (#18) | 1.20.5, 1.20.6 | 21 | `ec3f2a51d8afc7b0a1911cdc6cae88fe00e2b917` | all |
| [1.21-1.21.1](https://github.com/skyRolly/third-person-readable-maps/pull/17) (#17) | 1.21, 1.21.1 | 21 | `253e4600e94a5c05da81cb5d4bf700d5b7a7117d` | all |
| [1.21.2-1.21.3](https://github.com/skyRolly/third-person-readable-maps/pull/16) (#16) | 1.21.2, 1.21.3 | 21 | `63338bbd9c3634e27a9a42e3025a8a3279301bbe` | all |
| [1.21.4-1.21.8](https://github.com/skyRolly/third-person-readable-maps/pull/14) (#14) | 1.21.4, 1.21.5, 1.21.6, 1.21.7, 1.21.8 | 21 | `e15fd43aba735760d37f61427a52e0a6305d1022` | all |
| [1.21.9-1.21.10](https://github.com/skyRolly/third-person-readable-maps/pull/13) (#13) | 1.21.9, 1.21.10 | 21 | `aa319a0ea75dd62eb23aa2d44dda3b827de973b5` | all |

| Group | Candidate JAR | SHA-256 |
|---|---|---|
| 1.14-1.14.4 | `third-person-readable-maps-0.0.2-mc1.14-1.14.4.jar` | `839f0982d11c0a0f95199e1486f7ece203acb7fe8f3e2dd309e9edec214ce5a5` |
| 1.15-1.16.5 | `third-person-readable-maps-0.0.2-mc1.15-1.16.5.jar` | `d30a2a682699e881903275ce373d79374b1475e5dff10e7b3e66d364819b13de` |
| 1.17-1.19.2 | `third-person-readable-maps-0.0.2-mc1.17-1.19.2.jar` | `aee00518a1a5b3c31cf794063ac685aa2675ac0b719f11d2b50d0ec8ccf351e6` |
| 1.19.3 | `third-person-readable-maps-0.0.2-mc1.19.3.jar` | `f7288ad9a7f73f718176db15f185bab10d8a02548b02e2f4a943aac06f0db16b` |
| 1.19.4-1.20.4 | `third-person-readable-maps-0.0.2-mc1.19.4-1.20.4.jar` | `7b6e18ebce73045fb937640a1edc0b364a6b13f6bb66941f0c209a204cab0af9` |
| 1.20.5-1.20.6 | `third-person-readable-maps-0.0.2-mc1.20.5-1.20.6.jar` | `8c02fa2fc1b565e8154926642ac4fa260b28f59aeca8a49f9958a8d39050cdfd` |
| 1.21-1.21.1 | `third-person-readable-maps-0.0.2-mc1.21-1.21.1.jar` | `d4054952d77a3b4dc79d7681779126cf38bd0fb34c1f9afd3346ceb9f4ca4745` |
| 1.21.2-1.21.3 | `third-person-readable-maps-0.0.2-mc1.21.2-1.21.3.jar` | `28a15aacf531dfdb3dd51ba63b7e9cf42000e0b981d863cdc0c27bebc89523e4` |
| 1.21.4-1.21.8 | `third-person-readable-maps-0.0.2-mc1.21.4-1.21.8.jar` | `26a28fb550132d07af415c41ccb82982937906ab991ad810406d2937b5e4e776` |
| 1.21.9-1.21.10 | `third-person-readable-maps-0.0.2-mc1.21.9-1.21.10.jar` | `03c760850ef7b1501fb5b6d23af61ce855e746ab8d5a2f2a1deed9a4480e26ac` |

The legacy candidate JARs use Fabric intermediary names; the 26.x JARs use official names.

The [grouping record](legacy-group-decisions.md) describes the tested API boundaries and rejected unchanged-JAR combinations. Ten new candidate JARs plus the three maintained JARs are the current practical partition, not proof that a smaller fully tested partition is impossible. Build execution uses Java 25, Gradle 9.8.2, Loom 1.19.3 and Loader 0.20.1; older artifacts target Java 8, 16, 17 or 21 as listed in the [toolchain record](compatibility.md#toolchain-decision).

The verified integrated baseline heads were `main` `794aec0eda8e7bfaea5f5e14307766b359589d8f`, `mc/1.21.11` `177f5708727ae4c152091d185536aaa734063280`, `mc/26.1-26.2` `453cf35695cf07be4072f77895cdbafbed617870`, and `mc/26.3` `226b1de7dd4e7c2a75ec35eef1697434462e4f54`. The ten new `mc/*` base branches remain at the 1.21.11 baseline until their draft PRs are independently reviewed and integrated. [Coordination PR #15](https://github.com/skyRolly/third-person-readable-maps/pull/15) targets `main`; its current head and checks are shown on the PR.

The [13-group dry-run record](legacy-dry-run-expanded-2026-11-05.md) lists every tested source head, local build source, artifact digest, matrix, provenance and checksum. This was local staged aggregation, not a hosted release workflow. The [advisory review index](legacy-security-triage-2026-11-05.md) summarizes the unreviewed, failing candidate OSV results; the authoritative security ledger and release configuration still cover only integrated groups. The separately proposed [scheduled candidate audit](dependency-monitoring.md#proposed-scheduled-legacy-candidate-audit) compares source-pinned candidate branches against an unreviewed baseline without accepting risk; its hosted workflow has not run.

Review game-specific ports and their human runtime evidence independently. Integrate only reviewed branches under appropriate protections, verify their actual merged-head Linux and Windows checks, and activate their planned Dependabot targets only when those branches contain the port. Review the coordination PR and refresh its candidate fixture when heads move. Before any later release registration, re-scan actual maintained heads, individually triage advisories, add verified groups and per-version runtime reports to the strict release plan, complete independent review and administrative gates, and rerun the full release authorization and aggregation checks. No merge, tag, draft release or publication was performed by this work.
