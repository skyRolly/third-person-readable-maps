# Coordination branch decision record

Status: PR #8 merged this architecture at `b90ee78e9b1da6d1da2c2f5f93da765739716137`.
The original decision below records the pre-merge alternatives and evidence; its
imperative wording is historical, not unfinished game-build migration work.
The current [maintenance report](maintenance-2026-11-04.md),
[monitoring record](dependency-monitoring.md), and [administrative inventory](administrative-controls.md)
supersede its preliminary configuration and advisory status. Main is coordination-only;
all three game branches are established and 0.0.2 remains unreleased.

Decision based on the repository state inspected on 2026-11-04: `main` was
`3844e9bc0295f71cae64224cbfd6a2c36afb56f0`; the maintained heads were
`1bbd3f41b97ea5d0b78ae1909e846462078bdf9d` (1.21.11),
`6891b6080e4bea981f7a7399a061b32f95f3452e` (26.1–26.2), and
`0839b2cc31ec2a57ffeae82a8b8f892a649f8eaf` (26.3). PRs #3–#7 are
merged. All four heads had successful push CI and automatic dependency
submission. The GitHub branch API reported all four as unprotected, no release
environments were listed, and the available token could not read protection or
Dependabot alert details. PRs #4, #5, #6 and #7 each had no submitted reviews.
The existing release verifier requires approvals submitted before the merge, so
the three current maintenance heads need new, independently reviewed merge
commits after protection is configured. These observations do not authorize
publication.

## Ownership and CI

The `main` Gradle project duplicates 1.21.11; its source, wrapper, build files,
Windows build entry point and Gradle verification are owned by the independent
`mc/1.21.11` project. The other two branches have their own complete projects;
26.1–26.2 also owns the four-version API verifier. The root release scripts,
release configuration, tests, documentation, workflows, license and GitHub
configuration are coordination assets. Remove the duplicated game project from
`main`, retaining the three game projects unchanged. A shared module or merged
26.x JAR would cross the documented namespace and pose API boundaries without
supporting evidence.

Replace main's Linux/Windows game builds and graph generation with Linux
coordination validation, including the release and authorization tests and
workflow lint. The coordinator is Python and has no Windows-specific build
entry point; the maintenance projects retain their existing Linux and Windows
checks. Require the explicitly named coordination job on `main`, and the two
existing build jobs on each game branch. Both roles must still prove the job is
in the latest successful push of the exact `ci.yml` workflow, branch and commit,
with the required GitHub Actions app identity. Review, protection, independent
environment approval, release-plan, artifact and checksum controls remain in
force. Reusing the game-build names on `main` or accepting arbitrary successful
checks would obscure the branch role and weaken that identity guarantee.

## Dependency coverage

Dependabot version updates can target each maintenance branch from the default
branch configuration. GitHub documents that alerts and security-update PRs
concern the default branch; a successful submitted snapshot for a non-default
branch is not evidence of equivalent alert coverage. Keep default-branch Actions
updates, add Gradle and Actions version updates for all maintenance branches,
and keep GitHub's dependency graph, alerts and security updates enabled.

GitHub's managed automatic Gradle submission runs against the default branch and
is not a checked-in workflow. Once `main` has no Gradle project, an administrator
must disable **Automatic dependency submission** under **Settings → Security and
quality → Advanced Security → Dependency graph**, without disabling the graph or
alerts. An additional submission workflow was considered, but submitting
non-default snapshots alone does not supply default-branch alert equivalence.
A source-only scanner without lockfiles would miss resolved transitive versions;
a separate submission workflow would not repair the default-branch alert gap.
A scheduled, read-only OSV advisory scan of resolved maintenance-branch dependency
snapshots is a complementary reporting mechanism; it must identify its sources,
report failures, and not force upgrades to Minecraft-managed libraries. Coverage
is limited to what the Gradle snapshot resolves and the advisory database knows;
review game-supplied libraries and incomplete snapshots separately.

Sources: [Dependabot alerts](https://docs.github.com/en/code-security/concepts/supply-chain-security/dependabot-alerts),
[Dependabot options](https://docs.github.com/en/code-security/reference/supply-chain-security/dependabot-options-reference),
[automatic dependency submission settings](https://docs.github.com/en/code-security/how-tos/secure-your-supply-chain/secure-your-dependencies/submit-dependencies-automatically),
and [Gradle dependency snapshots](https://github.com/gradle/actions/blob/main/docs/dependency-submission.md).

The initial real snapshots produced advisory matches for 10 of 85 packages on
1.21.11, 10 of 84 on 26.1–26.2, and 5 of 86 on 26.3. The
[dated audit](dependency-audit-2026-11-04.md) records the matched packages and
IDs for triage. Those matches do not establish whether this mod is exposed.
