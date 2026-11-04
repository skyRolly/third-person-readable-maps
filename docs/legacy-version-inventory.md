# Legacy stable-version inventory

Source: [machine-readable inventory](legacy-version-inventory.json), generated from Mojang’s version manifest, hash-checked per-version metadata and mappings, and Fabric metadata. Mapping excerpts and client URLs/SHA-1s are recorded per row. The Fabric Loader value is the globally listed stable version, not proof it launches each old client.

An **unverified** row is not a support claim. Candidate grouping is an investigation hypothesis, and all unlisted tests remain NOT RUN. The 1.21.9–1.21.10 smoke results are detailed in [candidate evidence](legacy-candidate-evidence.json) and [PR #13](https://github.com/skyRolly/third-person-readable-maps/pull/13) / [PR #14](https://github.com/skyRolly/third-person-readable-maps/pull/14).

| Minecraft | Java in Mojang metadata | Fabric intermediary / Yarn | Mapping evidence | Candidate | Linkage | Installed client / graphics |
|---|---:|---|---|---|---|---|
| 1.21.10 | 21 | listed / 1.21.10+build.3 | Mojang | 1.21.9–1.21.10* | PASS* | World PASS; graphics PARTIAL* |
| 1.21.9 | 21 | listed / 1.21.9+build.1 | Mojang | 1.21.9–1.21.10* | PASS* | World PASS; graphics PARTIAL* |
| 1.21.8 | 21 | listed / 1.21.8+build.1 | Mojang | 1.21.4–1.21.8* | PASS* | World PASS; graphics PARTIAL* |
| 1.21.7 | 21 | listed / 1.21.7+build.8 | Mojang | 1.21.4–1.21.8* | PASS* | World PASS; graphics PARTIAL* |
| 1.21.6 | 21 | listed / 1.21.6+build.1 | Mojang | 1.21.4–1.21.8* | PASS* | World PASS; graphics PARTIAL* |
| 1.21.5 | 21 | listed / 1.21.5+build.1 | Mojang | 1.21.4–1.21.8* | PASS* | World PASS; graphics PARTIAL* |
| 1.21.4 | 21 | listed / 1.21.4+build.8 | Mojang | 1.21.4–1.21.8* | PASS* | World PASS; graphics PARTIAL* |
| 1.21.3 | 21 | listed / 1.21.3+build.2 | Mojang | 1.21.2–1.21.3? | NOT RUN | NOT RUN |
| 1.21.2 | 21 | listed / 1.21.2+build.1 | Mojang | 1.21.2–1.21.3? | NOT RUN | NOT RUN |
| 1.21.1 | 21 | listed / 1.21.1+build.3 | Mojang | 1.21–1.21.1? | NOT RUN | NOT RUN |
| 1.21 | 21 | listed / 1.21+build.9 | Mojang | 1.21–1.21.1? | NOT RUN | NOT RUN |
| 1.20.6 | 21 | listed / 1.20.6+build.3 | Mojang | undetermined | NOT RUN | NOT RUN |
| 1.20.5 | 21 | listed / 1.20.5+build.1 | Mojang | undetermined | NOT RUN | NOT RUN |
| 1.20.4 | 17 | listed / 1.20.4+build.3 | Mojang | undetermined | NOT RUN | NOT RUN |
| 1.20.3 | 17 | listed / 1.20.3+build.1 | Mojang | undetermined | NOT RUN | NOT RUN |
| 1.20.2 | 17 | listed / 1.20.2+build.4 | Mojang | undetermined | NOT RUN | NOT RUN |
| 1.20.1 | 17 | listed / 1.20.1+build.10 | Mojang | undetermined | NOT RUN | NOT RUN |
| 1.20 | 17 | listed / 1.20+build.1 | Mojang | undetermined | NOT RUN | NOT RUN |
| 1.19.4 | 17 | listed / 1.19.4+build.2 | Mojang | undetermined | NOT RUN | NOT RUN |
| 1.19.3 | 17 | listed / 1.19.3+build.5 | Mojang | undetermined | NOT RUN | NOT RUN |
| 1.19.2 | 17 | listed / 1.19.2+build.28 | Mojang | undetermined | NOT RUN | NOT RUN |
| 1.19.1 | 17 | listed / 1.19.1+build.6 | Mojang | undetermined | NOT RUN | NOT RUN |
| 1.19 | 17 | listed / 1.19+build.4 | Mojang | undetermined | NOT RUN | NOT RUN |
| 1.18.2 | 17 | listed / 1.18.2+build.4 | Mojang | undetermined | NOT RUN | NOT RUN |
| 1.18.1 | 17 | listed / 1.18.1+build.22 | Mojang | undetermined | NOT RUN | NOT RUN |
| 1.18 | 17 | listed / 1.18+build.1 | Mojang | undetermined | NOT RUN | NOT RUN |
| 1.17.1 | 16 | listed / 1.17.1+build.65 | Mojang | undetermined | NOT RUN | NOT RUN |
| 1.17 | 16 | listed / 1.17+build.13 | Mojang | undetermined | NOT RUN | NOT RUN |
| 1.16.5 | 8 | listed / 1.16.5+build.10 | Mojang | undetermined | NOT RUN | NOT RUN |
| 1.16.4 | 8 | listed / 1.16.4+build.9 | Mojang | undetermined | NOT RUN | NOT RUN |
| 1.16.3 | 8 | listed / 1.16.3+build.47 | Mojang | undetermined | NOT RUN | NOT RUN |
| 1.16.2 | 8 | listed / 1.16.2+build.47 | Mojang | undetermined | NOT RUN | NOT RUN |
| 1.16.1 | 8 | listed / 1.16.1+build.21 | Mojang | undetermined | NOT RUN | NOT RUN |
| 1.16 | 8 | listed / 1.16+build.4 | Mojang | undetermined | NOT RUN | NOT RUN |
| 1.15.2 | 8 | listed / 1.15.2+build.17 | Mojang | undetermined | NOT RUN | NOT RUN |
| 1.15.1 | 8 | listed / 1.15.1+build.37 | Mojang | undetermined | NOT RUN | NOT RUN |
| 1.15 | 8 | listed / 1.15+build.2 | Mojang | undetermined | NOT RUN | NOT RUN |
| 1.14.4 | 8 | listed / 1.14.4+build.18 | Mojang | undetermined | NOT RUN | NOT RUN |
| 1.14.3 | 8 | listed / 1.14.3+build.13 | Yarn | undetermined | NOT RUN | NOT RUN |
| 1.14.2 | 8 | listed / 1.14.2+build.7 | Yarn | undetermined | NOT RUN | NOT RUN |
| 1.14.1 | 8 | listed / 1.14.1+build.10 | Yarn | undetermined | NOT RUN | NOT RUN |
| 1.14 | 8 | listed / 1.14+build.21 | Yarn | undetermined | NOT RUN | NOT RUN |

\* Candidate evidence is limited to the identified JAR and environment; it does not mean release-ready or complete graphical acceptance. `?` marks an unverified grouping hypothesis.

Mojang metadata lists a client artifact for every row; listing is not a successful download. The 1.21.4–1.21.10 clients were actually downloaded and hash-checked for this round. Fabric’s game and intermediary metadata did not list sampled 1.13.2, 1.13.1, 1.13, or 1.12.2 releases; pre-1.14 is outside this round’s official Fabric target and has not been ported.
