# Advisory ownership and scope — 2026-11-14

The [index](index.json) gives each of the 490 current-source failing
group/package/version/advisory occurrences its exact source SHA, OSV report,
fingerprint, severity, Gradle scope and Minecraft versions whose hash-identified
runtime metadata lists that coordinate. The [collector](collect.py) verifies
each coordinate against the retained November 14 report inventories and links
the separately inspected proposed JAR's source and digest. It does not relabel
that proposed JAR as an artifact of an integrated maintenance branch.

All 490 occurrences appear in at least one Minecraft runtime metadata inventory;
424 also appear in Gradle inventories and 66 appear only in runtime inventories.
These runtime lists include all declared platform variants, so a listing alone
does not prove loading or exploitability on a particular installation. The
proposed Mod JARs contain no third-party class files or nested JARs, but an
unbundled game-provided dependency can still be relevant.

Minecraft manages the listed runtime library coordinates. An applicable runtime
remediation may therefore depend on upstream; any separate Gradle exposure and
actual execution path still need individual assessment. No occurrence is marked
safe, resolved, non-applicable or accepted by this cross-reference, and all
remain failing. The existing individual advisory investigations and dated OSV
reports retain their original provenance. Do not force an unverified Minecraft
library override to make the audit green.
