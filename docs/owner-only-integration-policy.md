# Owner-only integration and release authorization

The repository owner selected owner-controlled PR integration and removed all
branch-protection policies and rulesets. The owner manually inspects and merges
PRs; GitHub self-approval is not used or required. Successful exact-head checks
are voluntary integration evidence, not enforced branch rules.

`scripts/authorize_release.py` applies this policy to release source heads. For
each coordinated branch it requires an unprotected exact head, no effective
branch rules or repository rulesets, one unambiguous PR merge into that branch,
and the repository owner as the recorded merger. It then requires the current
push CI run and the branch-role checks on that exact commit. It does not require
an independent PR approval or claim that `mergeable` establishes safety.

These source integration checks do not replace release controls. The authorizer
still requires the configured release environment and an actual independent
deployment approval for the relevant first-attempt dispatch. Source-bound
artifact verification, dependency security, strict per-version runtime
evidence, and publication safeguards remain required. Candidate rehearsal is
non-publishing and cannot authorize a tag, draft, or public release.

The current integration execution and any unsatisfied gates are tracked in
[Issue #44](https://github.com/skyRolly/third-person-readable-maps/issues/44).
