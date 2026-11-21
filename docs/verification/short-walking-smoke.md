# Short walking smoke: 1.19.3

These installed-client checks use the unchanged candidate JAR built from
`c9ca3b5f05768017a197116919f22e2a967a8d01`, with SHA-256 `f7288ad9a7f73f718176db15f185bab10d8a02548b02e2f4a943aac06f0db16b`, Fabric Loader 0.20.1,
and Linux Xorg/Mesa software rendering. A copied local world was placed on
a cleared stone platform at `[5.5, 81, -62.5]`, then the player walked forward.
The ending position was read from saved player data after a clean exit. Screen
captures are local visual smoke evidence, not complete arm, lighting, multiplayer
or independent visual acceptance.

## 1.19.3

The Java 17 client moved horizontally 6.47 blocks, from `[5.5, 81, -62.5]` to
`[5.5, 81.0, -56.02798334640486]`. Map terrain is visible in both walking frames. See the [standing](short-walk/1.19.3-standing-day.png),
[walking frame 1](short-walk/1.19.3-walking-1.png), [walking frame 2](short-walk/1.19.3-walking-2.png),
and [after-walk](short-walk/1.19.3-after-walk.png) views; the [measurement](short-walk/1.19.3-movement.json),
[saved player data](short-walk/1.19.3-ending-player.dat), and [log excerpt](short-walk/1.19.3-excerpt.txt)
record the test.
