# Minecraft 26.3 software-renderer startup attempt — 2026-11-12 UTC

The final 1.0.0 [maintenance proposal](https://github.com/skyRolly/third-person-readable-maps/pull/33)
was launched with Fabric Loader 0.20.1 and Java 25 on a Linux Xorg dummy display
with Mesa software rendering. The [index](index.json) records the exact proposal
commit, artifact SHA-256 and retained file hashes. Fabric and Mixin initialized,
but the client could not create a graphics backend: OpenGL reported no matching
GLX visual and Vulkan reported no `VK_KHR_surface` extension. The actual
[dialog](backend-error.png), [client log](client.log) and [runner log](runner.log)
are retained. No local world was joined, so this is a **blocked startup
attempt**, not a passing startup, graphical acceptance or proof of a mod defect.
The [subsequent EGL attempt](../26.3-egl-startup-attempt/) reached a local
world on the same artifact; its walking harness failed and broader acceptance
remains open.
