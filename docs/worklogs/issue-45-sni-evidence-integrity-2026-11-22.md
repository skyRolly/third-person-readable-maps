# Issue 45: Netty SNI evidence integrity follow-up

PR #56's review and priority register are linked by SHA-256 over exact JSON
bytes. Its writer used platform text-mode newlines: on Windows it could hash
CRLF bytes that Git subsequently normalizes to LF, leaving the register's
embedded review checksum stale. The writer now creates new files exclusively
from explicit UTF-8, LF-terminated bytes. Existing evidence was not rewritten.
The regression simulates Windows newline translation, demonstrates the old
writer produces different bytes, and checks that a freshly generated review and
register match the retained bytes and ledger on both CI platforms.

The earlier CI unit test checked the current register's ledger path and hash,
but did not exercise the standalone verifier's copied coverage counts and
clearance flag. The same ledger-reference validator is now called by both the
CLI and CI tests. Mutations of each count, the clearance flag, path and checksum
are rejected. No advisory disposition, audit gate or risk decision changes.
All 490 findings remain blocking, and the High SNI investigation retains its
bounded static scope.
