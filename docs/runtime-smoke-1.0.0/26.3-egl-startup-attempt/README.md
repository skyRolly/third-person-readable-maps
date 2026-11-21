# Minecraft 26.3 EGL local-world startup — 2026-11-13 UTC

After the [earlier GLX/Vulkan failure](../26.3-backend-attempt/), the same
1.0.0 proposal JAR was launched with `SDL_VIDEO_FORCE_EGL=1`, a valid
`XDG_RUNTIME_DIR`, Fabric Loader 0.20.1 and Java 25 on Linux Xorg/Mesa software
rendering. The [client log](client.log) reports the OpenGL backend, Mixin
initialization and `MapSmokeTest joined the game`; the [index](index.json)
binds the retained logs to the proposed source commit and artifact hash.

This establishes one installed-client local-world startup only. The automation
then failed to identify the SDL game window when sending walking input, as the
[runner log](runner.log) records; its cleanup terminated the client. No walking
frames, clean shutdown, hardware-GPU, multiplayer or independent visual
acceptance are claimed for this attempt.
The [later walking observation](../26.3/) used the same JAR with the window
title handling corrected and records its separate save-log recovery.
