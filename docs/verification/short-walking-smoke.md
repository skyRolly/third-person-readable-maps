# Short walking smoke: 1.21.2-1.21.3

These installed-client checks use the unchanged candidate JAR built from
`84d8291e16fc14ffa3b0956404b64c9538251693`, with SHA-256 `28a15aacf531dfdb3dd51ba63b7e9cf42000e0b981d863cdc0c27bebc89523e4`, Fabric Loader 0.20.1,
and Linux Xorg/Mesa software rendering. A copied local world was placed on
a cleared stone platform at `[5.5, 81, -62.5]`, then the player walked forward.
The ending position was read from saved player data after a clean exit. Screen
captures are local visual smoke evidence, not complete arm, lighting, multiplayer
or independent visual acceptance.

## 1.21.3

The Java 21 client moved horizontally 10.36 blocks, from `[5.5, 81, -62.5]` to
`[5.5, 81.0, -52.142520115107104]`. Map terrain is visible in both walking frames. See the [standing](short-walk/1.21.3-standing-day.png),
[walking frame 1](short-walk/1.21.3-walking-1.png), [walking frame 2](short-walk/1.21.3-walking-2.png),
and [after-walk](short-walk/1.21.3-after-walk.png) views; the [measurement](short-walk/1.21.3-movement.json),
[saved player data](short-walk/1.21.3-ending-player.dat), and [log excerpt](short-walk/1.21.3-excerpt.txt)
record the test.
