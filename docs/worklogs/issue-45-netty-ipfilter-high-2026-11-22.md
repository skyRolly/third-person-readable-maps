# Issue 45: High Netty IP-filter investigation

`GHSA-3qp7-7mw8-wx86` / `CVE-2026-44249` concerns IPv6 access rules when an
affected Netty subnet filter is installed. [Netty's advisory](../dependency-evidence/issue45-netty-ipfilter-high-2026-11-22/upstream-advisory.json)
identifies fixes in 4.1.135.Final and 4.2.15.Final. The 12 scoped matches cover
10 source groups and 27 game versions. The affected handler versions are
4.1.77, 4.1.82, 4.1.97, 4.1.115, 4.1.118 and 4.2.7. Minecraft's runtime
manifests supply these libraries; a Gradle scope does not itself prove a build
plugin uses the affected API. A newer game-library override was not applied.
The separate Critical Netty SNI advisory requires later fixed versions.

The [source-bound review](../dependency-evidence/issue45-netty-ipfilter-high-2026-11-22/source-bound-review.json)
binds each occurrence to its source commit, audit archive, package version,
scope, client artifact and mod JAR hashes. An offline [classpath scan](../dependency-evidence/issue45-netty-ipfilter-high-2026-11-22/vanilla-classpath-scan.json)
rechecked 471 previously catalogued client/default-runtime JARs and 369,335
class files against their retained hashes. It found 66 selected literal-reference
hits inside the six Netty IP-filter implementations and none outside them. A
separate reinspection of the six Netty JARs pins the 66 known class entries;
the validator requires their complete identities and checks all artifact rows.
The offline validator checks retained record relationships; the hosted
`--verify-known-download` check independently fetches the six exact Mojang
Netty JARs, verifies their pinned sizes and hashes, and compares the 66 observed
class entries with those bytes. No remote vulnerability test or exploitation
was performed.

The [product JAR scan](../dependency-evidence/issue45-netty-ipfilter-high-2026-11-22/product-jar-static-scan.json)
rechecked 13 retained source-bound JARs and 30 classes with no selected literal
hits. The [Fabric scan](../dependency-evidence/issue45-netty-ipfilter-high-2026-11-22/fabric-loader-static-scan.json)
checked the official Fabric Loader 0.20.1 JAR against its SHA-1 sidecar and
SHA-256, including its one nested JAR; 771 outer and 506 nested classes had no
selected literal hits. That loader version appears in the source-bound Gradle
inventories, but no launcher process was observed to establish its effective
runtime classpath.

These are class-file searches, not a game execution trace. They do not exclude
indirect calls, generated names, custom launchers, other mods, agents or separate
dedicated-server distributions. The reachable input boundary and compatible
game-side remediation remain unverified, so all 12 occurrences remain **Further
investigation** and release-blocking. No risk is accepted.

Run `python3 scripts/inspect_issue45_netty_ipfilter_high.py` to verify the
retained source and report bindings. With the exact locally cached artifacts,
`--runtime-cache <sha1-keyed-cache> --fabric-jar <fabric-loader-jar>` also
rehashes and rescans those JARs. The [updated register](../dependency-evidence/issue45-netty-ipfilter-high-2026-11-22/priority-register-v3.json)
records 117 focused Critical/High occurrences across 22 advisory IDs; 82 High
occurrences across 15 IDs remain outside the focused set. All 490 audit findings
remain failing.
