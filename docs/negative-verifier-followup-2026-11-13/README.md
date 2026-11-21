# Adjacent-version negative controls — 2026-11-13 UTC

The [index](index.json) records nine intentionally unsupported adjacent-version
checks run with the advanced product source heads and their cleanly rebuilt
1.0.0 JARs. Every case returned a nonzero exit with a missing Mixin target,
class or member, rather than an infrastructure error. The individual logs and
[runner](run.py) are retained. These controls confirm rejection of the tested
boundaries; they do not imply a different artifact grouping or justify dropping
an advertised version.
