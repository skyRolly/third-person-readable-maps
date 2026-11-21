# Verifier-follow-up clean builds — 2026-11-13 UTC

The [index](index.json) identifies completed clean Linux builds from archived
exact product commits. Each retained log is hashed; the [resumed build runner](run.py)
uses the local JDK, Gradle caches and a clean `git archive` extraction. The
first six builds used the same core command before the runner gained a resume
guard; that earlier runner's exact bytes were not retained. The
[collector](collect.py) checks source identity and artifact SHA-256 before
recording it. The JARs remain local build outputs rather than committed files.
A matching previous digest identifies identical bytes; it does not relabel an
old source-bound runtime observation as a test of the new source commit. The
[hosted CI index](../hosted-builds-verifier-followup-2026-11-13.json) records
separate Linux and Windows jobs.
