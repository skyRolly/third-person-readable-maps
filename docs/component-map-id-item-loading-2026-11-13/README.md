# Component map-ID item-loading investigation — 2026-11-13

The [first local-world attempt](playerdata-only-attempt/) was inconclusive:
the edited player-data file was not the host inventory loaded by the integrated
server. The saved inventory matched the unmodified host inventory in `level.dat`.
The files, screenshot and diagnostic are retained so this result is not mistaken
for evidence about malformed IDs. A [corrected host-inventory probe](host-inventory-attempt/)
sets both inventory copies and retains a distinct map-zero data record. It
observed numeric coercion and map-zero rendering in 1.21.11; its source,
artifact, inputs, output and limits are recorded separately. A subsequent
[no-Mod control](no-mod-control/) observed the same item-loading result.

A later [paired 1.21.4 test](1.21.4-2026-11-14/) exercised the then-proposed
JAR and a no-Mod control in copies of the same world. The current clean JAR has
the same hash. Both preserved
explicit zero and seven, normalized the tested malformed numbers to zero, and
left the wrong-type and missing components absent. The selected fractional
case displayed seeded map-zero terrain. This remains one single-player path,
not coverage of all component-era item-loading or synchronization paths.

The [paired 1.20.5 test](1.20.5-2026-11-15/) also exercised actual item
loading in copied local worlds with the current proposed artifact and without
the Mod. Both runs produced the same saved identity results and displayed the
seeded map-zero terrain for the selected fractional case. This adds an early
component-era loading path, not native 26.3 or multiplayer coverage. Preserve
the game-provided typed component as the provisional client-rendering contract:
after Minecraft normalizes malformed data the original serialized identity is
not available to this renderer. Explicit zero remains valid. An owner must
independently accept that contract; a game-wide codec intervention would need a
separate design and review.

The [paired 26.3 test](26.3-world-upgrade-2026-11-14/) exercised an upgrade
from a 1.21.10-format copied world, with and without the then-proposed JAR;
the current clean JAR has the same hash.
Both produced the same saved identity results and displayed map-zero terrain.
The later [paired 26.3 native-format test](26.3-native-format-2026-11-15/)
seeded newly malformed IDs into 26.3-format player data and loaded it with and
without the current proposal, without an upgrade during either run. It found
the same saved results and map-zero rendering. The source world had been
upgraded and saved by 26.3 previously; the test does not establish every native
world-generation path or multiplayer synchronization behavior.
