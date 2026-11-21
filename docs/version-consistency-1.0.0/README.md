# 1.0.0 version consistency — 2026-11-14

**Historical snapshot:** the table below records the November 13 proposal
heads. The [current proposed source pins](current-heads.json) have advanced;
the [clean final-head build and verification index](stabilization-2026-11-14/) records matching artifact hashes, 48-version static results and exact-head hosted checks. The table remains a historical observation, including its original runtime source identities.

The table distinguishes actual remote target properties from unmerged proposed heads. Every proposed artifact is 1.0.0; its hash was checked in the candidate rehearsal and its declared versions completed local-world startup and short walking observations. Full graphical acceptance, security dispositions and integration remain open.

| Target/group | Current remote Mod / Minecraft property | Proposed Mod | Proposed artifact | SHA-256 | Local-world smoke |
|---|---|---|---|---|---|
| [1.14-1.14.4](https://github.com/skyRolly/third-person-readable-maps/pull/23) | 0.0.2 / 1.21.11 | 1.0.0 | `third-person-readable-maps-1.0.0-mc1.14-1.14.4.jar` | `e9ee5d9e7cd0c3e2bbbab8f328bf824e10388fa7049902e165e0c7684b39972b` | 5/5 |
| [1.15-1.16.5](https://github.com/skyRolly/third-person-readable-maps/pull/21) | 0.0.2 / 1.21.11 | 1.0.0 | `third-person-readable-maps-1.0.0-mc1.15-1.16.5.jar` | `11d981b84902ce7ecea3cbf2e97c2b73af13ad68b944892e9a38904c3cdde79c` | 9/9 |
| [1.17-1.19.2](https://github.com/skyRolly/third-person-readable-maps/pull/20) | 0.0.2 / 1.21.11 | 1.0.0 | `third-person-readable-maps-1.0.0-mc1.17-1.19.2.jar` | `fe12ac4576e7d6f55389192b8094698dce33467bf8fb9336a5cb06a72478fcb5` | 8/8 |
| [1.19.3](https://github.com/skyRolly/third-person-readable-maps/pull/22) | 0.0.2 / 1.21.11 | 1.0.0 | `third-person-readable-maps-1.0.0-mc1.19.3.jar` | `4282166c4250d35db2cc794de986ae4c3de9438e8d7932991778454bdefff1c1` | 1/1 |
| [1.19.4-1.20.4](https://github.com/skyRolly/third-person-readable-maps/pull/19) | 0.0.2 / 1.21.11 | 1.0.0 | `third-person-readable-maps-1.0.0-mc1.19.4-1.20.4.jar` | `c2fc1583487f5e1d4e6e82494582951aee055e45664583fbe1c6c88605601a2c` | 6/6 |
| [1.20.5-1.20.6](https://github.com/skyRolly/third-person-readable-maps/pull/18) | 0.0.2 / 1.21.11 | 1.0.0 | `third-person-readable-maps-1.0.0-mc1.20.5-1.20.6.jar` | `d0d37fb74198d8b930597eb4c615c6e09d43034ae7e1bfe34b6b12c4583c190a` | 2/2 |
| [1.21-1.21.1](https://github.com/skyRolly/third-person-readable-maps/pull/17) | 0.0.2 / 1.21.11 | 1.0.0 | `third-person-readable-maps-1.0.0-mc1.21-1.21.1.jar` | `89fb3722f5136d73bc196d4edb4a20da95d1902edd4e7cef2ee39f9743eb892c` | 2/2 |
| [1.21.11](https://github.com/skyRolly/third-person-readable-maps/pull/31) | 0.0.2 / 1.21.11 | 1.0.0 | `third-person-readable-maps-1.0.0-mc1.21.11.jar` | `c60f65c24a44fec6cf0c1fc0c67bb52a06e045ab32e2a9f7dbeab2c619f45b73` | 1/1 |
| [1.21.2-1.21.3](https://github.com/skyRolly/third-person-readable-maps/pull/16) | 0.0.2 / 1.21.11 | 1.0.0 | `third-person-readable-maps-1.0.0-mc1.21.2-1.21.3.jar` | `1b16c66cb32a7684645d5c28e423fc76244d47326ba3e4cce839ead8e01b2e75` | 2/2 |
| [1.21.4-1.21.8](https://github.com/skyRolly/third-person-readable-maps/pull/14) | 0.0.2 / 1.21.11 | 1.0.0 | `third-person-readable-maps-1.0.0-mc1.21.4-1.21.8.jar` | `6b7fbc8140fcc2fe8e510c82ce01a68a61dff5ad18a6a0dc437e1cbb3189d02e` | 5/5 |
| [1.21.9-1.21.10](https://github.com/skyRolly/third-person-readable-maps/pull/13) | 0.0.2 / 1.21.11 | 1.0.0 | `third-person-readable-maps-1.0.0-mc1.21.9-1.21.10.jar` | `c1c1724e9aa3ae1f0c9dc976a364a3ae98e22f2e49e9bd5a1ea8948809e16f1a` | 2/2 |
| [26.1-26.2](https://github.com/skyRolly/third-person-readable-maps/pull/32) | 0.0.2 / 26.1 | 1.0.0 | `third-person-readable-maps-1.0.0-mc26.1-26.2.jar` | `703bbfa20130642133b393ba4198e02eba6e7824814d8c575098a5527ea4e93f` | 4/4 |
| [26.3](https://github.com/skyRolly/third-person-readable-maps/pull/33) | 0.0.2 / 26.3 | 1.0.0 | `third-person-readable-maps-1.0.0-mc26.3.jar` | `ecb9bd62d7bb256f9cf6981a80fdb1cb5617da8bfdf6d691e585fc8f62673559` | 1/1 |

The ten legacy targets are placeholders containing the 1.21.11 baseline, not integrated legacy ports. The three existing maintenance targets are integrated at 0.0.2. The proposed 1.0.0 heads and expected post-integration versions are not current target states. See the [source and artifact index](index.json), [48-version matrix](../compatibility-1.0.0-validation.md), and [release gates](../release-readiness-1.0.0.md).

No 1.0.0 tag, draft release or public release was created.
