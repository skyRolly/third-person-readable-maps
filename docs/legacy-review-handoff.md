# Legacy candidate review handoff

All ten proposed legacy implementations remain draft PRs against placeholder `mc/*` branches. They are not integrated or release-ready. The coordinated proposed mod version is **1.0.0**; actual integrated branches remain 0.0.2 pending their separate reviewed PRs. No coordinated release has been published.

All 42 legacy versions passed instruction-aware verification on the advanced proposed heads, with remaining JVM limits in the [review matrix](review-resolution-1.0.0.md). The [current per-version inventory](legacy-version-inventory.md), [candidate evidence](legacy-candidate-evidence.json), [prior 1.0.0 snapshot](historical-verifier-followup-2026-11-13/) and [historical 0.0.2 evidence](historical-0.0.2-2026-11-05/) retain separate identities.

| Group | Draft PR | Proposed source HEAD | 1.0.0 JAR SHA-256 | New-head installed coverage |
|---|---|---|---|---|
| 1.14-1.14.4 | [PR](https://github.com/skyRolly/third-person-readable-maps/pull/23) | `f2b45ae6242ac44d952f7b037e0200f4a85ad128` | `e9ee5d9e7cd0c3e2bbbab8f328bf824e10388fa7049902e165e0c7684b39972b` | 5/5 partial local-world evidence |
| 1.15-1.16.5 | [PR](https://github.com/skyRolly/third-person-readable-maps/pull/21) | `24cd97031ac91ab3595c50add83c2208f5230fbc` | `11d981b84902ce7ecea3cbf2e97c2b73af13ad68b944892e9a38904c3cdde79c` | 9/9 partial local-world evidence |
| 1.17-1.19.2 | [PR](https://github.com/skyRolly/third-person-readable-maps/pull/20) | `d5792f245f133cdf4873b1e6ce0078c77d20a3d3` | `fe12ac4576e7d6f55389192b8094698dce33467bf8fb9336a5cb06a72478fcb5` | 8/8 partial local-world evidence |
| 1.19.3 | [PR](https://github.com/skyRolly/third-person-readable-maps/pull/22) | `2cb3f385443e6db375eb46077d562421ed7aa4cc` | `4282166c4250d35db2cc794de986ae4c3de9438e8d7932991778454bdefff1c1` | 1/1 partial local-world evidence |
| 1.19.4-1.20.4 | [PR](https://github.com/skyRolly/third-person-readable-maps/pull/19) | `991fc1d6d21819f642c9963f91570fb10ab40f92` | `c2fc1583487f5e1d4e6e82494582951aee055e45664583fbe1c6c88605601a2c` | 6/6 partial local-world evidence |
| 1.20.5-1.20.6 | [PR](https://github.com/skyRolly/third-person-readable-maps/pull/18) | `c0efb70ad1e01298c96441d18bc68f0b2674d6d6` | `d0d37fb74198d8b930597eb4c615c6e09d43034ae7e1bfe34b6b12c4583c190a` | 2/2 partial local-world evidence |
| 1.21-1.21.1 | [PR](https://github.com/skyRolly/third-person-readable-maps/pull/17) | `7e6b43e91e9eb32788f288d6aa64aaa72ee3f514` | `89fb3722f5136d73bc196d4edb4a20da95d1902edd4e7cef2ee39f9743eb892c` | 2/2 partial local-world evidence |
| 1.21.2-1.21.3 | [PR](https://github.com/skyRolly/third-person-readable-maps/pull/16) | `78ef3c311f2db755c87907af6d698ed4527bd2de` | `1b16c66cb32a7684645d5c28e423fc76244d47326ba3e4cce839ead8e01b2e75` | 2/2 partial local-world evidence |
| 1.21.4-1.21.8 | [PR](https://github.com/skyRolly/third-person-readable-maps/pull/14) | `55df5055388918d5df96a3f61f6c9dc999042271` | `6b7fbc8140fcc2fe8e510c82ce01a68a61dff5ad18a6a0dc437e1cbb3189d02e` | 5/5 partial local-world evidence |
| 1.21.9-1.21.10 | [PR](https://github.com/skyRolly/third-person-readable-maps/pull/13) | `24e4acd8e02d1a30c3d18860f2d72fa9b7c77f81` | `c1c1724e9aa3ae1f0c9dc976a364a3ae98e22f2e49e9bd5a1ea8948809e16f1a` | 2/2 partial local-world evidence |

Earlier controlled map-ID and 1.14 texture/lighting probes are retained with their prior source heads. All 19 component-era game codecs converted the tested malformed numeric values to zero in the [isolated codec sweep](dependency-evidence/component-mapid-codec-2026-11-13/); a [1.21.11 local-world probe](component-map-id-item-loading-2026-11-13/host-inventory-attempt/) also observed the item-loading path. Other paths and a bounded remedy remain open. Historical candidate/no-mod [foreground comparisons](foreground-comparisons-2026-11-13/) did not reproduce the large shape, but the original conditions were not reproduced and its cause remains unresolved.

Do not activate Dependabot for a placeholder. Candidate dependency monitoring must stay source-pinned; activation, authoritative release admission, runtime acceptance, security dispositions and independent approvals are separate gates. See the [48-version matrix](compatibility-1.0.0-validation.md), [PR handoff](pr-integration-handoff-1.0.0.md) and [release gates](release-readiness-1.0.0.md).
