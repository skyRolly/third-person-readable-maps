# Issue 45: cross-source and retained-evidence validation

The merged PR #58 exporter selected Critical and High rows before comparing
source observations. A different source reporting the same advisory as
Moderate could therefore disappear from the register. The exporter now selects
advisory IDs first and checks every verified occurrence of those IDs, including
lower-severity observations, for consistent effective severity and advisory
content. A timestamp-only difference is recorded by source; a substantive
conflict stops export. Moderate-only advisories remain outside the priority
register. The retained 37-advisory, 199-occurrence register is unchanged.

Regression fixtures repack source reports and update archive hashes. The
per-report verifier accepts them; the actual merged PR #58 exporter omits the
synthetic Moderate observations, and the corrected exporter rejects the
conflict. The CLI also refuses to write a register for that case. A separate
temporary historical fixture updates the compressed and uncompressed archive
hashes, finding index, focused-evidence references and ledger pin. With its
live manifest and reviewed manifest unchanged, a changed or missing historical
manifest is rejected. Removing only the historical half of the check causes the
same fixture to be accepted.

The [supplemental class inventory](../dependency-evidence/issue45-netty-sni-high-2026-11-22/known-clienthello-class-hits-2026-11-22.json)
records an independent local rehash of the six previously catalogued Netty
JARs and 18 known ClientHello literal-bearing class entries. Two class paths
per JAR also match the prior hash-bound class catalog; the third is a previously
uncatalogued inner class. `python3 scripts/inspect_issue45_sni_high.py
--verify-known-hits-cache <sha1-keyed-cache>` rechecks the JARs and class bytes.
The scan validator now requires the exact known paths and hashes, rejects
duplicates, and binds each hit to the correct JAR and coordinate. These are
class-file observations, not evidence that a class runs or that an input path
is reachable. The existing 471-JAR scan and all dispositions are unchanged.

The evidence writer's exclusive-open property has a deterministic interleaving
test: another writer creates the target after the existence check. The real
`xb` open preserves those bytes; a `wb` mutant overwrites them. The register
timestamp schemas and the retained SNI consumer's schema restriction are
documented in the dependency-monitoring guide. All outstanding advisories remain
blocking; this work grants no security clearance or risk acceptance.
