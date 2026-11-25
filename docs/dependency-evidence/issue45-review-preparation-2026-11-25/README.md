# Issue 45 — review preparation checkpoint (2026-11-25)

This is a **proposal for independent review**, not a reviewed advisory disposition,
new scan, runtime capture, or release authorization. It changes no product
source, dependency, audit rule, existing diagnostic, or historical archive.

## PR 22: three-way comparison

The user supplied the CodeRabbit coding agent's five files. The maintenance
session independently read them and the previously downloaded November 24
hosted audit/snapshot ZIPs. SHA-256 and CRC matched; the November 25 local report
hash matched the [agent's issue comment](https://github.com/skyRolly/third-person-readable-maps/issues/45#issuecomment-7171830911).
All 24 normalized package/version/advisory/severity tuples matched across the
three reports; the two OSV inventories and all 24 advisory fingerprints also
matched. All are failing in both Gradle and Minecraft 1.19.3 scopes. The
normalized review worklist preserves these observations and proposed review
topics; the five uploaded original files and two hosted ZIPs are **not**
embedded here, only their digests and provenance. CI checks the proposal's
structure and scope and compares all 24 exact package/version, advisory,
severity, fingerprint, scope and blocking-status identities against the
retained November 21 v2 finding index (candidate 1.19.3, exact source).
The historical index's Git blob is pinned and calculated offline from
the working-tree bytes; no Git history is needed. This verifies consistency
with retained repository evidence, not the authenticity or availability
of those external inputs or a fresh audit. Repository-reviewed pins are
not an independent trust root. Retain the original inputs separately for a subsequent reviewed archive.

The local scan used a retained same-candidate snapshot from November 21;
the hosted snapshot is a different dated observation. Neither is a fresh
Gradle resolution by this session. The repository SBOM snapshot contains 93
packages (85 Maven), including Minecraft 1.21.11; it does not establish
authoritative alert attribution or coverage of every branch. The coding
agent reported HTTP 403 from the alerts endpoint. No risk acceptance.

The Critical GHSA-c4c3-7fpv-j4q5 remains applicable by version to Netty
4.1.82.Final. The retained exact vanilla TLS investigation is bounded
static evidence, not a reviewed non-reachability decision. Seek supported
upstream remediation and independently review actual configuration and
component ownership. Do not override Minecraft-managed libraries.
All 24 remain blocking. The 24 are already included in the dated 385
candidate occurrences, not an addition to the 490 combined total.

## SPDY capture plan

The separate plan records all seven client manifests across four retained
occurrences. The two planned process roles per row are client and dedicated
server: 14 proposed captures, zero executed. Server-bundle identity must be
verified separately; the client manifest HTTP coordinate is not an assertion
about a dedicated server's bundled libraries. The existing six-environment
compression matrix is separate and remains unchanged.

Before implementing or running a new observer, independently review its
design and privacy boundary. Preserve the original compression agent and
build inputs. A separately built observer and validator must pass synthetic
positive/negative registration, loaded-only, duplicate defining loaders,
digest mismatch, truncated capture and redaction controls. Observe already
defined classes and passive handler lifecycle only; do not proactively load
target classes in a game or send malformed frames. Retain only allowlisted
class names, hashes, counts, roles and run-local opaque IDs, not packet
contents, addresses, paths, account information, arguments or credentials.
Use authorized disposable local game environments, operator consent and
EULA decisions, normal join and disconnect, and orderly shutdown. Pin actual
client/server distribution, mod source/artifact, launcher/JVM, agent and
observed library identities. No synthetic result substitutes for actual
Minecraft. A missing observation is not proof of non-reachability.

The plan checks use the retained HTTP verifier's historical source/manifest
pins, not mutable current branch registries, and verify actual retained
client manifest bytes offline. No Git history fetch, network access, or game
launch is required. A later, separately reviewed capture schema must not
overwrite this planning-only record.

Run the new offline checks from the repository root:
```sh
python -m unittest discover -s tests -p test_issue45_review_preparation.py -v
```
