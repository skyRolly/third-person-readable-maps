# Legacy candidate review handoff

All ten proposed legacy implementations remain draft PRs against placeholder `mc/*` branches. They are not integrated or release-ready. The coordinated proposed mod version is **1.0.0**; the three already-integrated branches still contain 0.0.2 until their separate review PRs merge. No release has been published.

All 42 legacy versions passed the current instruction-aware static checks against the identified local 1.0.0 JARs. This is not complete JVM verification or graphical acceptance. [Current per-version results](legacy-version-inventory.md), [machine-readable candidate evidence](legacy-candidate-evidence.json), and [historical 0.0.2 observations](historical-0.0.2-2026-11-05/) are separate.

| Group | Draft PR | Proposed source HEAD | 1.0.0 JAR SHA-256 | Installed 1.0.0 coverage |
|---|---|---|---|---|
| 1.14-1.14.4 | [PR](https://github.com/skyRolly/third-person-readable-maps/pull/23) | `83f3a34a5a984d2ac88398465679b7dffd60e20d` | `5770c22a021f1c2fd74a80444fe759701f70c82a65fa03e9fd5e90154e701423` | 5/5 partial local-world evidence |
| 1.15-1.16.5 | [PR](https://github.com/skyRolly/third-person-readable-maps/pull/21) | `f566285f448411f0abc4a61c86a1036300547495` | `2f8b094db2de01569e42605870ef05a82880ffc72291796ded0a8dd518804eed` | 5/9 partial local-world evidence |
| 1.17-1.19.2 | [PR](https://github.com/skyRolly/third-person-readable-maps/pull/20) | `7bc8efafa18f832d683aed38ef3a998008afa070` | `0bb801f64aa4adcea52ed50e123909d242a353d5faa4cdb69aae3e1fc5250116` | 0/8 partial local-world evidence |
| 1.19.3 | [PR](https://github.com/skyRolly/third-person-readable-maps/pull/22) | `52221cf3d087df8f3ec6d5533d2409a309b8193e` | `cb5c1e04f33ad1fc572f72f01da6f15ba3c151e520df651b9638ae8a2afa4597` | 0/1 partial local-world evidence |
| 1.19.4-1.20.4 | [PR](https://github.com/skyRolly/third-person-readable-maps/pull/19) | `d727717745a29811b9bb6758b19f4a7c0dc548da` | `dfe2940c28a80b051856efbd1c86eec99ff7c1031426ab62ebcfc7f26efdd29a` | 0/6 partial local-world evidence |
| 1.20.5-1.20.6 | [PR](https://github.com/skyRolly/third-person-readable-maps/pull/18) | `44bd44301fbfc11e9f5eefe63a1eb2d04e8b0c96` | `d0d37fb74198d8b930597eb4c615c6e09d43034ae7e1bfe34b6b12c4583c190a` | 0/2 partial local-world evidence |
| 1.21-1.21.1 | [PR](https://github.com/skyRolly/third-person-readable-maps/pull/17) | `b24ed245e4630c2df87f539707dbf662bba354ac` | `89fb3722f5136d73bc196d4edb4a20da95d1902edd4e7cef2ee39f9743eb892c` | 0/2 partial local-world evidence |
| 1.21.2-1.21.3 | [PR](https://github.com/skyRolly/third-person-readable-maps/pull/16) | `2f7f902dc2d1ca62ed6e7f628db8ef1c367586c1` | `1b16c66cb32a7684645d5c28e423fc76244d47326ba3e4cce839ead8e01b2e75` | 0/2 partial local-world evidence |
| 1.21.4-1.21.8 | [PR](https://github.com/skyRolly/third-person-readable-maps/pull/14) | `08f70683b93eff8d4a68dd366232c70cedd65101` | `6b7fbc8140fcc2fe8e510c82ce01a68a61dff5ad18a6a0dc437e1cbb3189d02e` | 0/5 partial local-world evidence |
| 1.21.9-1.21.10 | [PR](https://github.com/skyRolly/third-person-readable-maps/pull/13) | `ec7b47fb8d87e307d33250ef8693671d8e65ab0b` | `c1c1724e9aa3ae1f0c9dc976a364a3ae98e22f2e49e9bd5a1ea8948809e16f1a` | 0/2 partial local-world evidence |

The 1.14 and 1.15 candidates include source-bound controlled map-ID probes; 1.14 also includes texture and lighting state probes. These are targeted diagnostics, not independent full acceptance. An unexplained foreground shape in earlier walking captures did not recur in one matched 1.21.4 candidate/no-mod comparison; the cause remains unresolved and requires matched world, camera, pose, renderer, and frame comparisons.

Do not activate Dependabot for a placeholder. After independent source review and integration, register the exact maintenance commit, switch candidate monitoring to the pinned integrated-transition state, and only then activate Gradle and Actions updates. Strict release admission, current per-version runtime evidence, independent approvals, security dispositions, branch protection and release authorization are separate gates. See [dependency monitoring](dependency-monitoring.md) and the [1.0.0 release gate matrix](release-readiness-1.0.0.md).
