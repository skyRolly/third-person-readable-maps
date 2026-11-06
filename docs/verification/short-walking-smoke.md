# Short walking smoke: 1.21.4-1.21.8

These installed-client checks use the unchanged candidate JAR built from
`4b2e363c495640fa5ca305620c51c709a434ee2c`, with SHA-256 `26a28fb550132d07af415c41ccb82982937906ab991ad810406d2937b5e4e776`, Fabric Loader 0.20.1,
and Linux Xorg/Mesa software rendering. A copied local world was placed on
a cleared stone platform at `[5.5, 81, -62.5]`, then the player walked forward.
The ending position was read from saved player data after a clean exit. Screen
captures are local visual smoke evidence, not complete arm, lighting, multiplayer
or independent visual acceptance.

## 1.21.5

The Java 21 client moved horizontally 9.93 blocks, from `[5.5, 81, -62.5]` to
`[5.5, 81.0, -52.574238251923404]`. Map terrain is visible in both walking frames. See the [standing](short-walk/1.21.5-standing-day.png),
[walking frame 1](short-walk/1.21.5-walking-1.png), [walking frame 2](short-walk/1.21.5-walking-2.png),
and [after-walk](short-walk/1.21.5-after-walk.png) views; the [measurement](short-walk/1.21.5-movement.json),
[saved player data](short-walk/1.21.5-ending-player.dat), and [log excerpt](short-walk/1.21.5-excerpt.txt)
record the test.

A small dark foreground shape overlaps the map in the first walking view;
map terrain remains visible. Its cause was not established by this check.

## 1.21.4

The Java 21 client moved horizontally 10.14 blocks, from `[5.5, 81, -62.5]` to
`[5.5, 81.0, -52.35837918351525]`. Map terrain is visible in both walking frames. See the [standing](short-walk/1.21.4-standing-day.png),
[walking frame 1](short-walk/1.21.4-walking-1.png), [walking frame 2](short-walk/1.21.4-walking-2.png),
and [after-walk](short-walk/1.21.4-after-walk.png) views; the [measurement](short-walk/1.21.4-movement.json),
[saved player data](short-walk/1.21.4-ending-player.dat), and [log excerpt](short-walk/1.21.4-excerpt.txt)
record the test.

The first walking view contains large green foreground geometry above the
player; its cause was not established by this smoke check. The map itself is
visible in both views.
