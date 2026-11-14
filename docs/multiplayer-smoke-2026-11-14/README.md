# 1.21.11 local multiplayer observation — 2026-11-14

This is a partial, software-rendered diagnostic, not multiplayer acceptance.
Two Fabric 0.20.1 clients ran on Java 21 and Linux Xorg/Mesa. Both loaded the
proposed `third-person-readable-maps-1.0.0-mc1.21.11.jar`, built from
`b79f5061bae6caacb8c083f5fb90a1754ea32b9e` with SHA-256
`c60f65c24a44fec6cf0c1fc0c67bb52a06e045ab32e2a9f7dbeab2c619f45b73`.
The runner checked the JAR hash before copying it to both client directories.
The build record is [here](../builds-verifier-followup-2026-11-13/).

The host loaded a copied local world and published its integrated server on a
LAN. Its selected hotbar slot contained a filled map with ID 2. The observer
joined and was positioned above the host with a fixed view of that held map.
The [first observer image](view-retry/observer-before-map.png) shows a blank
map surface. The host then gave the observer a filled map with ID 2; the
observer selected that map and, after a wait, its [first-person image](view-retry/observer-held-map.png)
shows terrain. After selecting an empty slot, the [second observer image](view-retry/observer-after-map.png)
shows terrain on the remote player's map. The [host image](view-retry/host-held-map.png)
also shows terrain on the host's selected map. The [runner](view-retry/runner.py),
[runner output](view-retry/runner.log), [host log](view-retry/host.log),
[observer log](view-retry/observer.log), and [result](view-retry/result.json)
record the setup and actions. The screenshots were inspected visually; the
automated evidence test verifies their bytes and provenance, not their content.

The observer's map-data cache and network packets were **not instrumented**.
These images do not prove why the first surface was blank, establish every
naturally unavailable-data path, or cover the other 47 versions. The exercise
does not cover all hands, poses, first-person regressions, multiplayer topologies,
hardware GPUs, or independent human acceptance. Realms/authentication service
requests were refused and the X11 cursor-shape warning appears in the logs. The
LAN server allowed the local observer despite unavailable authentication. Both
clients were terminated after capture; no clean shutdown is asserted.

The runner's automatic loopback quick-connect initially failed because the
authentication servers were unreachable; the [failure screen](view-retry/loopback-auth-failure.png)
and both connection attempts are retained. The operator returned to the server
list and selected the discovered LAN world manually; that UI intervention is
not encoded in the runner. The retained helper scripts supplied the subsequent
input. The copied world's `level.dat`, `map_2.dat` and options are retained as
a [fixture sample](fixture-sample/), taken and hashed from the unchanged source
fixture **after** the run. They are not the full world and were not hashed
before launch, so they do not by themselves prove the complete initial world
state.

Two earlier attempts remain separate. In [port-parser-attempt](port-parser-attempt/),
the host published the LAN, but the parser did not accept the bracketed port;
the operator interrupted the runner. In [edge-on-attempt](edge-on-attempt/),
the operator manually selected the LAN world after the client remained at the
main menu. Both clients joined and screenshots were captured, but the observer
viewed the remote map almost edge-on and selected an empty slot after receiving
its map. Those images do not demonstrate the desired data transition. The
successful retry changed the viewpoint and selected the filled map before the
second capture; it retained both attempts instead of replacing them.

[index.json](index.json) binds the retained files to their SHA-256 digests.
