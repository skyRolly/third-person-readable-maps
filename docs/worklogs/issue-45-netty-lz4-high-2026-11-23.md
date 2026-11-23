# Issue 45: bounded Netty Lz4FrameDecoder investigation

This source-bound follow-up covers [GHSA-mj4r-2hfc-f8p6](https://github.com/advisories/GHSA-mj4r-2hfc-f8p6)
(`CVE-2026-42583`). The advisory identifies an allocation risk in
`io.netty.handler.codec.compression.Lz4FrameDecoder`: an untrusted frame header
declares the decompressed length, which the decoder uses to size a buffer before
decompression. Netty lists `netty-codec` 4.1.133.Final and
`netty-codec-compression` 4.2.13.Final as fixed boundaries. The retained
[upstream snapshot](../dependency-evidence/issue45-netty-lz4-high-2026-11-23/upstream-advisory.json)
is bound by SHA-256
`cfaeba6cf6352a1708c76d39db0c360fc6e54cbef7505f8704dadaee6693da4b`.

The [source-bound review](../dependency-evidence/issue45-netty-lz4-high-2026-11-23/source-bound-review.json)
requires exact equality with all 12 indexed High occurrences across ten source
groups, preserving source commits, package versions, scopes, fingerprints,
report identities and hashes, manifest identities, artifact hashes, dependency
ownership and blocking dispositions. All 12 remain **Further investigation**,
release-blocking and unaccepted. The earlier Trust Manager evidence remains
preserved at its own v5 register.

## Static observations

* The exact 27 retained Minecraft version manifests identify 471 unique client
  and runtime artifacts. Their 369,335 class files contain 18 selected literal
  hits, all in the LZ4 decoder and its two inner classes inside six Netty codec
  JARs: `netty-codec` 4.1.77, 4.1.82, 4.1.97, 4.1.115 and 4.1.118, plus
  `netty-codec-compression` 4.2.7. No non-Netty decoder-name caller was found
  in this bounded search.
* All 27 official dedicated-server bundles and 983 nested JARs were scanned,
  covering 782,120 class files and 81 decoder-class hits. The hits were in
  bundled Netty codec JARs. The 1.19 server bundle contains Netty 4.1.76.Final,
  while the indexed client manifest uses 4.1.77.Final. That additional affected
  server artifact is recorded separately because it is outside the indexed 12
  source-audit occurrence identities and needs dependency-owner reconciliation.
* The selected Fabric Loader 0.20.1 classes and nested MixinExtras JAR, plus
  all 13 retained product JARs, had no selected decoder-name hits.
* Static disassembly of exact Minecraft 26.1.2 client and dedicated-server
  classes shows `Connection.setupCompression` installing Minecraft's
  `CompressionDecoder`; that decoder uses `java.util.zip.Inflater`. The
  selected classes contain no `Lz4FrameDecoder` reference. No channel was
  observed running.
* Exact Mojang 26.2 and 26.3 manifests and server bundles select
  `netty-codec-compression` 4.2.15.Final and 4.2.16.Final, respectively. These
  versions are beyond the advisory's 4.2.13 fixed boundary. They do not update
  older supported game lines or establish which classpath a launcher used.

These are bounded static observations. No Minecraft client, Fabric runtime,
dedicated server or modpack was launched. No frame, proof of concept, remote
target or resource-exhaustion behavior was exercised. Literal searches do not
exclude reflection, generated code, agents, native paths, or uninspected mods.
No per-channel or aggregate allocation control was measured. The review does
not establish game-level exploitability or non-reachability.

## Compatibility and disposition

Netty's fixed decoder source adds a configurable per-decoder maximum; its
default remains 32 MiB. The source review does not establish aggregate or
per-channel limits in Minecraft. Netty's fixed modules declare Java 8
compatibility, below the Java 17, 21 and 25 runtime requirements in the
affected and newer Minecraft manifests. Java bytecode level alone does not
establish Minecraft, Fabric, module-family or ABI compatibility.

The separate Critical Netty SNI advisory requires at least 4.1.135.Final or
4.2.15.Final, and Trust Manager requires those same fixed lines. The LZ4-only
boundaries would not clear those findings. Mojang supplies the affected
dependencies in the retained game versions; no dependency override was made.
The 26.2/26.3 fixed-boundary observations do not clear older versions or other
Netty findings.

The [derived priority register](../dependency-evidence/issue45-netty-lz4-high-2026-11-23/priority-register-v6.json)
now covers 25 focused advisory IDs and 154 focused Critical/High occurrences.
45 High occurrences across 12 advisory IDs remain without focused evidence.
The retained inventory remains 490 blocking occurrences. These counts are
not a new dependency scan. No security clearance, risk acceptance, release or
Minecraft-managed dependency override is authorized.

## Verification and next work

`python scripts/inspect_issue45_netty_lz4_high.py` validates the retained
advisory, source reports, artifact and class observations, review and register
offline. Its explicit `--verify-cache` mode rechecks all 471 runtime artifacts,
27 server bundles, Fabric Loader, the 26.2/26.3 fixed-boundary artifacts and
the 26.1.2 static disassembly from local hash-verified caches. The tests mutate
occurrence identities, report provenance, runtime and server observations,
fixed boundaries and pipeline evidence to prove those checks reject changes.

Next, observe actual supported client, Fabric and dedicated-server classpaths
and pipelines separately, resolve the 1.19 server/client Netty discrepancy,
and ask Minecraft/Fabric owners about compatible updates across affected game
lines. Historical repository-write-capable credential exposure and Issue 46's
full final-JAR graphical and multiplayer acceptance remain independent
blockers.
