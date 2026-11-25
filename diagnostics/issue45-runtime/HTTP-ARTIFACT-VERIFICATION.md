# Issue #45 HTTP codec artifact verification

This opt-in, offline verifier covers the four retained GHSA-6jqx-86gh-f27w
occurrences (seven game manifests, three distinct Netty HTTP codec JARs).
It is separate from the existing synthetic compression matrix, which does
not include the HTTP codec. No classes are loaded or executed. No network
connections or game processes are initiated by the verifier.

Use an authorized existing Minecraft library cache (or fetch the three
official JARs separately using their manifest URLs and preserve the relative
Maven paths). The verifier checks the retained manifest SHA-256, game ID,
exact dependency coordinate, official URL/path, size and SHA-1, then records
the observed artifact SHA-256 and bounded SPDY class-member digests. It
rejects missing or conflicting identities, duplicate ZIP members and missing
or invalid class headers. Class inventory is not bytecode verification.

Run from the repository checkout, with an output path that does not exist
and is outside the retained historical evidence directory:

```sh
python diagnostics/issue45-runtime/verify_http_artifacts.py --libraries-root /path/to/libraries --output /path/to/new-http-observation.json
python -m unittest discover -s tests -p test_issue45_http_artifacts.py -v
```

The operator must retain the exact verifier checkout identity and report
SHA-256 when archiving a new observation. The output is only static artifact
identity and class-inventory evidence; neither presence nor absence of a
class establishes actual game runtime reachability. All four occurrences
remain blocking. No risk acceptance, release or managed-library override is
authorized. Actual class-loader/code-source and pipeline observations still
require separately reviewed diagnostics and authorized real game runs.

Do not overwrite historical evidence or upload the raw dependency JARs,
absolute host paths or account information. No malformed frames or traffic
are needed for this static verification.

## Hosted end-to-end artifact check

The separate Issue 45 official HTTP artifact verification workflow exercises
the documented offline CLI on the exact PR head (or main push SHA). It
reconciles all seven pinned manifest identities before acquiring each of
the three official Mojang artifacts once, refuses redirects, bounds reads
and checks size/SHA-1 before writing into a disposable library cache.
The same offline CLI checks the actual ZIP inventories. Only the resulting
static JSON report is uploaded; the log records the checkout, report
SHA-256, artifact SHA-256 values and SPDY class counts. The temporary JARs
are deleted. Download, integrity or CLI failures fail the job. No game or
class execution, release clearance, or risk acceptance is implied.

For an authorized network-enabled checkout, the same hosted path can be run
locally with a new output file:

```sh
python diagnostics/issue45-runtime/verify_official_http_artifacts.py --output /path/to/new-http-observation.json
```

Both verifier scripts must have exact working-tree bytes matching their
committed Git blobs at HEAD. The hosted/local wrapper checks these bytes
before acquisition, before the offline CLI, and before publishing the report,
and logs their SHA-256 digests under repository-relative source names beside
the checkout and report digest. Staged or unstaged source edits are rejected,
even when hidden by an index optimization. Unrelated local changes are
allowed. Use a stable checkout without concurrent edits and without checkout
filters that alter these script bytes (including line-ending conversion).
Commit intended script changes before running the wrapper. The report is
first generated in a temporary directory and only published to the exclusive
output path after successful verification and final source checks.
These checks guard ordinary source drift; they are not attestation against
an adversarial local interpreter, process or modified verifier.
