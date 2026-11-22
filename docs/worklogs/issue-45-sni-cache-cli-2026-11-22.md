# Issue 45: offline SNI cache CLI verification

The known-hits cache command now checks each file's source-bound size and cache
path before the existing JAR and class-hash checks. Its regression fixture runs
the real CLI with six temporary synthetic JARs, without network access. It
checks all six reads and rejects corrupted, missing, wrongly pinned or
incomplete artifacts. Mutation controls remove the CLI branch, skip one JAR,
or bypass size, JAR-hash and class-hash checks; the corresponding assertions
fail for each mutant.

The hosted workflow separately acquires six exact Mojang JARs into a new
temporary SHA-1-keyed directory, verifies their pinned size and hashes, then
runs `inspect_issue45_sni_high.py --verify-known-hits-cache` as an offline
step. Cleanup runs even if an earlier step fails. The IP-filter download CLI
test now checks invocation arguments and failure propagation without depending
on success-message wording. These checks do not clear an advisory or authorize
a release.
