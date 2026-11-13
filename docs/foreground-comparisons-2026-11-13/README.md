# Foreground comparisons — 2026-11-13 UTC

These controls accompany the [1.20.6 comparison](../foreground-comparison-1.20.6-2026-11-13/)
for versions separately mentioned in the historical foreground-shape report.
The [index](index.json) identifies each completed control, its paired
candidate source and JAR, the copied local fixture and retained-file hashes.
Each control used Fabric Loader 0.20.1 with an empty mods directory; its client
log confirms that this mod was not loaded. The [runner](run.py) prints the
paired candidate hash for identification but does not install that JAR.

For each pair, the candidate and control used separate copies of the same
fixture, the required Java runtime, Linux Xorg/Mesa software rendering,
1280×720 windows, the same stone/air walking area, teleport position, day
setting, third-person perspective and programmed capture delays. The copied
fixtures are not archived. The runs are not frame-synchronized and their
saved movement distances and player poses can differ.

The two candidate frames and two no-mod frames for each of 1.21.1, 1.21.5
and 1.21.10 were visually inspected. The large historical foreground shape
was not seen in these twelve frames. Small green objects and their shadows
appear in candidate and no-mod frames; small dark-green shapes also appear in
both 1.21.10 runs. The captures differ in pose and position, so these
observations do not identify the objects or establish the cause of the
historical shape. The original viewpoint was not reproduced. Further
comparisons should match the original conditions and examine any repeatable
candidate/no-mod difference. These frames do not establish full graphical,
hardware-GPU, multiplayer or independent acceptance.
