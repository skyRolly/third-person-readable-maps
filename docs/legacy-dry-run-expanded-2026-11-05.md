# Local non-publishing 13-group candidate dry run — 2026-11-05

**PASS for the complete local candidate aggregation; not a hosted workflow or production approval.** Coordinator release tooling `ac282db9ea8dd3c8468e3776c37d7ee86dd40c81` generated the 13-group dynamic matrix from the [candidate-only plan and configuration](legacy-dry-run-expanded/), covering all 42 historical versions plus the six already maintained versions. Every planned branch HEAD matched its pinned commit via remote source verification.

Latest source-head verification and aggregation rerun: 2026-11-06 UTC. The plan date is a non-publishing test fixture.

All 13 actual JARs were inspected for filenames, metadata, namespace, bytecode, expected required Mixins and ZIP integrity; aggregation produced a candidate provenance manifest and SHA-256 checksums. `sha256sum --check SHA256SUMS` passed for all JARs and the manifest. An empty artifact directory was rejected, and a strict plan without per-version runtime reports was rejected. Candidate configuration requires candidate mode. No tag, Draft Release, public Release, or release-writing API was invoked.

| Group | Planned source head | Build source / provenance | JAR SHA-256 |
|---|---|---|---|
| 1.14-1.14.4 | `8db35d3d13401008a5d60823020dd0d889984782` | local clean build `d35a7f1074992607b6149842e4100cd936ba1430`; pinned head adds evidence only | `839f0982d11c0a0f95199e1486f7ece203acb7fe8f3e2dd309e9edec214ce5a5` |
| 1.15-1.16.5 | `e6eb2d0481c96a88bf551390bb071a86143337b8` | local clean build `84dde45175c0ca154b44a1acd4efe30d741d5077`; pinned head adds evidence only | `d30a2a682699e881903275ce373d79374b1475e5dff10e7b3e66d364819b13de` |
| 1.17-1.19.2 | `202228e4b3777670399dfc60275080a6198ee709` | local clean build `a12c56cc742ec0b0c3ab26619bddf110482b95d6`; pinned head adds evidence only | `aee00518a1a5b3c31cf794063ac685aa2675ac0b719f11d2b50d0ec8ccf351e6` |
| 1.19.3 | `6405f8bbcf481bed760d7de73ca01d0f3e86e55c` | local clean build `c9ca3b5f05768017a197116919f22e2a967a8d01`; pinned head adds evidence only | `f7288ad9a7f73f718176db15f185bab10d8a02548b02e2f4a943aac06f0db16b` |
| 1.19.4-1.20.4 | `4df429e9a32da098b9bebd52f70989aa445245b0` | local clean build `532cfb548bb29eb99fbcb57424592f07c8ca3606`; pinned head adds evidence only | `7b6e18ebce73045fb937640a1edc0b364a6b13f6bb66941f0c209a204cab0af9` |
| 1.20.5-1.20.6 | `ec3f2a51d8afc7b0a1911cdc6cae88fe00e2b917` | local clean build `32164d846089ce67d5c0a10ba351796207312b02`; pinned head adds evidence only | `8c02fa2fc1b565e8154926642ac4fa260b28f59aeca8a49f9958a8d39050cdfd` |
| 1.21-1.21.1 | `253e4600e94a5c05da81cb5d4bf700d5b7a7117d` | local clean build `5f5fdad012ab499b2f31e0f878d507c4d774d4b4`; pinned head adds evidence only | `d4054952d77a3b4dc79d7681779126cf38bd0fb34c1f9afd3346ceb9f4ca4745` |
| 1.21.11 | `177f5708727ae4c152091d185536aaa734063280` | merged-head Linux CI 41878123381 | `18e3a8dbd461b4bad2711cfe14282b96797f13bebabc8a2b644b6f482a27f930` |
| 1.21.2-1.21.3 | `63338bbd9c3634e27a9a42e3025a8a3279301bbe` | local clean build `84d8291e16fc14ffa3b0956404b64c9538251693`; pinned head adds evidence only | `28a15aacf531dfdb3dd51ba63b7e9cf42000e0b981d863cdc0c27bebc89523e4` |
| 1.21.4-1.21.8 | `e15fd43aba735760d37f61427a52e0a6305d1022` | local clean build `4b2e363c495640fa5ca305620c51c709a434ee2c`; pinned head adds evidence only | `26a28fb550132d07af415c41ccb82982937906ab991ad810406d2937b5e4e776` |
| 1.21.9-1.21.10 | `aa319a0ea75dd62eb23aa2d44dda3b827de973b5` | local clean build `ee07f9599f3868909c1d198802783422f6d83e72`; pinned head adds evidence only | `03c760850ef7b1501fb5b6d23af61ce855e746ab8d5a2f2a1deed9a4480e26ac` |
| 26.1-26.2 | `453cf35695cf07be4072f77895cdbafbed617870` | merged-head Linux CI 41878099343 | `75c244ef6440ff2622d8617a5c60288b956d1a1d80956a233e13bac1ced9c554` |
| 26.3 | `226b1de7dd4e7c2a75ec35eef1697434462e4f54` | merged-head Linux CI 41878066239 | `9f3bc6a3ee4477a3e7cc0f0ebb4c2ff25785ac3f608761f2dc502765f23e2e69` |

The ten locally built legacy JARs also passed their candidate cross-version static verifiers and hosted Linux and Windows PR CI at their implementation commits. Later evidence-only heads require their own current checks. The integrated artifacts came from successful merged-head Linux CI; their compilation was not repeated in this aggregation. Candidate heads with a different local build source add documentation/evidence only, and the artifact hashes match the installed/tested JARs where runtime smoke is recorded.

The [matrix](legacy-dry-run-expanded/matrix.json), [manifest](legacy-dry-run-expanded/release-manifest.json), and [checksums](legacy-dry-run-expanded/SHA256SUMS) are retained as evidence. This was a staged local aggregation, not a hosted 13-group release workflow. It did not complete the graphical matrix, independent review, security triage, branch protections, or release authorization. Any changed source head or artifact requires a new run.
