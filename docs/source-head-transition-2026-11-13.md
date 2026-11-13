# Product source-head transition — 2026-11-13 UTC

All 13 proposed product heads advanced with the same verifier-only correction. The prior source-bound CI, runtime and candidate-security reports remain historical for their recorded heads. New [exact-head Linux/Windows CI](hosted-builds-verifier-followup-2026-11-13.json), [clean Linux builds](builds-verifier-followup-2026-11-13/) and a [non-publishing candidate rehearsal](legacy-dry-run-1.0.0.md) passed for every product PR; each clean-build JAR matched its previous digest. [Fresh source-bound runtime observations](runtime-smoke-verifier-followup-2026-11-13/) are partial. Dependency snapshots still need refresh before that gate can pass. No product branch was merged.

The updated parser checks class-only instructions, class constants and constructor method handles, using the effective Mixin target as the access context. Its 16 controlled fixtures and a prototype run over all 48 previous artifacts passed. Protected-receiver flow, some `invokespecial` cases, descriptor-only class access and complex transformations remain unproven. The prototype run is not a source-bound test of newly built artifacts.

| Group | Previous source HEAD | Current proposed HEAD | Previous artifact SHA-256 |
|---|---|---|---|
| 1.14-1.14.4 | `341d33664272c2a19aa419e3d33f01b1954df991` | `f2b45ae6242ac44d952f7b037e0200f4a85ad128` | `e9ee5d9e7cd0c3e2bbbab8f328bf824e10388fa7049902e165e0c7684b39972b` |
| 1.15-1.16.5 | `7bf2ae372fac4d6e478f3a523db963886e05900f` | `24cd97031ac91ab3595c50add83c2208f5230fbc` | `11d981b84902ce7ecea3cbf2e97c2b73af13ad68b944892e9a38904c3cdde79c` |
| 1.17-1.19.2 | `96060a2c1c5267eae102f24cf3a78d6646d4dbce` | `d5792f245f133cdf4873b1e6ce0078c77d20a3d3` | `fe12ac4576e7d6f55389192b8094698dce33467bf8fb9336a5cb06a72478fcb5` |
| 1.19.3 | `c3ac7d261b4289451c8b27df96fae7a316ba75ed` | `2cb3f385443e6db375eb46077d562421ed7aa4cc` | `4282166c4250d35db2cc794de986ae4c3de9438e8d7932991778454bdefff1c1` |
| 1.19.4-1.20.4 | `4c78b44bd8ac1a758f3c04987530b9fda844127b` | `991fc1d6d21819f642c9963f91570fb10ab40f92` | `c2fc1583487f5e1d4e6e82494582951aee055e45664583fbe1c6c88605601a2c` |
| 1.20.5-1.20.6 | `44bd44301fbfc11e9f5eefe63a1eb2d04e8b0c96` | `c0efb70ad1e01298c96441d18bc68f0b2674d6d6` | `d0d37fb74198d8b930597eb4c615c6e09d43034ae7e1bfe34b6b12c4583c190a` |
| 1.21-1.21.1 | `b24ed245e4630c2df87f539707dbf662bba354ac` | `7e6b43e91e9eb32788f288d6aa64aaa72ee3f514` | `89fb3722f5136d73bc196d4edb4a20da95d1902edd4e7cef2ee39f9743eb892c` |
| 1.21.11 | `1c78a4c5488133cf041520dad1b97e5ef0de3f30` | `b79f5061bae6caacb8c083f5fb90a1754ea32b9e` | `c60f65c24a44fec6cf0c1fc0c67bb52a06e045ab32e2a9f7dbeab2c619f45b73` |
| 1.21.2-1.21.3 | `2f7f902dc2d1ca62ed6e7f628db8ef1c367586c1` | `78ef3c311f2db755c87907af6d698ed4527bd2de` | `1b16c66cb32a7684645d5c28e423fc76244d47326ba3e4cce839ead8e01b2e75` |
| 1.21.4-1.21.8 | `08f70683b93eff8d4a68dd366232c70cedd65101` | `55df5055388918d5df96a3f61f6c9dc999042271` | `6b7fbc8140fcc2fe8e510c82ce01a68a61dff5ad18a6a0dc437e1cbb3189d02e` |
| 1.21.9-1.21.10 | `ec7b47fb8d87e307d33250ef8693671d8e65ab0b` | `24e4acd8e02d1a30c3d18860f2d72fa9b7c77f81` | `c1c1724e9aa3ae1f0c9dc976a364a3ae98e22f2e49e9bd5a1ea8948809e16f1a` |
| 26.1-26.2 | `d3695609e0a05ede476bf80b09bf0047868165e5` | `1d888cf76ba985fd8587a931d6c88c20d22ae691` | `703bbfa20130642133b393ba4198e02eba6e7824814d8c575098a5527ea4e93f` |
| 26.3 | `fb8acf5d10592382c20b48f60b2fe224d65aacb0` | `f59d2add2d5a7eba16cd5b5fe72a36e18c29746c` | `ecb9bd62d7bb256f9cf6981a80fdb1cb5617da8bfdf6d691e585fc8f62673559` |

The [machine-readable source identities](source-head-transition-2026-11-13.json) preserve the full branch names and hashes. An unchanged artifact digest can support a continuity argument but does not relabel earlier source-bound tests or approve a release.
