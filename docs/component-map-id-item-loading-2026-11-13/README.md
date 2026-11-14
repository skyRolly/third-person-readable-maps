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

A later [paired 1.21.4 test](1.21.4-2026-11-14/) exercised the current
proposal JAR and a no-Mod control in copies of the same world. Both preserved
explicit zero and seven, normalized the tested malformed numbers to zero, and
left the wrong-type and missing components absent. The selected fractional
case displayed seeded map-zero terrain. This remains one single-player path,
not coverage of all component-era item-loading or synchronization paths.

The [paired 26.3 test](26.3-world-upgrade-2026-11-14/) exercised an upgrade
from a 1.21.10-format copied world, with and without the current proposal JAR.
Both produced the same saved identity results and displayed map-zero terrain.
This does not establish the native 26.3 serialization or multiplayer paths.
