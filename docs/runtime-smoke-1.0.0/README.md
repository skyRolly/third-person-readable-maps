# 1.0.0 local walking smoke evidence

These are source- and artifact-identified installed-client observations in copied local worlds on Linux Xorg/Mesa software rendering. Each row retains the movement measurement, saved ending player data, two actual walking frames and the full client log. The [index](index.json) identifies each candidate source, artifact and file SHA-256. The frames and a positive local movement distance are partial diagnostics; they are not full graphical, hardware-GPU, multiplayer or independent human acceptance. The user-facing map may be partly occluded in a frame. The existing branch-specific probes cover different state and map-ID cases.

The diagnostic harnesses `v100-walking-final-early-90.py` and `v100-walking-later-89.py` in the original local test workspace use Minecraft Launcher Lib, cached Mojang/Fabric artifacts, an X11 display and copied test-world fixtures; the original historical 0.0.2 reports retain their own earlier source and artifacts.
