# Issue 45: bounded Netty Bzip2 investigation

This investigation covers [GHSA-558v-64gr-wgg4](https://github.com/netty/netty/security/advisories/GHSA-558v-64gr-wgg4)
(`CVE-2026-59901`). The upstream advisory identifies a `Bzip2Decoder` input
processing condition that can hang its event-loop thread. Its published fixed
versions are `netty-codec` 4.1.136.Final and `netty-codec-compression`
4.2.16.Final. The affected runtime versions in these sources are supplied by
Minecraft. A compatible game-side upgrade has not been verified; the separate
Critical Netty SNI advisory has later fixed boundaries and must also be
considered. No library override, risk acceptance or security clearance is made.

The [source-bound review](../dependency-evidence/issue45-netty-bzip2-high-2026-11-22/source-bound-review.json)
records all 13 High occurrences across ten candidate/integrated source groups,
including source commits, audit archive hashes, scopes, exact dependency and
client artifacts, metadata identities, product JAR hashes and class digests.
Each occurrence remains **Further investigation** and release-blocking. The
independent [upstream metadata snapshot](../dependency-evidence/issue45-netty-bzip2-high-2026-11-22/upstream-advisory.json)
records the advisory and version boundaries. The historical findings and
earlier priority registers were not changed.

## Observations and limits

* The retained hash-verified manifests identify seven affected Netty codec JARs
  across 28 Minecraft versions. All seven contained `Bzip2Decoder`; the exact
  JAR and class hashes are recorded in the review. Presence alone does not show
  that the class is installed in a live pipeline.
* Selected `Bzip2` name variants were absent from 242,984 class files in the 28
  exact client JARs, 30 classes in 13 retained product JARs, and the inspected
  Fabric Loader 0.20.1 JAR and its one nested JAR. This is a literal search,
  not a complete call graph or runtime observation. Other Minecraft runtime
  libraries, dedicated-server artifacts, other mods, agents, reflection and
  dynamically generated references were not covered by this search.
* Static disassembly of the exact Minecraft 26.2 client shows
  `Connection.setupCompression(int, boolean)` installing Minecraft's
  `CompressionDecoder`, whose bytecode references `java.util.zip.Inflater`.
  The [record](../dependency-evidence/issue45-netty-bzip2-high-2026-11-22/minecraft-26.2-pipeline-observation.json)
  binds both class digests to the hash-verified client. This is a selected
  vanilla code path, not proof of the effective pipeline in a running game or
  the absence of other compression handlers.
* Fabric Loader was inspected as an artifact; no Fabric, launcher, Minecraft
  client or dedicated-server process was launched for this investigation.
  The build inventories do not prove a particular runtime classpath. No
  malformed input or remote vulnerability test was performed.

The [derived priority register](../dependency-evidence/issue45-netty-bzip2-high-2026-11-22/priority-register-v4.json)
now references focused evidence for 130 Critical/High occurrences across 23
advisory IDs. It leaves 69 High occurrences across 14 advisory IDs outside
focused investigations. These counts describe scoped records; they do not
measure independent exploitable vulnerabilities or reduce the 490 retained
blocking occurrences.

## Verification and next work

`python scripts/inspect_issue45_netty_bzip2_high.py` verifies the source-bound
review and derived register offline. The explicit `--verify-codec-download`
and `--verify-client-download` options independently fetch pinned Mojang
artifacts, reject redirects and verify sizes, SHA-1, SHA-256 and the inspected
class bytes. The client check also requires `--javap` and compares a fresh
disassembly to the retained pipeline observation. `--verify-runtime-cache`
rechecks the retained client and manifest cache, all seven codec JARs, the
Fabric artifact and the `javap` observation;
it requires the explicitly named cache paths, Fabric JAR and `javap` executable.
Unit tests use synthetic, harmless archive entries and never need network access.

Next, observe effective pipelines and untrusted-input boundaries in supported
launcher/Fabric configurations and the relevant dedicated server; investigate
other runtime and mod paths; and verify a Minecraft-compatible upstream fix
against all applicable Netty advisories. The historical credential assessment
and Issue 46 graphical/multiplayer acceptance remain independent blockers.
