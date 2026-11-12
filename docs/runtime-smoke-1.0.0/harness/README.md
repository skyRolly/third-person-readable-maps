# Archived local walking harnesses

These are the diagnostic scripts used for the local 1.0.0 walking observations,
retained to make their input and capture procedure inspectable. They use the
original local absolute paths, Java toolchains, X11 displays, Minecraft Launcher
Lib, `nbtlib`, Xlib, Pillow and cached Mojang/Fabric downloads. The copied test
world fixtures and system configuration are not included here, so these files
alone do not reproduce the sessions. They are not CI or release checks.

The early and later scripts start the game in a copied world, set up a short
walking area, capture frames, and check saved player movement. The managed
scripts prune only re-downloadable asset-cache objects outside the active game
versions. The modern script was adjusted after an initial 26.1 attempt because
that game's successful time-setting command uses a different confirmation
message. The copied 1.21.10 world also required manual confirmation of the
26.1 world-upgrade dialogs. The first 26.1 attempt is not counted as a completed
walking observation. The second 26.1 attempt completed the game run, but the
runner looked for saved player data in the pre-26 path. The separate recovery
script checks the original log, frames, artifact and the new `players/data`
file before recording its observed movement; the runner was then updated to
use that path. The scripts use a dummy local identity and token; they do not
establish authenticated, multiplayer, hardware-GPU or human acceptance.
