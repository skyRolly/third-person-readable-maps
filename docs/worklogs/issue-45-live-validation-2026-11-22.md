# Issue 45: live scans, guarded builds and runtime gaps

These observations do not authorize a release, a legacy port merge, or an
acceptance of risk. The source-bound investigation from PR #53 and all earlier
reports remain unchanged.

## Fresh scans

The candidate workflow [45013904609](https://github.com/skyRolly/third-person-readable-maps/actions/runs/45013904609)
and integrated workflow [45013904999](https://github.com/skyRolly/third-person-readable-maps/actions/runs/45013904999)
ran the coordinator at `048b6e0a00aff2be37565e14ea25f9e76a872b8d` on
2026-11-22. All 13 wrapper preflights and guarded dependency snapshot steps
passed. Each of the 13 OSV audit steps failed on unresolved matches, as required.
All 13 separate Gradle 9.9.2 upstream tool-advisory queries completed with zero
matches; this does not cover every Gradle plugin or native binary.

The [artifact index](../dependency-evidence/issue45-live-source-2026-11-22/artifact-index.json)
records GitHub's artifact IDs, source workflow IDs, sizes and SHA-256 digests.
The 26 original artifact ZIPs contain the 13 dependency snapshots, 13 OSV reports
and 13 Gradle-tool reports. The [comparison](../dependency-evidence/issue45-live-source-2026-11-22/comparison.json)
is reproducible with `python3 scripts/reconcile_issue45_live_audits.py`; exit 1
is expected while findings remain. The tool verifies ZIP hashes, complete
reports, commit and ref, snapshot inventories, findings, scopes and advisory
fingerprints. It compares exact occurrence identities with the hash-verified
[historical index](../dependency-evidence/issue45-exact-source-2026-11-21-v2/finding-index.json).
It refuses to compare a changed source as the same source. A missing or renamed
advisory requires review; it is not automatically a fix.

| Source | Critical | High | Moderate | Low | Total |
|---|---:|---:|---:|---:|---:|
| Ten legacy candidates | 18 | 141 | 212 | 14 | 385 |
| Three integrated maintenance groups | 4 | 36 | 62 | 3 | 105 |
| Total scoped occurrences | 22 | 177 | 274 | 17 | 490 |

The fresh reports contain the same 490 source/group/package/advisory identities
as the archived scan: no new or missing identities, changed scopes, severity,
fingerprints or dispositions. None of the returned advisory records changed
its `modified`, aliases or withdrawal field. These statements are bounded by the
OSV records actually returned; they do not independently establish that no
unqueried or missing advisory exists. Candidate and integrated counts are
separate: respectively 180 and 63 distinct package-version/advisory pairs and
88 and 40 advisory IDs. Globally there are 243 distinct pairs and 89 advisory
IDs. These are not counts of independent exploitable vulnerabilities.

The [prioritized register](../dependency-evidence/issue45-live-source-2026-11-22/priority-register.json)
contains all 199 Critical/High occurrences and 37 advisory IDs, exact source
commits, current report archive hashes and member names, scopes, aliases,
upstream affected ranges and existing dispositions. Its 20 focused IDs cover 93
occurrences (22 Critical, 71 High); the remaining 17 High IDs still require
advisory-specific investigation. No new reviewer decision is implied.

## Reachability and remediation priorities

* **Netty GHSA-c4c3-7fpv-j4q5 / CVE-2026-75595:** 14 occurrences, 11 source
  groups. Existing exact vanilla classpath evidence inspected 29 affected game
  versions and 612 unique official client/runtime JARs. The inspected optional
  dedicated management endpoint constructs an `SslHandler` rather than an SNI
  handler and uses application API-key authentication. This does not establish
  the behavior of launchers, Fabric mods, agents or generated pipelines.
  Upstream fixed versions are 4.1.137.Final and 4.2.17.Final; a compatible
  Minecraft-managed update is not verified. All occurrences still block.
* **Log4j GHSA-jfh8-c2jp-5v3q, GHSA-7rjr-3q55-vv33 and
  GHSA-fxph-q3j8-mv87:** eight occurrences across three legacy groups, with
  Minecraft-managed Core 2.8.1 or 2.14.1. Selected client chat input reaches
  logging; the exact default configuration and alternate embedded configuration
  have different local probe results. The actual supported-launcher JVM
  arguments, loaded configuration, classpath order and third-party plugins
  remain unobserved. No remote exploit or general non-reachability was claimed.
  A compatible upstream change must cover the complete advisory family, not
  just the earliest fixed version for one advisory.
* **Guava:** 16 High occurrences of the focused deserialization/allocation
  advisory remain blocked. First-party sample paths and bounded-memory component
  checks do not establish behavior for other mods or arbitrary inputs.
* **LZ4:** 19 overlapping scoped advisory occurrences in the focused work.
  Local region-file parsing and native extraction need further trust-boundary
  and platform analysis; a remote network route was not established by the
  sampled packet paths. Shared temporary directories and macOS remain open.
* **Commons Compress:** 12 High occurrences in the focused work. The exact
  Minecraft/Realms backup path reaches TAR extraction; whether an attacker can
  control the relevant archive metadata remains unverified.
* **Jackson/MSAL and the other High IDs:** focused observations and all
  uninvestigated identities are listed in the register. Continue with
  network-facing, deserialization and file-processing inputs first.

The [earlier source-bound dispositions](../dependency-evidence/critical-reachability-2026-11-21/source-bound-dispositions-2026-11-21.json)
retain each focused finding's source, evidence, reviewer, limitations and next
action. One Netty 26.2 occurrence remains upstream-dependent; all other current
records retain their prior further-investigation classification. There is no
verified compatible dependency upgrade in this repository, and no game-managed
library was silently overridden.

The new [product JAR literal inspection](../dependency-evidence/issue45-live-source-2026-11-22/mod-jar-literal-inspection.json)
checks the previously retained exact-source archives and JAR SHA-256 values.
Across all 13 product JARs it records 30 class files, no selected literal
Netty/Log4j/JNDI references and no nested JAR entries. This checks this mod's
packaged bytes only; indirect game calls, dynamically constructed names,
reflection, other mods, agents and runtime configuration remain outside it.

## Supported runtime observation matrix

The table is an investigation scope, not a claim that every environment has
been tested. No official launcher, graphical session, Fabric installation or
Minecraft account is available in this execution environment.

| Environment | Linux | Windows | macOS | Remaining observation |
|---|---|---|---|---|
| Official Launcher, vanilla client | Not launched | Not launched | Unavailable | Actual JVM, classpath, Log4j configuration and loaded pipeline |
| Official Launcher, clean Fabric plus this mod | Not launched | Not launched | Unavailable | Loader version, exact mod JAR and effective runtime configuration |
| Representative additional mods or custom launcher | Not tested | Not tested | Unavailable | Mod list, added logging plugins, agents and pipelines |
| Singleplayer/integrated server | Static/component evidence only | Static/component evidence only | Unavailable | Runtime pipeline and configuration for exact game version |
| Multiplayer client | Not tested | Not tested | Unavailable | Runtime state and safe, non-exploit network behavior |
| Optional dedicated server management endpoint | Selected vanilla bytecode/configuration inspected | Same source evidence | Unavailable | Operator settings and actual runtime handlers; this mod is client-only |

For a real observation, use a disposable test installation and record the game
version, Fabric Loader version, operating system, source commit and mod JAR
SHA-256. Record the Java executable's SHA-256 and version; enumerate the
classpath in order using each JAR's SHA-256 and a non-sensitive component label.
Use an explicitly reviewed, local diagnostic agent or mod that reads only
allowlisted JVM property names and reports the loaded Log4j configuration's
content hash, logger/appenders and relevant handler class names. Record agent
source and hash, and whether it could alter the observed process. Capture
whether each relevant JVM option is present and its non-secret configuration
hash; do not dump raw process arguments, environment variables, account names,
tokens or launcher logs. Unknown or redacted options remain unknown. Compare
clean vanilla, clean Fabric plus this exact mod and each specifically supported
third-party configuration separately. Record only safe local component checks;
do not send remote exploitation payloads. Treat an absent environment or an
unexecuted test as pending, and preserve exact artifact hashes and limitations.
The runtime capture and any instrumentation still need implementation and
verification in an actual supported installation.

## Credential isolation and owner checklist

The historical local compatibility and initial final-build subprocesses
inherited a repository-write-capable `GH_TOKEN`; 25 retained logs lacked its
literal value, but plugin access or network disclosure was not excluded.
Its full permissions, identity, lifetime and current validity remain unknown.
The available personal-account audit endpoint was not accessible through the
CLI; this is not evidence that no activity occurred. The current authenticated
account's repository permissions do not establish the historical token's scope.

The existing local helper strips arbitrary inherited credentials, and the two
hosted audit snapshot workflows pass an empty action token and use an early
Gradle init guard. The coordinated release build now also applies that guard
before project configuration. A local real-Gradle 9.6.1 regression used only
synthetic values: a clean build passed, each of `GH_TOKEN`, `GITHUB_TOKEN` and
`INPUT_GITHUB-TOKEN` was rejected before project configuration, and the local
isolation helper removed all three. Negative controls invoke the Gradle Java
launcher directly because some POSIX shells drop hyphenated environment names
before the JVM starts. This is not a sandbox or proof that every secret source is
blocked. Direct unguarded invocations and filesystem or network access remain
possible. Hosted Gradle 9.9.2 results must be read from the exact-head CI run.

The credential owner must independently:

1. Identify the historical credential and the period covering the initial
   compatibility and final-build attempts; review available account audit and
   security activity and any relevant build/plugin activity for that period.
2. Check its effective scopes, repository access, expiration and current
   validity without sharing the value.
3. Revoke or rotate it if exposure cannot be excluded, review related
   credentials, and verify that legitimate automation uses the replacement.
4. Record the decision and completion without committing a credential or private
   audit details. No revocation or rotation is claimed here.

## Non-publishing replay and remaining gates

Changing the release workflow invalidated its previous rehearsal code hash.
The [new non-publishing replay](../version-consistency-1.0.0/current-validation/rehearsal-2026-11-22-credential-guard/index.json)
ran at coordinator commit `2abc17ccc0761e363ce66411b28671a2112d558b` using the
retained earlier exact-head Linux and Windows product archives. It checked 13
groups, 48 advertised versions and the recorded negative controls. It did not
execute the newly guarded release build or provide current graphical/runtime
evidence. The former rehearsal is preserved unchanged.

Issue #45 remains open: all 490 occurrences block, supported-launcher evidence
is incomplete, compatible upstream remediation remains unverified, and the
credential-owner assessment is pending. Issue #46 separately requires genuine
final-JAR, hardware-GPU and multiplayer acceptance across the advertised matrix;
no component probe substitutes for it. The ten legacy PRs remain security-blocked.
