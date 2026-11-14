# Foreground item-entity control — 2026-11-13

Two controlled Minecraft 1.21.11 local-world runs used the same copied fixture,
camera setup, teleport location, stone-and-air area and Linux Xorg/Mesa software
renderer. The [candidate](candidate/) used the exact proposed 1.0.0 JAR; the
[control](control/) used Fabric Loader with an empty `mods` directory. The
[collector](collect.py), [source and file hashes](index.json), logs and frames
are retained. Fixture file hashes were recorded after the runs; the original
fixture itself was copied, not modified.

In both runs, an in-game data query identified the nearest dropped item as
`minecraft:wheat_seeds`. Clearing only `minecraft:item` entities reported
eight entities removed in each run. The small green object visible before the
clear disappeared afterward in both scenes; several small dark shapes in the
candidate scene also disappeared after the clear. The paired captures and logs
support dropped-item entities as an explanation for these particular small
shapes. The query identified the nearest item, not the identity of every shape.

The original large historical foreground shape was not reproduced under its
original conditions, so its cause remains inconclusive. Reproduce it with the
same world, camera, pose, motion, renderer and frame timing, then compare a
matched candidate and no-Mod run before resolving that observation. These
frames are diagnostics, not full graphical or independent acceptance. A prior
[invalid-selector attempt](invalid-selector-attempt/) is retained separately
and is not part of the successful comparison.
