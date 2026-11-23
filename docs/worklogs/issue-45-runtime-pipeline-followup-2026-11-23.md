# Issue 45: runtime pipeline follow-up

This is new evidence after PR #66. It does not change the earlier LZ4
worklog's statement that PR #66 contained static analysis only.

## Repository and review baseline

The current main at task start was
`8650a8a1195e04b865c8c977361ba99ae54b2dbc`. PR #65 is merged; its standalone
`--javap` review comment is addressed by the negative CLI regression in the
merged implementation. PR #66 is merged with no public review submissions or
discussion comments. Issues #45 and #46 remain open; #44 is closed. The
historical ten port PRs remain open and release-blocked.

## Executed engineering work

`diagnostics/issue45-runtime` adds a separate opt-in Java agent, deterministic
builder, source-bound validator, synthetic controls, and an operator run
procedure. The agent instruments `AbstractChannel` construction,
`DefaultChannelPipeline$HeadContext.channelActive`, and `DefaultChannelPipeline`
handler add/remove callbacks. It reports loaded Netty and Fabric class
identities, hashes code-source JARs, and records sanitized process/classpath
metadata. It does not modify the product mod or any Minecraft-managed
dependency. It never reads environment variables, captures raw process command
lines, or records remote addresses.

The synthetic harness executed real local `EmbeddedChannel` pipelines against
four exact module sets: Minecraft 1.19 manifest Netty 4.1.77.Final; Minecraft
26.2 manifest Netty 4.2.15.Final; and isolated Maven Central candidates
4.1.137.Final and 4.2.17.Final. In every process the recorder transformed
Netty's `DefaultChannelPipeline`, recorded channel-active pipeline snapshots,
and distinguished an installed
`Lz4FrameDecoder`, `JdkZlibDecoder`, and plain inbound handler. The plain
pipeline contained neither decoder. Each process exited zero, emitted a
shutdown-hook record, and redacted a synthetic access-token property. No
socket or frame data was used. The exact agent SHA-256 is recorded in
`synthetic-control-verification.json`; it is reproducible from the pinned
builder inputs.

These are recorder controls only. The workspace has Java 21 but no Minecraft
launcher or game installation and no authenticated client session. No real
client, Fabric client, or dedicated server was launched. The six rows in
`environment-matrix.json` are all `not_executed`. They are not passes.

## Minecraft 1.19 dependency reconciliation

The new targeted revalidation re-fetched the official Minecraft 1.19 version
manifest, client `netty-codec`, server bundle, and only the server's nested
`netty-codec`. All official SHA-1/size metadata and retained SHA-256 values
matched. The client uses Netty 4.1.77.Final; the bundled server module is
4.1.76.Final. This is an expected official client/server artifact divergence
and a historical audit-scope omission: the server JAR was outside the exact
12 indexed High occurrences and remains a separately traceable artifact.

The process-runtime dependency selection remains unresolved. No running
server class loader proved that the bundle's nested JAR was loaded. The
reconciliation report preserves this distinction and does not modify the
historical count.

The same retained server-bundle scan pins Minecraft 26.1.2's dedicated-server
bundle and Netty 4.2.7.Final `netty-codec-compression` artifact separately
from the client manifest. Its process selection is also unobserved. The 26.2
matrix entry is a client target; no runtime row is inferred from a manifest
as proof of a separate dedicated-server bundle.

## Reachability and compatibility

The evidence record keeps all nine reachability levels separate. Manifest and
bundle presence are confirmed; actual game classpath selection, class loading,
decoder construction, Minecraft pipeline installation, remote input,
pre-authentication state, and game-level resource limits were not observed.
No frame was sent and no denial-of-service experiment was run. Retained
Minecraft 26.1.2 disassembly uses Minecraft's Zlib `Inflater` decoder, but
that is not evidence from a running process.

The current priority register contains 15 focused Netty advisory IDs. Its
maximum fixed boundaries are 4.1.137.Final and 4.2.17.Final. Synthetic
Java 21 controls show the recorder works with those component candidates;
they do not prove Minecraft or Fabric ABI compatibility. Minecraft 26.2's
4.2.15.Final meets the LZ4 advisory's 4.2.13.Final boundary, but not the
maximum boundary for the focused Netty set. No dependency override or Fixed
disposition was made.

## Remaining blockers

The historical security inventory remains 490 blocking occurrences: 22
Critical, 177 High, 274 Moderate, and 17 Low. The 45 unfocused High
occurrences across 12 advisory IDs remain. The next target selected directly
from priority register v6 is GHSA-6jqx-86gh-f27w / CVE-2026-55831, four
unfocused High `netty-codec-http` occurrences, with 26.2 at 4.2.15.Final and
the retained fixed boundary at 4.2.16.Final.

Historical `GH_TOKEN` disclosure remains unresolved pending the owner
handoff's token-permission, audit, inheritance, and revoke/rotation evidence.
Issue #46 remains separate: exact final-JAR provenance, 48-version runtime
acceptance, hardware-GPU visuals, both hand/off-hand layouts, left/right
handedness, first-person regressions, multiplayer map-data synchronization,
and the foreground rendering artifact still need evidence.

The full executable instructions, exact per-environment blockers, input
boundary record, source hashes, and validation command are in
`docs/dependency-evidence/issue45-runtime-pipeline-2026-11-23/`.
