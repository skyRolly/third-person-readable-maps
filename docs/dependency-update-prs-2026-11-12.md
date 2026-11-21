# Dependency-update PR review — 2026-11-12

## Current update proposals — 2026-11-21

The seven November 12 PRs below are historical: #24–#30 are closed without
merging. Dependabot replaced them with the seven open PRs below. Their green
checks apply to the current 0.0.2 or existing main bases, not to future
security/product integration trees. Keep bot branches separate and require a
rebase or recreation and fresh checks after the relevant target changes.

| PR | Target | Update | Current review disposition |
|---|---|---|---|
| [#37](https://github.com/skyRolly/third-person-readable-maps/pull/37) | `mc/1.21.11` | setup-java 6.3.0 | Revalidate against the security and 1.0.0 integration tree. |
| [#38](https://github.com/skyRolly/third-person-readable-maps/pull/38) | `mc/26.1-26.2` | setup-java 6.3.0 | Revalidate against the security and 1.0.0 integration tree. |
| [#39](https://github.com/skyRolly/third-person-readable-maps/pull/39) | `mc/26.3` | setup-java 6.3.0 | Revalidate against the security and 1.0.0 integration tree. |
| [#40](https://github.com/skyRolly/third-person-readable-maps/pull/40) | `main` | setup-java 6.3.0 | Revalidate against the coordinator's final workflows. |
| [#41](https://github.com/skyRolly/third-person-readable-maps/pull/41) | `mc/26.1-26.2` | Gradle 9.9.1 | Superseded for security purposes by 9.9.2; reconcile after target integration. |
| [#42](https://github.com/skyRolly/third-person-readable-maps/pull/42) | `mc/26.3` | Gradle 9.9.1 | Superseded for security purposes by 9.9.2; reconcile after target integration. |
| [#43](https://github.com/skyRolly/third-person-readable-maps/pull/43) | `mc/1.21.11` | Gradle 9.9.1 | Superseded for security purposes by 9.9.2; reconcile after target integration. |

The setup-java `v6.3.0` upstream tag resolved to
`d1374f8ac74474200d16ef8ecee22c7ae7a51880`. The three 9.9.1 PRs passed the
coordinator's canonical Wrapper preflight: the published Wrapper JAR SHA-256
was `621008afc4f5d59357fcf06ffa644dd5aade5e091bdc363742710445f73cdaf8` and
the published binary distribution SHA-256 was
`d8a18a7a841dd5df825d35a685fad6f2d7f12ac0c280e57b67c27b4a520ba228`.
Gradle 9.9.2 is the fixed release for additional upstream high-severity
advisories affecting 9.9.1; see the [source-bound investigation](worklogs/late-review-2026-11-16.md)
and [upstream advisory records](dependency-evidence/gradle-build-tool-advisories-2026-11-21.json).
These checksum checks establish identity against Gradle's published values,
not compatibility with the pending 1.0.0 implementations.

## Historical 2026-11-12 proposals

On [2026-11-14](pr-checks-2026-11-14.json), all seven PRs were still open,
their recorded checks still passed on their existing bot heads, and no diff
modified `gradle.properties`. The setup-java tag still resolved to the pinned
commit and Gradle 9.9.0 still appeared as a non-prerelease. The conclusions
below remain the recommended handling; rerun checks after any target update.

All seven PRs below were open and mergeable at inspection. Their existing
checks passed on their then-current bot heads, but those results do not certify
the separate proposed 1.0.0 heads or a future merged/rebased result. None of the
bot diffs changes `gradle.properties`; they should nevertheless be revalidated
against the final target before integration.

| PR | Target | Update | Disposition |
|---|---|---|---|
| [#24](https://github.com/skyRolly/third-person-readable-maps/pull/24) | `mc/26.3` | `actions/setup-java` 6.2.0 | Keep separate; rebase or recreate after the 1.0.0 maintenance PR and rerun both OS builds. |
| [#25](https://github.com/skyRolly/third-person-readable-maps/pull/25) | `mc/1.21.11` | `actions/setup-java` 6.2.0 | Same; review the CI workflow interaction. |
| [#26](https://github.com/skyRolly/third-person-readable-maps/pull/26) | `main` | `actions/setup-java` 6.2.0 | Keep separate; rebase or recreate after coordination changes and rerun coordination validation. |
| [#27](https://github.com/skyRolly/third-person-readable-maps/pull/27) | `mc/26.1-26.2` | `actions/setup-java` 6.2.0 | Keep separate; rebase or recreate after the maintenance PR and rerun both OS builds. |
| [#28](https://github.com/skyRolly/third-person-readable-maps/pull/28) | `mc/1.21.11` | Gradle wrapper 9.9.0 | Keep separate; review after the 1.0.0 PR, verify wrapper integrity and rerun both OS builds. |
| [#29](https://github.com/skyRolly/third-person-readable-maps/pull/29) | `mc/26.3` | Gradle wrapper 9.9.0 | Same. |
| [#30](https://github.com/skyRolly/third-person-readable-maps/pull/30) | `mc/26.1-26.2` | Gradle wrapper 9.9.0 | Same. |

The setup-java PRs pin `77dd5b2ce225ea11469928ac317850245a74ae78`, which
matched the upstream `v6.2.0` tag at inspection. Gradle's `v9.9.0` release was
published as a non-draft, non-prerelease on 2026-11-06. All three wrapper PRs'
JARs hash to `621008afc4f5d59357fcf06ffa644dd5aade5e091bdc363742710445f73cdaf8`,
matching Gradle's published 9.9.0 wrapper checksum. Their distribution SHA-256
`0b00b0ffe07c4d4789c12d4935a44a7057d55774b7540bd4a3f76f336deb177a`
matches the published binary distribution checksum. This verifies the checked
identities, not compatibility with untested historical game branches. No broad
toolchain upgrade, bot-branch rewrite, merge or auto-merge was performed.
