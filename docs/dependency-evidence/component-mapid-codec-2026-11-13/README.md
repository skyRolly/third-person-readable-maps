# Component map-ID codec sweep — 2026-11-13 UTC

This controlled, no-mod diagnostic executes each game's own `MapId.CODEC`
with that game's `NbtOps` for every component-era version in the proposed
compatibility matrix: 1.20.5 through 1.21.11 and 26.1 through 26.3, 19
explicit versions in total. The [results](results.json) identify each source
client JAR, official mappings where present, metadata-selected DataFixerUpper
and cached libraries. Mojang's [version manifest](version_manifest_v2.json)
and each exact per-version metadata response are retained; the runner checks
client, mapping, metadata and available library sizes and SHA-1s before use.
Missing cached library artifacts are listed, and the probe succeeded without
those files. The runner used OpenJDK 25.0.5; it is not a full client launch.

For every tested version an explicit integer zero decoded to zero and seven
decoded to seven. The three other numeric inputs tested—double `0.5`, long
`4294967296`, and double `NaN`—each decoded to zero. The string input was
rejected. The [probe source](MapCodecProbe.java) checks the two valid cases and
prints all results without assuming how malformed values should behave; the
[runner](run.py) records the output, source hashes and exact artifact identities.
The previous [two-version probe](../component-mapid-codec-2026-11-12/) and its
original results remain historical evidence.

This establishes the behavior of the named codec in isolation. It does not
prove that every item-loading path accepts malformed serialized components,
that a world contains available map-zero data, or what a player would see.
A missing component and a legitimate explicit zero remain distinct to the
renderer; once the game's codec has converted a malformed number to zero, the
renderer cannot recover the original input. A bounded remedy must be designed
and independently reviewed with explicit-zero, first-person and item-loading
regressions before the issue can be closed. No product code was changed or
security risk accepted by this diagnostic.
