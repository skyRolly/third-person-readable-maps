# Tracked repository files — 2026-11-13

The [index](index.json) inventories every tracked path and Git object from all
13 advanced product PR heads, integrated `main`, and coordination PR commit
`28a707a1adab682cfd3984ca7b69ca80f6c00552`. The latter is an explicit
snapshot: this generated inventory and subsequent evidence commits do not
exist in that commit. The [collector](collect.py) records source commits,
classifies paths, checks all 13 proposed `mod_version` values and verifies the
required README title, shared introduction and branch-specific badge. The
`main` and coordination README title and introduction were also checked.

There are 1,954 distinct relative paths across these trees. Twenty-four paths
appear in all 13 product trees; 13 have identical Git objects in every product.
The identical files include `.gitattributes`, `.gitignore`, `LICENSE`,
`Build-Windows.bat`, `settings.gradle`, the Gradle wrapper and daemon criteria,
the shared JVM and library linkage components, and the common linkage fixtures.
The product-specific properties, metadata, workflows, READMEs, namespace
adapters and verification rules differ with their group. Different object IDs
alone do not establish a defect.

The game-specific rendering code, Fabric metadata and Mixin configurations
retain necessary API and mapping differences. Java 16-compatible output for
the 1.17–1.19.2 group remains distinct from the Java 17 runtime required by
its Minecraft 1.18 and later members. Branch CI badges identify their actual
targets; candidate README text warns that legacy target badges currently show
placeholder builds. The [dependency-update review](../dependency-update-prs-2026-11-12.md)
keeps bot upgrades separate rather than forcing the same toolchain change
through every branch.

The many `docs/verification/` paths include retained screenshots, logs and
probes needed to understand source-bound historical results and rendering
regressions. Their presence or duplication alone is not evidence that they are
safe to delete. Historical 0.0.2 artifacts, hashes and snapshots remain dated;
current candidate evidence is linked separately from the
[review handoff](../legacy-review-handoff.md). Active documentation now
distinguishes placeholder ports, proposed 1.0.0 heads and unreleased status.
No tracked diagnostic or historical artifact was removed merely to reduce
file count. This inventory does not claim that every documentation statement
or dependency has been independently reviewed for obsolescence.
