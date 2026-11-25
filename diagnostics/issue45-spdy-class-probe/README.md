# Issue 45 — isolated SPDY class-definition controls

This is a **separate synthetic diagnostic**, not a change to the historical
compression agent, control profiles, runtime capture schema, or product code.
It is the next limited step after the verified official HTTP artifact archive
in `docs/dependency-evidence/issue45-official-http-observation-2026-11-25`.

The probe uses three representative retained Minecraft manifests (1.21.9,
1.21.11, 26.2) for HTTP artifact families 4.1.118.Final, 4.2.7.Final and
4.2.15.Final. It does not recreate all seven game environments or reconcile
all four advisory occurrences independently. Exact retained manifest SHA-256,
official URL/path and size/SHA-1 pin a minimal non-native Netty classpath.
The HTTP JAR and target class resource SHA-256 additionally match the
archived static observation. Companion JAR SHA-256 values are observed,
not previously pinned SHA-256 values. No product dependency is overridden.

For each profile a standalone Java source-file launch creates two isolated
URLClassLoaders with the platform parent. The negative loader omits the HTTP
JAR and must raise ClassNotFoundException for SpdyFrameCodec. The positive
loader includes it and uses Class.forName(name, false, loader), checks the
defining loader, code-source location and JAR digest, and checks the class
resource digest. This measures class definition and the resource bytes,
not JVM-transformed bytecode. No class initialization, handler construction,
pipeline insertion, network frames, packet contents, or game launch is
requested. Manifest Class-Path expansion is rejected. This is not an
attempt to exercise the vulnerability.

The hosted workflow runs the fixture controls, then acquires the actual
official files into disposable directories and retains only a JSON report.
Source blobs must match HEAD at the beginning and at observation checkpoints;
the report records checkout, script digests and actual Java version. Use a
stable, trusted checkout and interpreter; these checks are not attestation
against adversarial concurrent changes or an altered JVM.

Local offline fixture controls (JDK 21+ and Python 3.10+):

```sh
python -m unittest discover -s diagnostics/issue45-spdy-class-probe -p test_probe.py -v
```

Actual official probe in a network-enabled clean checkout:

```sh
python diagnostics/issue45-spdy-class-probe/probe.py --java "$JAVA_HOME/bin/java" --output /path/to/new-report.json
```

**Limitations:** the actual game class loader and pipeline are not observed;
`pipeline_observed: false`, `runtime_reachability: not_established`,
`risk_accepted: false`, `release_blocking: true`. All four retained
GHSA-6jqx-86gh-f27w occurrences remain blocking. A missing class in the
deliberately restricted negative control is not proof of non-reachability in
Minecraft. Dedicated benign pipeline observation and all live capture
environments remain separate work.
