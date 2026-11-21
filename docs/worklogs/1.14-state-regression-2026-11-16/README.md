# 1.14 rendering-state diagnostic

The two sample logs and `result.json` preserve an eight-draw comparison in a
1.14 local world with Fabric Loader 0.20.1, Java 8, an Xorg dummy display and
Mesa software OpenGL. The test-only `StateProbeMixin` seeds and reads state at
entry and return of `ReadableMapSurface.draw`; it is a separate Fabric Mod and
is not included in either product JAR. It restores the previously captured
state after each observation. The old candidate changed the seeded blend,
alpha-test, blend-factor and current-color state; the corrected preview
preserved them and the previously checked texture unit, binding and lighting.
The preview hash matches the separate clean build at the proposed source commit.

To reproduce, compile the probe with Java 8 bytecode against the 1.14.4 mapped
client, LWJGL 3.2.2 and Fabric's Sponge Mixin APIs, and package its class with
the two retained JSON files as `/dev/shm/tprm-state-probe.jar`. Prepare an
isolated launcher root at `/dev/shm/tprm-launcher-state` with the 1.14 client,
assets and libraries and a Fabric Loader 0.20.1 profile. The retained `run.py`
uses task-owned temporary worlds copied from the existing 1.14 test-world backup,
the listed old and preview artifacts, display `:115`, and the same user-input
harness described in `docs/verification/state-units-1.0.0/run.py` on the 1.14
proposal. These local paths and fixture assets are environment-specific; their
presence is not assumed in CI. No shared launcher assets need to be deleted or
modified.

This is an instrumented targeted state comparison, not unmodified-artifact
multiplayer, hardware-GPU, complete graphical, or independent acceptance.
