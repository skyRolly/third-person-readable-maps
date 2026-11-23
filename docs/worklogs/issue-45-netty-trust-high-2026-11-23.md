# Issue 45: bounded Netty Trust Manager investigation

The upstream [GHSA-c653-97m9-rcg9](https://github.com/netty/netty/security/advisories/GHSA-c653-97m9-rcg9)
(`CVE-2026-50010`) describes a hostname-verification problem in certain Netty
trust-manager configurations. Upstream lists `netty-handler` 4.1.135.Final
and 4.2.15.Final as fixed versions for this advisory. Minecraft supplies the
affected runtime libraries in the retained sources; some coordinates also
appear in Gradle resolution. The separate Critical Netty SNI advisory has later
fixed-version boundaries. Compatibility of newer libraries with the affected
game and Java versions has not been verified, and no replacement was made.

The [source-bound review](../dependency-evidence/issue45-netty-trust-high-2026-11-23/source-bound-review.json)
binds all 12 High occurrences across ten source groups to their exact source,
package, scopes, advisory fingerprint, compressed and uncompressed audit report
hashes, 27 version metadata and client identities, handler class digests and
product JAR hashes. All 12 remain **Further investigation**, release-blocking
and unaccepted. The previous Bzip2 register and all historical reports remain
unchanged.

The same source group's hash-verified Minecraft 26.2 manifest and retained
audit inventory list `netty-handler` 4.2.15.Final, the upstream fixed boundary
for this advisory. This is a version-specific upstream observation: the actual
launched classpath was not observed, the 26.1 variants still have affected
occurrences, and the separate Critical SNI advisory remains a blocker for
4.2.15.Final. The shared maintenance group is not cleared.

## Static observations

* A hash-verified literal search covered 471 official vanilla client and
  default-runtime JARs containing 369,335 class files across the 27 affected
  Minecraft versions. Six pinned Netty handler JARs contained the selected
  trust-manager classes. The selected class identities and byte hashes are
  retained in [known handler observations](../dependency-evidence/issue45-netty-trust-high-2026-11-23/known-handler-class-hits.json).
* Six client JARs contained a selected `SslContextBuilder` reference. The
  [management observations](../dependency-evidence/issue45-netty-trust-high-2026-11-23/management-static-observations.json)
  bind those class bytes to prior hash-verified disassemblies. The selected
  bytecode describes management-server-related TLS construction, including a
  JDK trust-manager factory passed to a server context builder. This is static
  code evidence, not an observed live pipeline or certificate-validation test.
* The selected name literals were absent from 13 retained product JARs and the
  inspected Fabric Loader 0.20.1 JAR and its nested JAR. Literal absence does
  not exclude indirect calls, reflection, generated references or other mods.

No Minecraft launcher, client, dedicated server, TLS session or certificate
validation behavior was run in this investigation. Effective runtime
providers, classpaths, configuration, third-party mods and dedicated-server
distributions remain unverified. Neither the positive references nor the
negative literal search establish exploitability or non-applicability.

The [derived priority register](../dependency-evidence/issue45-netty-trust-high-2026-11-23/priority-register-v5.json)
links focused evidence for 142 Critical/High scoped occurrences across 24
advisory IDs. It leaves 57 High occurrences across 13 IDs without focused
investigation. The retained audit baseline is unchanged at 490 blocking
occurrences; this is not a fresh OSV scan or a security-clearance decision.

## Verification and next work

`python scripts/inspect_issue45_netty_trust_high.py` validates retained records,
occurrence identity and exact report provenance without network access. The
explicit `--verify-known-download --verify-management-download
--verify-fixed-download --javap javap` mode independently verifies the six
affected handler JARs, a selected 26.1 client and disassembly, and the 26.2
manifest and fixed-boundary handler JAR. Retained JSON
consistency alone is not independent class-byte verification. The hosted
download mode does not download or dynamically launch all 27 clients.

With the pinned SHA-1-keyed runtime cache and Fabric JAR available locally,
reinspect the full cached classpath without network downloads. In addition to
the 471 scanned JARs, the runtime cache must contain the 26.2 handler JAR
`d5344afd1148e3b9927a74be019605ebb0937a93`; the manifest cache must contain
the matching `26.2.json` from the recorded Mojang metadata source:

```sh
python scripts/inspect_issue45_netty_trust_high.py \
  --runtime-cache /path/to/sha1-keyed-jars --fabric-jar /path/to/fabric-loader-0.20.1.jar \
  --manifest-cache /path/to/version-json \
  --javap /path/to/jdk-21/bin/javap
```

Next, assess the supported launcher and mod configurations, actual TLS trust
boundaries and relevant dedicated-server distributions, and verify a compatible
upstream game update. Historical credential assessment and Issue 46's final-JAR
graphical and multiplayer acceptance remain independent blockers.
