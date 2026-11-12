# Component map-ID codec probe — 2026-11-12

This controlled diagnostic runs the actual Minecraft `MapId` codec with the
game's NBT operations, without a mod or running world. The [results](results.json)
record exact SHA-1 identities for the original Mojang metadata, client JARs,
DataFixerUpper 9.0.19 and every available metadata-selected library artifact;
the original metadata files are retained byte-for-byte. Missing library files
are listed and were not needed by this probe. The official 1.21.11 client
mappings were also checked before using that obfuscated client's class names.

Both 1.21.11 and 26.1.2 decoded an explicit integer zero and seven correctly.
They decoded double 0.5, long 4294967296 and double NaN as zero; a string was
rejected. The [probe](MapCodecProbe.java) asserts each result, and the [runner](run.py)
asserts the metadata, game, mapping and available library hashes before use.
It used Java 25 and the Linux library cache. Its hard-coded local client and
toolchain paths must be adapted to rerun elsewhere; the relevant downloads and
hashes are in the retained metadata.

This establishes codec behavior for two game versions. It does not prove how a
malformed value entered an item stack, whether client map-zero data exists,
what a player sees, or whether every other component-era game behaves the same
way. A missing component and a legitimate explicit zero remain distinct at the
renderer, but after this upstream numeric conversion the original malformed
value cannot be distinguished from an explicit zero by the renderer alone. No
fix or security-risk acceptance is implied.
