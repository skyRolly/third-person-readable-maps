# Issue 45: High Netty SNI resource-exhaustion investigation

`GHSA-x4gw-5cx5-pgmh` / `CVE-2026-45416` affects the SNI handler in
`io.netty:netty-handler` and is classified High. The
[upstream Netty advisory metadata](../dependency-evidence/issue45-netty-sni-high-2026-11-22/upstream-advisory.json)
identifies fixed versions 4.1.135.Final and 4.2.15.Final. This finding concerns
resource exhaustion; it has different consequences and preconditions from the
Critical SNI fallback finding. No network payload or vulnerability reproduction
was used for this investigation.

The [source-bound review](../dependency-evidence/issue45-netty-sni-high-2026-11-22/source-bound-review.json)
binds the 12 failing occurrences to their exact source commits, audit archives,
package versions, scopes, Minecraft client hashes and mod JAR hashes. Ten
candidate and two integrated occurrences cover 10 source groups and 27 Minecraft
versions. The affected versions of the handler in these occurrences are
4.1.77.Final, 4.1.82.Final, 4.1.97.Final, 4.1.115.Final, 4.1.118.Final and
4.2.7.Final. These are game-manifest dependencies; a `gradle` scope also records
resolution in a development graph and does not establish that the vulnerable
handler is a Gradle plugin. No mod-level replacement was made.

For this follow-up, six locally cached upstream JARs were rechecked against the
previously retained SHA-1 and SHA-256 values, and the SNI-related class entries
were hashed. The [local artifact record](../dependency-evidence/issue45-netty-sni-high-2026-11-22/local-artifact-verification.json)
records those observations. The upstream advisory also names the lower-level
`SslClientHelloHandler`, which the earlier SNI-name search did not independently
cover. A [new offline classpath scan](../dependency-evidence/issue45-netty-sni-high-2026-11-22/clienthello-classpath-scan.json)
verified and scanned 471 cached client/default-runtime JARs containing 369,335
class files across the 27 affected game versions. It found 18 literal references
inside Netty handler classes and none outside them. Earlier hash-bound inspection
of 29 vanilla client/default-runtime classpaths, including all 27 versions here,
found no non-Netty `SniHandler` name references. The selected mod JAR literal
scan also found none. The selected dedicated management bytecode uses an
`SslHandler` directly. CI validates the recorded hashes and relationships; it
does not independently redownload or rescan those JARs. These observations do
not establish the behavior of every dedicated-server distribution, custom
launcher, Java agent, other mod or dynamically assembled pipeline.

Exposure requires an installed affected SNI or ClientHello handler, including a
subclass, to process untrusted TLS handshake input. That path is not established
for the inspected vanilla client classpaths, but it remains unknown in supported
modded or customized runtime configurations. The 12 occurrences therefore remain
**Further investigation** and release-blocking. Their reviewer, scope, evidence
and follow-up are recorded without a risk-acceptance decision.

The prior manifests show Minecraft 26.2 with handler 4.2.15.Final and 26.3 with
4.2.16.Final, both beyond this High advisory's affected 4.2 range. This is an
observation about those exact game versions, not a verified compatible update
for affected older versions. The separate Critical SNI advisory still affects
those library versions and identifies later fixed endpoints. Any game-side
remediation must cover both advisories and preserve module compatibility.

The [updated priority register](../dependency-evidence/issue45-netty-sni-high-2026-11-22/priority-register-v2.json)
preserves the earlier register and adds this bounded investigation: 21 focused
advisory IDs and 105 focused Critical/High occurrences, with 94 High occurrences
still outside the focused set. All 199 Critical/High occurrences and all 490
overall findings remain failing. `python3 scripts/inspect_issue45_sni_high.py`
checks the retained relationships without network access. Supported-launcher,
Fabric/modpack and owner credential observations remain open, as do Issues #45
and #46.
