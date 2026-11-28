# Short walking smoke: 1.20.5-1.20.6

These installed-client checks use the unchanged candidate JAR built from
`32164d846089ce67d5c0a10ba351796207312b02`, with SHA-256 `8c02fa2fc1b565e8154926642ac4fa260b28f59aeca8a49f9958a8d39050cdfd`, Fabric Loader 0.20.1,
and Linux Xorg/Mesa software rendering. A copied local world was placed on
a cleared stone platform at `[5.5, 81, -62.5]`, then the player walked forward.
The ending position was read from saved player data after a clean exit. Screen
captures are local visual smoke evidence, not complete arm, lighting, multiplayer
or independent visual acceptance.

## 1.20.6

The Java 21 client moved horizontally 10.57 blocks, from `[5.5, 81, -62.5]` to
`[5.5, 81.0, -51.92666104669894]`. Map terrain is visible in both walking frames. See the [standing](short-walk/1.20.6-standing-day.png),
[walking frame 1](short-walk/1.20.6-walking-1.png), [walking frame 2](short-walk/1.20.6-walking-2.png),
and [after-walk](short-walk/1.20.6-after-walk.png) views; the [measurement](short-walk/1.20.6-movement.json),
[saved player data](short-walk/1.20.6-ending-player.dat), and [log excerpt](short-walk/1.20.6-excerpt.txt)
record the test.

The prior attempt did not finish loading its local world. The environment stopped during that attempt; the [log excerpt](short-walk/1.20.6-interrupted-excerpt.txt)
is retained. Only the completed retry above is counted.

The first walking view contains large green foreground geometry above the
player; its cause was not established by this smoke check. The map itself is
visible in both views.

## 1.20.5

The Java 21 client moved horizontally 9.71 blocks, from `[5.5, 81, -62.5]` to
`[5.5, 81.0, -52.790097320331554]`. Map terrain is visible in both walking frames. See the [standing](short-walk/1.20.5-standing-day.png),
[walking frame 1](short-walk/1.20.5-walking-1.png), [walking frame 2](short-walk/1.20.5-walking-2.png),
and [after-walk](short-walk/1.20.5-after-walk.png) views; the [measurement](short-walk/1.20.5-movement.json),
[saved player data](short-walk/1.20.5-ending-player.dat), and [log excerpt](short-walk/1.20.5-excerpt.txt)
record the test.

The first attempt stopped before a completed walking result because the
test environment ran out of disk space; the [error excerpt](short-walk/1.20.5-diskfull-excerpt.txt)
is retained. Only the completed retry above is counted.
