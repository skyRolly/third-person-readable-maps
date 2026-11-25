# Isolated SPDY class-definition observation — 2026-11-25

The original single-JSON Actions archive is retained byte-for-byte from the
successful PR #88 probe at the exact checkout recorded in
[provenance.json](provenance.json). The archive is a separate synthetic
observation, not a live Minecraft capture. The temporary Actions artifact
expires on December 2, 2026.

Independent verification checked the downloaded ZIP digest against the
GitHub API, CRC and sole JSON member digest against the actual CI log,
checkout and both source hashes against the locally tested source files,
and all three HTTP code-source and class-resource digests against the
prior static archive. All three positive and negative controls passed;
23 library digest records are present. Companion-library SHA-256 values
are observations, not previously pinned SHA-256 identities.

The archive intentionally predates the JVM failure-reporting changes in
`735aaf0` and `cd39e27`. Its checkout and source digests are historical
identities, not current-HEAD source digests. The later exact-head
[hosted run](https://github.com/skyRolly/third-person-readable-maps/actions/runs/45663992932)
at `cd39e279f3b66f2eefbead92e3fe3d8ce6660477` passed seven fixture tests
and all three official controls; its separately uploaded artifact is
[15046746903](https://github.com/skyRolly/third-person-readable-maps/actions/runs/45663992932/artifacts/15046746903).
That newer ZIP is not the historical retained archive and has not been
independently downloaded for this record.

From the repository root, verify the original archived bytes offline:

```sh
python diagnostics/issue45-spdy-class-probe/verify_archive.py
python -m unittest discover -s diagnostics/issue45-spdy-class-probe -p test_verify_archive.py -v
```

The verifier pins the reviewed original provenance Git blob and ZIP SHA-256,
checks size, Git blob, sole JSON member, CRC, JSON digest, historical checkout,
source digests recorded in the original provenance, controls and scope.
It does not re-hash the current probe as though it produced the old archive.
The pins are repository-reviewed evidence, not a signature or independent
trust root. CI runs this offline check before fresh observation, and changes
to the retained directory trigger the workflow on PRs and pushes to main.

No raw JARs, game sessions, class initialization, network frames or
pipeline observations were retained. All four advisory occurrences remain
blocking. This record does not change the historical runtime evidence
schema or authorize a risk disposition, product integration, or release.
