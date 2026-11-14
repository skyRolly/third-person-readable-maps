# No-Mod item-loading control — Minecraft 1.21.11

This separate local-world run used an empty `mods` directory with Fabric Loader
and the same exact host, player and map-zero fixture inputs as the
[candidate probe](../host-inventory-attempt/). The [client log](client.log)
shows four loaded components and no `thirdpersonreadablemaps` entry. The
[saved player data](ending-player.dat) contains the same normalized IDs as the
candidate run: malformed double 0.5 and overflowing long became integer zero,
valid zero and seven remained intact, and the missing component stayed missing.

The [first-person frame](first-person.png) shows the seeded map-zero terrain
while the formerly fractional item is selected. The candidate and control
first-person captures were taken at different locations and times, so this is
not a pixel-matched first-person regression test. It supports the conclusion
that this 1.21.11 single-player item-loading coercion occurs without the Mod.
The [index](index.json) binds the output and test harness to the input fixture
and paired candidate identity; other game versions and multiplayer paths remain
unverified by this control.
