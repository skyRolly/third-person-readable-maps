# Short walking smoke: 1.21-1.21.1

These installed-client checks use the unchanged candidate JAR built from
`5f5fdad012ab499b2f31e0f878d507c4d774d4b4`, with SHA-256 `d4054952d77a3b4dc79d7681779126cf38bd0fb34c1f9afd3346ceb9f4ca4745`, Fabric Loader 0.20.1,
and Linux Xorg/Mesa software rendering. A copied local world was placed on
a cleared stone platform at `[5.5, 81, -62.5]`, then the player walked forward.
The ending position was read from saved player data after a clean exit. Screen
captures are local visual smoke evidence, not complete arm, lighting, multiplayer
or independent visual acceptance.

## 1.21.1

The Java 21 client moved horizontally 12.08 blocks, from `[5.5, 81, -62.5]` to
`[5.5, 81.0, -50.41564756784185]`. Map terrain is visible in both walking frames. See the [standing](short-walk/1.21.1-standing-day.png),
[walking frame 1](short-walk/1.21.1-walking-1.png), [walking frame 2](short-walk/1.21.1-walking-2.png),
and [after-walk](short-walk/1.21.1-after-walk.png) views; the [measurement](short-walk/1.21.1-movement.json),
[saved player data](short-walk/1.21.1-ending-player.dat), and [log excerpt](short-walk/1.21.1-excerpt.txt)
record the test.

The first walking view contains large green foreground geometry above the
player; its cause was not established by this smoke check. The map itself is
visible in both views.

The first attempt stopped before a completed walking result because the
test environment ran out of disk space; the [error excerpt](short-walk/1.21.1-diskfull-excerpt.txt)
is retained. Only the completed retry above is counted.

## 1.21

The Java 21 client moved horizontally 10.79 blocks, from `[5.5, 81, -62.5]` to
`[5.5, 81.0, -51.71080197829078]`. Map terrain is visible in both walking frames. See the [standing](short-walk/1.21-standing-day.png),
[walking frame 1](short-walk/1.21-walking-1.png), [walking frame 2](short-walk/1.21-walking-2.png),
and [after-walk](short-walk/1.21-after-walk.png) views; the [measurement](short-walk/1.21-movement.json),
[saved player data](short-walk/1.21-ending-player.dat), and [log excerpt](short-walk/1.21-excerpt.txt)
record the test.
