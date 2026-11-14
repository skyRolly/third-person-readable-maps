# Minecraft 1.20.6 foreground comparison — 2026-11-13 UTC

The final 1.0.0 [candidate walking evidence](../runtime-smoke-1.0.0/1.20.6/)
and this control used separate copies of the same local 1.20.6 fixture, Fabric
Loader 0.20.1, Java 21, Linux Xorg/Mesa software rendering, 1280×720 windows,
the same stone/air walking area, teleport position, day setting, third-person
perspective and programmed frame delays. The control's `mods` directory was
empty, and its [client log](client.log) does not load this mod. Its [runner](run.py)
prints the paired candidate hash for identification; it does not install that
JAR. The [index](index.json) binds the candidate source and JAR and hashes the
control files. The original fixture is not archived, so the recorded scripts
and source path alone cannot recreate the world.

Visual inspection of both pairs of walking frames found no large foreground
shape like the historical observation. A small green shape and shadow appear
to the left in both first frames. The runs were not frame-synchronized: their
saved horizontal distances were about 8.63 and 10.14 blocks, and player poses
differ. These four frames do not identify the cause of the historical 1.20.6
observation or prove that it cannot recur. Repeat the original viewpoint and
timing with matched candidate/no-mod captures and investigate any repeatable
difference. The earlier observations on other versions and full graphical,
hardware-GPU, multiplayer and independent acceptance remain open.
