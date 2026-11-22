# Issue 45: focused-review runtime manifest binding

A follow-up review of PR #55 found that equal source commits, package scopes
and advisory fingerprints did not prove that the runtime manifests used by a
new audit were the same manifests examined by the focused investigation. The
priority exporter now requires exact, unique Minecraft-version coverage and
matches each reviewed version metadata SHA-1 against both the archived and
live audit report. A missing or changed manifest stops the export and requires
new review; no disposition or release gate is relaxed.

The former PR #55 validator is retained as an isolated test control. It accepts
a mutated runtime manifest digest or missing reviewed manifest while the updated
validator rejects each. The normal source-bound register remains byte-identical
to the retained baseline, and its findings remain blocking.

Independent scans can observe different `modified` timestamps for otherwise
identical advisory content. The exporter now records every differing timestamp
by source instead of selecting one or treating the difference alone as stale
review. Changes to other advisory fields or fingerprints still require review.
The audit reconciliation continues to report timestamp changes and returns a
blocking exit status while unresolved findings remain. No risk is accepted.
