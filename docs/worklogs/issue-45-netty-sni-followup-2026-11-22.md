# Issue #45 Netty SNI reachability follow-up — 2026-11-22

## Scope and sources

Investigated `GHSA-c4c3-7fpv-j4q5` / `CVE-2026-75595` against source-bound Netty occurrences from the 13 candidate/integrated source groups. Fourteen occurrences across eleven source groups use Minecraft-manifest-owned `io.netty:netty-handler` versions. The immutable source SHA, runtime scope, Netty package version and per-version Minecraft client hashes remain in `source-bound-dispositions-2026-11-21.json`.

The full scan report is `docs/dependency-evidence/critical-reachability-2026-11-21/netty-vanilla-classpath-scan-2026-11-22.json`. It verifies all 29 affected official Mojang manifests and 612 unique client/runtime JARs (1,300,288,588 bytes), then scans 414,135 `.class` entries for direct and reflective `SniHandler` class-name strings and `SslHandler`/`SslContext` references. Artifact sizes and SHA-1 values were checked against official metadata. The scan found 46 SNI string hits, all within `io.netty:netty-handler`'s own `io/netty/handler/ssl/` implementation classes; it found zero non-Netty SNI callers. The remaining 401 TLS-context hits include Netty implementation classes and optional management-server classes; the focused report records the exact 8 Minecraft client versions with first-party TLS references.

Reproduction from the captured pinned cache: `python3 scripts/inspect_netty_sni_client_reachability.py --cache /tmp/issue45-netty-reachability/jars --source-commit 956c28254afa347d222304947e4a9878e78d209a --output docs/dependency-evidence/critical-reachability-2026-11-21/netty-vanilla-classpath-scan-2026-11-22.json`. Add `--download` to fetch missing artifacts; the script checks the Mojang manifest size and SHA-1 before accepting each artifact.

## Runtime path and configuration

The named client packet-path captures for 1.21.10 and 26.3 remain indexed in the Guava packet path evidence. The 1.21.10 path uses Netty sockets and Minecraft packet handlers; the 26.3 `Connection` path is separately captured. Exact `IntegratedServer` class constant-pool checks for 1.21.10, 1.21.11 and 26.3 contain no management-server, `SniHandler`, `SslHandler` or `SslContext` marker.

The optional TLS JSON-RPC endpoint appears in dedicated-server code. Captured bytecode for 1.21.10, 1.21.11 and 26.3 shows `DedicatedServer`/`Main` create the management server only under its explicit server setting. Defaults are `management-server-enabled=false`, host `localhost`, and `management-server-tls-enabled=true` if the endpoint is enabled. An operator can change the bind host. `ManagementServer$1` inserts `SslContext.newHandler()` as an `SslHandler`, followed by HTTP and WebSocket handlers, including `AuthenticationHandler`; it does not install SNI routing. The provider calls `SslContextBuilder.forServer(keyManager).trustManager(trustManager).build()` and does not call `clientAuth()`. Exact `SslContextBuilder` bytecode for all eight affected handler versions initializes `ClientAuth.NONE`. Authentication is an API-key check, not SNI-selected mutual TLS. The full class and mapping digest index is `netty-callpath-bytecode-index-2026-11-22.json`.

## Upstream probe and disposition

The upstream advisory describes a fallback to the default `SslContext` when an SNI `ClientHello` is fragmented across TLS records; the security impact requires SNI-specific mTLS to be the only gate and a more permissive default context. The pinned local component probe confirms the vulnerable fallback in representatives 4.1.118, 4.2.7 and 4.2.15, and confirms host selection in fixed 4.1.137 and 4.2.17. The probe does not simulate Minecraft or prove an authentication bypass.

Conclusion: the advisory-specific path was not found in exact unmodified vanilla client or integrated-server code, including the optional dedicated management TLS route. This is strong evidence about those official artifacts, not about arbitrary third-party mods, custom launcher classpaths, agents, reflection combined with runtime-loaded code or pipeline mutation. All 14 records remain blocking: 13 `Further investigation` and the existing 26.2 `Upstream-dependent` record. Minecraft owns the affected dependency; no compatible Mojang update is in these manifests, so no dependency override was applied. Risk acceptance remains false and security clearance remains false.

## Verification

- Source-bound scanner: 29 Minecraft versions, 612 unique official client/runtime JARs, 414,135 classes; all artifact sizes and SHA-1 values verified; zero non-Netty `SniHandler` caller references.
- Focused `javap` captures: 1.21.10, 1.21.11, 26.3 game classes and all eight exact affected `SslContextBuilder` artifacts. Full client mappings for obfuscated versions were fetched from the URLs pinned in the Mojang version metadata and SHA-1 verified; extracted mapping blocks and class/output hashes are indexed.
- Component probe: all five existing Netty SNI cases matched expected behavior. No Minecraft-level exploit or live dedicated-server TLS test is claimed.
- Inventory counts unchanged: 490 total occurrences (385 candidate, 105 integrated); focused 22 Critical + 71 High = 93 blockers.

## Remaining blockers

1. Inspect concrete supported mod sets, custom launcher classpaths and Java agents, or define and verify a bounded supported runtime.
2. Request/consume Mojang updates to 4.1.137.Final or 4.2.17.Final for maintained game lines; do not override game libraries in this mod.
3. Obtain independent human security review and keep Issue #45 open. The historical `GH_TOKEN` owner assessment remains a separate outstanding action.
