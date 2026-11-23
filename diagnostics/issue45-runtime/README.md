# Issue 45 runtime pipeline diagnostic

This opt-in Java agent observes an already running Minecraft process. It does
not change packets, compression settings, authentication, TLS, or pipeline
handlers. It records Netty channel construction context, channel-active
pipeline snapshots, handler add/remove callbacks, loaded Netty classes and
code sources, Java/runtime metadata, the sanitized launch classpath, and
module JAR digests. It writes JSON Lines to a file configured by the
operator. Environment variables and application logs are not collected.

This artifact is diagnostic tooling. It is not part of the product mod and
must not be included in release candidates.

## Build

Requirements: Java 17 or later and Python 3.10 or later. The build obtains
pinned Byte Buddy and Eclipse Compiler for Java artifacts listed in
`dependencies.lock.json`, checks both SHA-256 values, compiles for Java 17,
and assembles a self-contained javaagent:

```sh
python3 diagnostics/issue45-runtime/build_agent.py --output build/issue45-runtime-agent.jar
sha256sum build/issue45-runtime-agent.jar
```

The build does not fetch Minecraft or change any Minecraft-managed libraries.

## Run with an official launcher

Create a private UTF-8 Java properties file outside the repository and set its
permissions so only the test operator can read it. Do not put credentials,
server addresses, or player data in it. Example:

```properties
output=./issue45-runtime-UNIQUE-RUN-ID.jsonl
minecraftVersion=1.19
distribution=client
launcher=official
sourceSha=8650a8a1195e04b865c8c977361ba99ae54b2dbc
productJar=/path/to/the/exact/product.jar
# Fabric only: also set fabricLoaderVersion and modsDirectory.
# fabricLoaderVersion=0.20.1
# modsDirectory=/path/to/the/exact/mods
```

Replace UNIQUE-RUN-ID with a freshly generated identifier for **every** launch.
The agent uses exclusive creation and refuses to overwrite an existing capture.
Use a private directory; never reuse a report filename. On Windows NTFS, inherited
read grants are explicitly removed before capture bytes are written; failure to
establish a private ACL aborts recording.

Add this JVM argument in the launcher's Java arguments, substituting absolute
paths:

```text
-javaagent:/absolute/path/issue45-runtime-agent.jar=/absolute/path/issue45-runtime.properties
```

Keep the launcher's effective classpath and all Minecraft-managed library
versions unchanged. Use a disposable game directory and a private test
account. For client pipeline coverage, connect only to an operator-controlled
local server; do not probe public servers. Shut the process down normally so
the final `process_end` record is flushed. Do not include the launcher's raw
logs or unredacted command line in evidence.

For a dedicated server, use the exact official server bundle and library
directory already selected by the test launcher. Follow Mojang's EULA using
the server owner's own account and decision. Start the diagnostic JVM with the
agent argument above, using `distribution=server`. The agent never writes
`eula.txt` or starts a server on the operator's behalf.

## Synthetic instrumentation controls

The control harness runs three local Netty `EmbeddedChannel` controls against
the exact Minecraft 1.19 Netty 4.1.77.Final and Minecraft 26.2 Netty
4.2.15.Final module sets, plus isolated upstream fixed candidates Netty
4.1.137.Final and 4.2.17.Final:
one with the affected `Lz4FrameDecoder`, one with Netty's JDK Zlib decoder,
and one without a compression decoder. No socket is opened and no frame bytes
are sent. The test supplies the separately pinned `lz4-java` helper needed to
instantiate Netty's optional LZ4 decoder; that helper is not added to or
claimed to be part of Minecraft's 1.19 runtime classpath. Run:

```sh
python3 diagnostics/issue45-runtime/run_controls.py --work-dir build/issue45-controls
```

The harness packages its compiled control classes into a dedicated hash-verified
JAR so that the initializer callbacks also have a verified code source.
Repeated runs may reuse the same `--work-dir`: every invocation compiles
into an isolated temporary class directory that is deleted after packaging,
so deleted or renamed classes cannot survive from prior builds. The control
JAR is regenerated atomically with canonical UTF-8 member-name ordering, fixed
ZIP timestamps, creator platform, storage method and permissions. Identical
class bytes therefore yield identical JAR hashes across hosts. Case-colliding
member names are rejected. Every diagnostic JSONL output path remains unique.
On Windows, the agent invokes only the absolute `SystemRoot\\System32\\icacls.exe`
path; it never searches the game directory or PATH for that executable, and
ACL-helper execution has a bounded timeout. After
each regeneration, validate the archive:

```sh
python3 diagnostics/issue45-runtime/validate_runtime_evidence.py \
  --evidence-dir docs/dependency-evidence/issue45-runtime-pipeline-2026-11-23
```

The command verifies pinned synthetic-test dependency hashes, verifies the
agent observed all three handler additions, checks that only the first
pipeline contains LZ4 and only the second contains Zlib, and requires a
zero-exit control JVM with its shutdown hook recorded. It writes the result
summary to `docs/dependency-evidence/issue45-runtime-pipeline-2026-11-23/synthetic-control-verification.json`.
This verifies instrumentation behavior only; it is not a Minecraft runtime
result.

## Record interpretation

Each run has a unique random run ID and starts with `process_start`. A
successful orderly execution ends with `process_end`, containing only classes
already loaded by the JVM at shutdown; the agent does not load LZ4 or any other
Netty class to test for its presence. `channel_created` records the channel
class, code source, privacy-preserving fingerprint, and constructor call-site
classes. `channel_active_pipeline_snapshot` records the handler inventory at
activation. `handler_added` and `handler_removed` record the handler class and
code source, pipeline installation call-site classes, address categories
(never addresses), and best-effort numeric limit fields. They distinguish
pipeline mutation from the channel constructor and activation events.

For a captured game run, add one `input_boundary_assessments` entry to its
matrix row for every fingerprint in `process_end.connected_socket_channel_fingerprints`.
The exact fields are `channel_fingerprint`, `channel_role`, `input_direction`
(`inbound`, `outbound`, `bidirectional`, or `unknown`), `input_origin`
(`remote_peer`, `local_process`, or `unknown`), `untrusted_remote_input`
(boolean), `protocol_framing`, `authentication_phase`
(`pre_authentication`, `authenticated`, `not_applicable`, or `unknown`),
`per_channel_resource_limits`, `aggregate_resource_limits`, and
`assessment_basis`. Use `unknown` where source review or runtime observation
cannot establish a value. Do not include server addresses, hostnames, account
identifiers, or player data. The validator requires every observed connected
channel to have a matching channel-active snapshot and assessment.

The classpath is recorded with home-directory components redacted. Netty JARs
on the launch classpath receive SHA-1/SHA-256 hashes; JARs that provide loaded
Netty classes and pipeline handlers are hashed from their actual code sources.
An interrupted attempt may be retained as `not_passed` with its original,
unaltered JSONL SHA-256. A malformed *unterminated final* fragment is excluded
from failed-run event validation and reported in `truncated_failed_capture_ids`.
A complete final JSON object without its terminal LF is retained and validated
as an event; it is reported separately in `missing_lf_failed_capture_ids`.
Malformed interior lines and all unterminated `captured` runs remain invalid. Legacy completed v1 captures without a loader
availability field require a separately verified classpath or loaded-code-source
JAR matching the pinned game dependency; this is not evidence of loader availability.

The evidence validator binds the LZ4 module to the exact official client
manifest or dedicated-server bundle pin. The JVM argument list is sanitized; access
tokens, account IDs, passwords, session values, cookies, authentication
headers, and server/host values are removed. Environment variables are not
read. Configure only paths writable by the test operator and protect the
output as private diagnostic data.

## Known coverage boundary

The agent targets the Netty 4.1/4.2 `AbstractChannel` constructors,
`DefaultChannelPipeline$HeadContext.channelActive`, and
`DefaultChannelPipeline.callHandlerAdded0`/`callHandlerRemoved0` methods. The
report includes transformation events, channel construction and activation
snapshots, and per-handler events. A run without all hooks and connected
socket coverage is incomplete and cannot support a negative reachability
conclusion. Validate each Netty family with the synthetic controls before
interpreting a game run. Custom transports that do not use these Netty channel
and pipeline classes are outside coverage and must be documented separately.
