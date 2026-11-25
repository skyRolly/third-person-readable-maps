# Issue 45 — synthetic SPDY pipeline identity

Separate from the integrated non-initializing class-only observation in #88.
Uses the same three representative retained manifests and pinned HTTP identities.
The JVM initializes a handler only in a disposable isolated loader and registers
it with an in-memory Netty EmbeddedChannel. It verifies the handler, channel,
pipeline and defining-loader/code-source identities, observes exact object
identity on insertion and removal, then closes/releases the channel and
requires no queued messages. The negative loader excludes the HTTP JAR.
No frame is constructed or sent; no socket, game launch or external network
traffic is requested by the Java control. Python acquisition downloads only
the pinned official library files. No product dependency is changed.

From the repository root (Python 3.10+, JDK 21+):

```sh
python -m unittest discover -s diagnostics/issue45-spdy-pipeline-probe -p test_pipeline_probe.py -v
python diagnostics/issue45-spdy-pipeline-probe/pipeline_probe.py --java "$JAVA_HOME/bin/java" --output /path/to/new-pipeline-report.json
```

The second command requires a clean committed checkout and official artifact
access. The new report schema is separate from the historic class-only schema;
source identities include the shared class probe and new pipeline sources.
Protocol tests use mocked process output; hosted official controls exercise
real JVM handler registration. The original class-only archive and its scope
flags are not modified.

This is **synthetic handler identity evidence only**, not a Minecraft
pipeline observation, a vulnerability exercise, proof of non-reachability
or a risk disposition. All four retained GHSA-6jqx-86gh-f27w occurrences
remain release-blocking. Actual game runtime captures remain separate.
