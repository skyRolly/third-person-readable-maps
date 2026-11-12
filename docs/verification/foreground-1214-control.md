# Foreground comparison on Minecraft 1.21.4

The original [1.21.4 walking view](short-walk/1.21.4-walking-1.png) contains
large green foreground geometry. To investigate it, two new offline local
single-player runs used independent copies of the same 1.21.3 world fixture,
Fabric Loader 0.20.1, Java 21, and Linux Xorg/Mesa software rendering. One run
installed the unchanged candidate JAR with SHA-256
`26a28fb550132d07af415c41ccb82982937906ab991ad810406d2937b5e4e776`; the
other used the same loader with no candidate JAR. Both clients saved and exited.

Each run first reproduced the original platform and air-clearance commands,
teleported the player to `[5.5, 81, -62.5]`, set daylight, and captured two
frames with walking input. Each then cleared the additional region from
`[-5, 86, -73]` to `[15, 95, -33]`, teleported back to the same starting
coordinates, and captured two more frames with walking input. The additional
fill reported 662 blocks changed in each run. The images are not frame-timed
or pixel-matched comparisons; the unmodified game renders the held map
differently, as expected. Small objects remain visible in the scene.

| Run | Original clearance | Additional clearance | Records |
|---|---|---|---|
| No candidate JAR | [standing](foreground-1214/no-mod-original-clearance-standing.png), [frame 1](foreground-1214/no-mod-original-clearance-walking-1.png), [frame 2](foreground-1214/no-mod-original-clearance-walking-2.png) | [standing](foreground-1214/no-mod-extra-clearance-standing.png), [frame 1](foreground-1214/no-mod-extra-clearance-walking-1.png), [frame 2](foreground-1214/no-mod-extra-clearance-walking-2.png) | [log excerpt](foreground-1214/no-mod-excerpt.txt), [result](foreground-1214/no-mod-result.json), [local harness](foreground-1214/no-mod-harness.py) |
| Candidate JAR | [standing](foreground-1214/candidate-original-clearance-standing.png), [frame 1](foreground-1214/candidate-original-clearance-walking-1.png), [frame 2](foreground-1214/candidate-original-clearance-walking-2.png) | [standing](foreground-1214/candidate-extra-clearance-standing.png), [frame 1](foreground-1214/candidate-extra-clearance-walking-1.png), [frame 2](foreground-1214/candidate-extra-clearance-walking-2.png) | [log excerpt](foreground-1214/candidate-excerpt.txt), [result](foreground-1214/candidate-result.json), [local harness](foreground-1214/candidate-harness.py) |

The large foreground shape was not reproduced in these captures under either
clearance condition. Since it appeared in a single original frame, capture
timing differed, and neither run reproduced it before the extra clearance,
this comparison does not establish its cause or rule out either the candidate
or the test environment. The observations on 1.20.6, 1.21.1, 1.21.5 and
1.21.10 were not separately reproduced by this experiment. Full visual
acceptance remains outstanding.
