# Component map-ID item-loading investigation — 2026-11-13

The [first local-world attempt](playerdata-only-attempt/) was inconclusive:
the edited player-data file was not the host inventory loaded by the integrated
server. The saved inventory matched the unmodified host inventory in `level.dat`.
The files, screenshot and diagnostic are retained so this result is not mistaken
for evidence about malformed IDs. A [corrected host-inventory probe](host-inventory-attempt/)
sets both inventory copies and retains a distinct map-zero data record. It
observed numeric coercion and map-zero rendering in 1.21.11; its source,
artifact, inputs, output and limits are recorded separately.
