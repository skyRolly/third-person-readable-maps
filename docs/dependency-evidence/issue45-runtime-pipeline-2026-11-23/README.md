# Issue 45 runtime pipeline evidence

This evidence set separates executable collection infrastructure from
observations of supported Minecraft processes. The current workspace has no
Minecraft launcher/game installation or authenticated client session. No
Minecraft client, Fabric client, or dedicated server was launched here. Rows
in `environment-matrix.json` are explicitly `not_executed`; no runtime pass
or negative reachability conclusion is claimed.

The diagnostic agent and pinned synthetic controls are under
[`diagnostics/issue45-runtime`](../../../diagnostics/issue45-runtime/README.md).
The agent observes `AbstractChannel` construction, snapshots the pipeline at
`DefaultChannelPipeline$HeadContext.channelActive`, and records handler
add/remove callbacks. Synthetic records confirm those hooks execute on the
tested Netty module sets; real game processes have not been observed.
The synthetic controls executed against exact Netty 4.1.77.Final modules from
the retained Minecraft 1.19 manifest, exact Netty 4.2.15.Final modules from
the retained Minecraft 26.2 manifest, and isolated 4.1.137.Final/4.2.17.Final
upstream candidate module sets. They verified add-handler observation for a
real `Lz4FrameDecoder`, Netty's `JdkZlibDecoder`, and a plain handler, along
with the loaded-class control and credential-value sanitization. The fixed
candidate runs show only that the diagnostic and synthetic pipeline controls
work with those Netty families; they do not establish Minecraft or Fabric ABI
compatibility. None of these tests are game evidence.

The 1.19 artifact check can be repeated with
`python3 diagnostics/issue45-runtime/revalidate_119_artifacts.py`. It fetches
only the official 1.19 manifest, client Netty codec, server bundle, and one
nested server Netty codec. Rebuild the compatibility derivation with
`python3 diagnostics/issue45-runtime/assess_upstream_compatibility.py`; it
reads the retained register and manifest copies rather than rescanning the
artifact inventory. The source-bound environment matrix also pins the
26.1.2 dedicated-server bundle and nested `netty-codec-compression` JAR to the
exact retained scan identities; this does not claim that the server process
selected those bytes.

## Reproducible process launch

Build the standalone agent and record the resulting digest:

```sh
python3 diagnostics/issue45-runtime/build_agent.py \
  --output /absolute/path/issue45-runtime-agent.jar
sha256sum /absolute/path/issue45-runtime-agent.jar
```

For each run, create a private Java properties file outside the repository.
Set `output` to a private JSONL destination, `sourceSha` to the exact source
commit of the product JAR being tested, and `productJar` to that JAR when the
mod is installed. For a Fabric run also set `fabricLoaderVersion` and
`modsDirectory`. Do not put credentials, account data, or server addresses in
the file. Use these matrix identities:

| Environment | `minecraftVersion` | `distribution` | `launcher` | Additional properties |
| --- | --- | --- | --- | --- |
| `minecraft-1.19-client` | `1.19` | `client` | `official` | — |
| `minecraft-1.19-dedicated-server` | `1.19` | `server` | `official-server-bundle` | — |
| `minecraft-1.21.11-fabric-client` | `1.21.11` | `client` | `official` | `fabricLoaderVersion=0.20.1`; exact `productJar` and `modsDirectory` |
| `minecraft-26.1.2-client` | `26.1.2` | `client` | `official` | — |
| `minecraft-26.1.2-dedicated-server` | `26.1.2` | `server` | `official-server-bundle` | — |
| `minecraft-26.2-client` | `26.2` | `client` | `official` | — |

Append this single JVM argument to the official launcher's Java arguments
for a client or Fabric run, substituting absolute paths:

```text
-javaagent:/absolute/path/issue45-runtime-agent.jar=/absolute/path/issue45-runtime.properties
```

For a dedicated server whose official start command is `java -jar server.jar`,
keep that command and its memory arguments intact, adding the same agent token
before `-jar`:

```sh
java -javaagent:/absolute/path/issue45-runtime-agent.jar=/absolute/path/issue45-runtime.properties \
  -Xms1G -Xmx2G -jar /absolute/path/server.jar nogui
```

If the official server bundle supplies a launcher script or JVM-argument file,
use that official entry point and add the agent token to its JVM arguments; do
not rebuild its classpath. Follow the server owner's EULA decision manually.
For both client and dedicated-server channel coverage, connect an
operator-controlled client to an operator-controlled local server so both
ends observe an active socket pipeline. Do not use a public server. Stop each
process normally so `process_end` is flushed. Record each operator-observed
exit code and sanitized startup outcome in the corresponding matrix row.
These are execution instructions; no command above was run for a Minecraft
process in this workspace.

## Per-run evidence format

After each real launch, copy the agent's sanitized JSON Lines file into
`captures/<environment-id>.jsonl`, calculate its SHA-256, and update only that
environment row with `status: "captured"`, the file path, and digest. Record
the operator-observed JVM exit status and any startup error in the matrix.
Do not copy raw launcher logs or unredacted command lines. Keep `sourceSha`
bound to the exact repository commit whose product JAR was tested, and set
`productJar` to that exact JAR where one is part of the environment.

Validate the full archive with:

```sh
python3 diagnostics/issue45-runtime/validate_runtime_evidence.py \
  --evidence-dir docs/dependency-evidence/issue45-runtime-pipeline-2026-11-23
```

For synthetic CI or an operator rerun that must preserve the checked-in
archive, create a **new** evidence directory (it must not already exist)
with `--fresh-evidence-dir`. This copies the non-synthetic historical
records byte-for-byte and excludes all retained synthetic reports and
observations before running the controls:

```sh
python3 diagnostics/issue45-runtime/run_controls.py \
  --work-dir /path/to/control-work --fresh-evidence-dir /path/to/new-evidence
python3 diagnostics/issue45-runtime/validate_runtime_evidence.py \
  --evidence-dir /path/to/new-evidence
```

CI uses different fresh evidence directories for Java 21 and Java 25 and
runs each validator in its own step with `--expected-synthetic-java-major 21`
or `--expected-synthetic-java-major 25`, respectively. The requested major
comes from the invocation, not the archive. Every synthetic process_start
must report that actual JVM major; a skipped or ineffective JDK setup cannot
be counted as successful coverage of the requested Java version. The
workflow regression also rejects conditional or failure-tolerant JDK setup
steps. The option may be omitted when validating unchanged historical
evidence, and does not apply to real Minecraft captures. Neither synthetic
run is a Minecraft launch or an acceptance decision.

The validator checks each run's unique identity, process start/end association,
source commit, diagnostic JAR hash, loaded Netty module and handler code-source
hashes, exact official manifest/server-bundle LZ4-module SHA-1/size identity,
channel creation, pipeline activation, transformation and callback
execution, and connected socket coverage. A captured run must include a
one-to-one input-boundary assessment for every observed connected channel,
including input origin, protocol framing, authentication phase, and per-channel
and aggregate resource limits. Unknowns must be explicit. A negative LZ4
observation is only considered when those controls confirm the hooks ran and
the connected channels are accounted for.

The agent reports `java.class.path` as sanitized launcher metadata and also
enumerates code sources for classes already loaded across class loaders. This
is important for Fabric and other layered launchers. Netty module versions
come from loaded class package metadata and actual code-source JAR identities,
not from the manifest alone. The agent does not force-load `Lz4FrameDecoder`.

## Minecraft 1.19 reconciliation

[`minecraft-1.19-official-artifact-revalidation.json`](minecraft-1.19-official-artifact-revalidation.json)
records a targeted re-fetch of the official Mojang 1.19 manifest, its client
`netty-codec`, the official server bundle, and only the nested server
`netty-codec`. All four hashes match the retained source-bound metadata. The
client manifest selects 4.1.77.Final (`netty-codec` SHA-256
`84e4e01dd5b345311e971289b5bc08c0dfd6054a28d16853f0416943c9a3e458`); the
server bundle contains 4.1.76.Final (`netty-codec` SHA-256
`8b50a48b7860056d393aa335818c04c4b3784bd560e669c25a75feefe9e346dc`). This
confirms an official client/server artifact divergence and a server artifact
outside the exact historical 12-occurrence set. It does not identify which
JAR a running server class loader selects.

The dependency is bundled by the dedicated-server distribution. The official
client version manifest and server bundle are separate dependency models, so
the version difference is an expected official artifact divergence. The
historical audit scope omission is also confirmed: this separate server JAR
was never one of the 12 indexed client/source-audit occurrences and is not
silently added to that count. Whether `java -jar server.jar` extracts and
loads that exact JAR in the launched supported server remains open until a
server process is run with the agent.

## Reachability levels

The retained static evidence says the vulnerable class exists in several
Minecraft-bundled Netty JARs. This new evidence does not claim the class is
loaded or installed in a Minecraft pipeline until a corresponding captured
run proves those steps. No current game run shows whether it receives remote
bytes, what authentication state applies, or what game-level/aggregate
resource limits exist. No untrusted frame was sent, and no remote denial of
service test was run.

The historical 490-occurrence security inventory remains unchanged and
release-blocking. This directory does not clear any advisory, accept risk, or
change Minecraft-managed dependencies.

## Remediation and next target

The source-bound priority register contains **15 Netty advisory IDs with
upstream fixed-version boundaries**, of which **7 have focused investigation
evidence** and **8 remain unfocused**. These are separate classifications.
The independently recomputed highest fixed boundaries for both the indexed
set and the focused subset happen to be 4.1.137.Final and 4.2.17.Final.
The 4.1.137/4.2.17 candidates pass only isolated synthetic Netty controls;
no Minecraft/Fabric runtime compatibility is established.

Minecraft 26.2 selects 4.2.15.Final, which meets this LZ4 advisory's
4.2.13.Final boundary but not the indexed 4.2.17.Final maximum. Use the
source-bound corrected [`remediation-compatibility-v2.json`](remediation-compatibility-v2.json)
for current classification, versions and environment status. The original
[`remediation-compatibility.json`](remediation-compatibility.json) is retained
byte-for-byte as historical v1 evidence with incorrect "focused" terminology.
The v2 validator binds its claim to the exact archived v1 bytes and to all
source-verified Netty artifact versions in the environment matrix. Rebuilding
the v2 report does not rewrite v1 or change vulnerability dispositions.

The next focused investigation is GHSA-6jqx-86gh-f27w (CVE-2026-55831), four
unfocused High occurrences in `netty-codec-http`. The retained register puts
26.2 at 4.2.15.Final and the fix boundary at 4.2.16.Final. Its input path and
reachability deserve a source-bound review; the full security inventory stays
at 490 occurrences. See [`next-security-target.json`](next-security-target.json).

The independent historical `GH_TOKEN` question remains an owner-level
blocker. The account-history handoff is in
[`issue-45-gh-token-owner-handoff-2026-11-23.md`](../../worklogs/issue-45-gh-token-owner-handoff-2026-11-23.md).
