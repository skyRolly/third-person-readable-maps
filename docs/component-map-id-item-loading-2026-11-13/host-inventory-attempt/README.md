# Corrected host-inventory probe — Minecraft 1.21.11

In a copied local single-player world, both the `level.dat` host inventory and
the player-data inventory were seeded with the same cases. Slot 1 held explicit
integer map ID 0; slot 2 held integer 7; selected slot 3 held `TAG_Double 0.5`;
slot 4 held `TAG_Long 4294967296`; slot 8 had no map-ID component. The copied
world's map-zero data contained 15,691 nonblank pixels copied from a terrain
map, so zero was distinguishable from a blank map. No production world or Mod
item stack was mutated to render the map.

With the exact proposed 1.0.0 JAR and Fabric Loader installed, the world joined
and was saved. The retained [input](input-level.dat) and
[saved player data](ending-player.dat), summarized and hashed in
[index.json](index.json), show that explicit integer 0 and 7 stayed 0 and 7,
the fractional and overflowing numeric values both became integer 0, and the
missing component stayed missing. The selected slot remained 3. The retained
[first-person frame](first-person.png) and [third-person frame](standing-day.png)
show terrain while the formerly fractional item is selected; the latter is a
partial diagnostic view, not full visual acceptance. The first-person image
was captured manually after world join; the automated harness captured the
third-person image and walking frames. Logs, launcher-library pins and the exact
harness are included.

This confirms an item-loading path to unintended map-zero fallback on 1.21.11,
in addition to the separate game-codec observations. This single-player probe
does not prove the item-loading behavior of every other version or a multiplayer
network path. A later [no-Mod control](../no-mod-control/) using the same input
fixture observed the same normalization. Once the
server or game's codec has converted a malformed serialized value to the same
typed integer zero used by a valid item, the client renderer cannot recover the
original value. A client-renderer-only rejection would also reject valid zero;
a safe fix needs an upstream or separately reviewed earlier-boundary design
that preserves valid zero, client/server behavior and first-person behavior.
