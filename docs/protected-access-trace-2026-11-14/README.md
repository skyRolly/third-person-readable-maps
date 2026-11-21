# Protected-access trace — 2026-11-14

The [runner](run.py) extracted each proposed product commit's `scripts/` tree
using `git archive` and ran the exact clean-build JAR against each advertised
game version. The [worker](worker.py) wrapped the existing JVM member
validator and recorded the access flags of every game or game-provided library
member it resolved. The [collector](collect.py) rechecked the archived script
hashes against the named Git commits, and the [index](index.json) binds each
trace and log to its source commit and artifact SHA-256.

All 48 version checks passed and the traced game/library member resolutions
included no protected members. This bounds the protected-receiver limitation
for these particular artifacts under the verifier's existing resolution model.
It is not an independent JVM verifier: Java platform APIs, Fabric/Mixin
internals, descriptor-only access, transformations and arbitrary dynamic
linkage are not covered by this trace. The general verifier still lacks full
protected receiver dataflow and must not be advertised as complete. Repeat the
trace and full checks if sources, mappings, libraries or JAR bytes change.
