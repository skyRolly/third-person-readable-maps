# Issue #45 LZ4 runtime follow-up — 2026-11-22

PR #53 adds source-bound LZ4 reachability evidence for `GHSA-cmp6-m4wj-q63q` / `CVE-2025-66566`, `GHSA-vqf4-7m7x-wgfc` / `CVE-2025-12183`, and the already tracked `GHSA-mcr4-qmvw-px4g` / `CVE-2026-106451`. The full investigation is in [lz4-reachability-2026-11-22.json](../dependency-evidence/critical-reachability-2026-11-21/lz4-reachability-2026-11-22.json).

## Findings

- Hash-verified official Minecraft client scans cover 19 exact versions across eight source groups. Each contains a direct `RegionFileVersion` caller for `LZ4BlockInputStream`; the direct region path selects compression id 4 from a chunk record. Captured bytecode confirms id 4 is `lz4`, that server.properties selects the write default, and that the default writer uses deflate id 2. Existing chunks remain readable by their recorded codec.
- Representative vanilla chunk-packet captures use a distinct packet decoder path. They do not establish that arbitrary mod, reflection, launcher, or agent paths are safe. An untrusted imported/downloaded local world is a plausible input to the confirmed region-file path. No vanilla remote multiplayer LZ4 input path was demonstrated.
- The bounded upstream CMP6 vector test reproduced non-zero output on the affected Java decompressor implementations: 923 output bytes for `at.yawk` 1.8.1; `org.lz4` 1.8.0 selected JNI fast decompression on this Linux runner and showed zero for this test set, while its Java variants showed 923. `at.yawk` 1.10.1 and 1.11.4 showed zero for all tested variants. The experiment is a component test, not a Minecraft exploit or exfiltration test.
- Native extraction was observed in pinned 1.8.0, 1.8.1 and 1.10.1 artifacts. The 1.11.4 artifact did not create the observed lock file. This runner defaults to `/tmp` (mode 1777; `protected_regular=0`), but the race was not attempted and user launcher policies are unknown.
- Every affected dependency is Minecraft-manifest runtime-owned. No mod-controlled override is justified. Upstream fixes were inspected; the exact `LZ4BlockInputStream(InputStream)` linkage is present in the captured fixed releases. No fix was applied to the repository or game-managed runtime.

## Disposition and verification

The five `GHSA-vqf4` rows, six `GHSA-cmp6` rows, and eight `GHSA-mcr4` rows remain **Further investigation**, failing, and release-blocking. These are scoped advisory occurrences that overlap; they are not 19 independent vulnerabilities. No risk is accepted and no clearance is claimed. Focused high findings increased by 11, from 60 to 71; the focused total is 22 Critical + 71 High = 93. The full source inventory remains 490 failing occurrences (385 candidate, 105 integrated).

Local dependency behavior checks passed 38/38 expected cases, including eight LZ4 cases. Exact client scanning covered 19 versions and eight groups. Linux and Windows hosted CI plus the source-bound validator are rerun on the PR commit. A full Minecraft build or in-game malformed region test is not claimed.

Remaining evidence gaps include an isolated game-level malicious region-file test, Windows/macOS native/fallback selection, a non-destructive shared-temp race experiment, third-party/modded runtime paths, and Mojang’s compatible dependency update. Issue #45 remains open.
