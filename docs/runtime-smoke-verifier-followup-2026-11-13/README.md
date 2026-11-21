# Verifier-follow-up local walking smoke — 2026-11-13 UTC

The [index](index.json) lists completed and pending versions separately. Each
completed observation ran the locally rebuilt 1.0.0 JAR associated with the
new product source commit and retained the client log, movement record, ending
player data and two walking frames. The [collector](collect.py) checks source
and artifact identities against the transition and build results before copying
them. Tests ran in copied local worlds on Linux Xorg/Mesa software rendering;
the [harnesses](harness/) and retained-file hashes are included for inspection.
The original world fixtures and system toolchains are not committed.

All 48 advertised versions completed this source-bound local-world startup
and short walking sweep. The 26.2 and 26.3 retries saved and exited normally;
the earlier timeout and recovery remain separately documented as historical
attempts. Some copied modern worlds required the recorded upgrade prompts.

These observations are partial diagnostics, not full graphical acceptance,
hardware-GPU or multiplayer validation, or independent human approval. Earlier
1.0.0 runs on the previous source heads are kept separately in
[the historical runtime evidence](../runtime-smoke-1.0.0/); matching artifact
hashes do not relabel those runs as current source-bound tests.

The initial sweep was interrupted with incomplete runs for 1.16, 1.18.1 and
1.21.1; their incomplete local directories were preserved, and no walking
result was recorded for those attempts. The early and middle sweeps were
resumed on separate displays using the included `early-96` and `middle-97`
harnesses; the later sweep resumed with `later-98`. The first modern attempt
with `modern-99` [failed during Mixin initialization](1.21.11-initialization-attempt/).
Its cause is unconfirmed. The `modern-100` retry uses checksum-verified private
copies of the Fabric launcher libraries, SDL EGL for the software-renderer
environment, and version-specific save-log detection. The subsequent
[26.1 attempt](26.1-upgrade-timeout-attempt/) timed out after a manual
world-upgrade prompt on the copied fixture. The `modern-102` retry and its
join-prompt sidecar use recorded OCR for recognized prompts; any manual
intervention is documented with the individual result. Completed results are
recorded independently and incomplete attempts are not counted as passes.
