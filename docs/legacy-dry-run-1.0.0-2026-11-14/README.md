# Non-publishing 1.0.0 candidate rehearsal — 2026-11-14

**Historical run:** the [plan](candidate-plan.json) pins all ten legacy candidate heads and three
separate maintenance proposal heads. The [candidate matrix](candidate-matrix.json)
contains 13 groups and 48 unique explicit Minecraft versions. The local
[rehearsal](rehearse.py) checked the remote source identities and aggregated
the exact clean-build 1.0.0 JARs into a candidate-only
[manifest](release-manifest.json) and [SHA256SUMS](SHA256SUMS). The JARs are
local build outputs and are not committed here. All checksums passed during
the run, as recorded in the [log](rehearsal.log).

The manifest identifies coordinator commit
`a8f53c353204ff6120a5daf5c3f65f703f0fe0e6`, which contained the exact release
validation code and this harness used for the run. Later evidence-only commits
do not change that identity. The [15 negative controls](negative-controls.json)
rejected missing or duplicate groups/artifacts, wrong versions, mixed 0.0.2
and 1.0.0 JARs, wrong metadata or namespace, changed checksums, wrong source,
missing strict runtime evidence and candidate publication attempts. Earlier
rehearsals and their source identities remain [historical](../legacy-dry-run-1.0.0.md).

The `tag` value in the candidate manifest is a proposed release identifier;
no Git tag, draft release or public release was created. The plan intentionally
does not claim strict runtime acceptance. This local candidate aggregation is
not production authorization; repeat it against reviewed, integrated exact
heads after the security, graphical, administrative and approval gates pass.

The [final-proposal rehearsal](stabilization-final/) uses the subsequently advanced product heads and preserves this earlier run.
