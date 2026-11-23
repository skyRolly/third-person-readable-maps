# Issue 45 historical GH_TOKEN owner handoff

The repository evidence does not include the historical token's identifier,
permission history, validity dates, or account/repository audit trail. The
current task environment exposes no account-level token creation or audit log
history. A configured GitHub CLI credential is not evidence about the
historical token and must not be copied into a report.

The credential owner should provide a short, secret-free disposition with:

1. The token's non-secret identifier/fingerprint, creation date, expiration,
   and historical permission scopes. Never disclose the token value.
2. Whether it could write repository contents, workflows, releases, or
   organization settings during the exposure window.
3. GitHub account, organization, repository, and Actions audit activity for
   that window, including unexplained workflow, branch, release, settings, or
   credential events.
4. Whether the token could be inherited by prior Gradle subprocesses or
   printed by any historical build/test command.
5. The evidence that rules exposure in or out. If it cannot be excluded,
   revoke or rotate the token and record the completion time and replacement
   controls without recording either secret.

Until the owner supplies that account-level evidence, the historical
repository-write-capable credential assessment remains unresolved and
release-blocking. The repository's build guard does not prove historical
non-disclosure.
