# Remaining high-priority dependency review — 2026-11-13 UTC

This supplements the [2026-11-12 review](security-high-priority-2026-11-12.md)
with the remaining twelve high-severity advisory IDs in the [current worklist](dependency-evidence/current-security-worklist-2026-11-13.json).
The [original OSV responses](dependency-evidence/high-advisories-2026-11-13/index.json)
were retrieved on 2026-11-13; each response's advisory fingerprint matches the
2026-11-12 source-bound scan. The separate [November 13 OSV rescan](dependency-evidence/1.0.0-osv-rescan-2026-11-13/)
queried all 13 groups using those earlier source-bound snapshots; it did not
re-resolve Gradle dependencies. Package/version/group occurrences, affected
ranges, inventory scopes and source commits remain individually traceable in
that worklist. These individual advisory reads do not by themselves establish
runtime applicability or a resolved disposition.

| Advisory | Trigger and recorded affected packages | Required follow-up |
|---|---|---|
| [GHSA-57rv-r2g8-2cj3](https://osv.dev/vulnerability/GHSA-57rv-r2g8-2cj3), CVE-2026-42584 | Netty `HttpClientCodec` can desynchronize responses with HTTP/1.1 pipelining, a HEAD request and an interim 1xx response. Recorded `netty-codec-http` versions are 4.1.118.Final and 4.2.7.Final; OSV lists fixes 4.1.133.Final and 4.2.13.Final. | Determine whether an affected client pipeline and those response conditions are reachable. |
| [GHSA-6jqx-86gh-f27w](https://osv.dev/vulnerability/GHSA-6jqx-86gh-f27w), CVE-2026-55831 | Netty's SPDY SETTINGS decoder can allocate an unbounded settings map from a peer-controlled frame. Recorded `netty-codec-http` versions are 4.1.118.Final, 4.2.7.Final and 4.2.15.Final; OSV lists fixes 4.1.136.Final and 4.2.16.Final. | Determine whether a peer can reach a configured SPDY codec. |
| [GHSA-7hfm-57qf-j43q](https://osv.dev/vulnerability/GHSA-7hfm-57qf-j43q), CVE-2021-35515 | A crafted 7z archive can cause an infinite codec-list loop in `commons-compress` 1.8.1; OSV lists 1.21 as fixed. | Identify any game, loader or build path that reads untrusted 7z archives. |
| [GHSA-crv7-7245-f45f](https://osv.dev/vulnerability/GHSA-crv7-7245-f45f), CVE-2021-35516 | A crafted 7z archive can exhaust memory in `commons-compress` 1.8.1; OSV lists 1.21 as fixed. | Assess untrusted 7z input and effective resource limits. |
| [GHSA-f6hv-jmp6-3vwv](https://osv.dev/vulnerability/GHSA-f6hv-jmp6-3vwv), CVE-2026-42587 | Netty HTTP decompression limits can be bypassed for Brotli, Zstandard or Snappy content. Recorded `netty-codec-http` versions are 4.1.118.Final and 4.2.7.Final; OSV lists fixes 4.1.133.Final and 4.2.13.Final. | Trace HTTP/1 or HTTP/2 decompressor use, enabled encodings and input trust. |
| [GHSA-jppx-w49h-x2qq](https://osv.dev/vulnerability/GHSA-jppx-w49h-x2qq), CVE-2026-56745 | Netty's SPDY-to-HTTP decoder can leak pooled buffers on reset or oversized content. Recorded `netty-codec-http` versions are 4.1.118.Final, 4.2.7.Final and 4.2.15.Final; OSV lists fixes 4.1.136.Final and 4.2.16.Final. | Determine whether a reachable pipeline instantiates `SpdyHttpDecoder`. |
| [GHSA-mc84-pj99-q6hh](https://osv.dev/vulnerability/GHSA-mc84-pj99-q6hh), CVE-2021-36090 | A crafted ZIP archive can exhaust memory in `commons-compress` 1.8.1; OSV lists 1.21 as fixed. | Determine whether untrusted ZIP input reaches this library rather than a different ZIP implementation. |
| [GHSA-mvh2-crg5-v77c](https://osv.dev/vulnerability/GHSA-mvh2-crg5-v77c), CVE-2026-55833 | Netty's SPDY zlib header decoder can continue inflation after its header limit is exceeded. Recorded `netty-codec-http` versions are 4.1.118.Final, 4.2.7.Final and 4.2.15.Final; OSV lists fixes 4.1.136.Final and 4.2.16.Final. | Determine whether a peer can reach the affected SPDY header pipeline. |
| [GHSA-p979-4mfw-53vg](https://osv.dev/vulnerability/GHSA-p979-4mfw-53vg), CVE-2019-16869 | Netty before 4.1.42.Final can mishandle whitespace before an HTTP header colon and permit request smuggling. `netty-all` 4.1.25.Final is recorded; OSV lists 4.1.42.Final as fixed. | Identify exposed HTTP parsing and any proxy/decoder differential. |
| [GHSA-pwqr-wmgm-9rr8](https://osv.dev/vulnerability/GHSA-pwqr-wmgm-9rr8), CVE-2026-33870 | Netty HTTP/1 chunk-extension quoted-string parsing can permit request smuggling. Recorded `netty-codec-http` versions are 4.1.118.Final and 4.2.7.Final; OSV lists fixes 4.1.132.Final and 4.2.10.Final. | Identify reachable HTTP/1 parsing and upstream proxy behavior. |
| [GHSA-xqfj-vm6h-2x34](https://osv.dev/vulnerability/GHSA-xqfj-vm6h-2x34), CVE-2021-35517 | A crafted TAR archive can exhaust memory in `commons-compress` 1.8.1; OSV lists 1.21 as fixed. | Identify whether untrusted TAR archives reach this library and whether resource limits apply. |
| [GHSA-rwm7-x88c-3g2p](https://osv.dev/vulnerability/GHSA-rwm7-x88c-3g2p), CVE-2026-42577 | A reset on a half-closed connection can leave Netty epoll channels stale or spinning. `netty-transport-classes-epoll` 4.2.7.Final is recorded; OSV lists 4.2.13.Final as fixed. The worklist says HIGH, while the advisory prose says Medium and also gives CVSS 7.5. | Verify use of the epoll transport, half-close behavior and remote reachability; reconcile the severity wording during review. |

All twelve remain **Further investigation** and failing. Their affected
libraries are supplied by the recorded Minecraft runtimes; individual
occurrences can additionally be present in Gradle inventories. No finding is
resolved or accepted merely because the mod does not bundle a library. Do not
override Minecraft-managed libraries without a compatible, reviewed fix.
