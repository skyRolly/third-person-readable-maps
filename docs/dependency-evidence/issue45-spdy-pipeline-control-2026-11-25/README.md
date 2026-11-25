# Original synthetic SPDY pipeline observation

This is the byte-for-byte original Actions ZIP from [job 139418879421](https://github.com/skyRolly/third-person-readable-maps/actions/runs/45674664714/job/139418879421),
[artifact 15051112080](https://github.com/skyRolly/third-person-readable-maps/actions/runs/45674664714/artifacts/15051112080),
on exact historical checkout `f21a88af720cf4d43890158a0f098ac3ffb1f691`. It is not a report of subsequent HEADs.

Actual hosted Temurin 25.0.5+8 constructed, registered, removed and cleaned up
the handler in all three manifest-pinned profiles, with no queued messages.
The three Python protocol tests only validate output parsing; the separate
hosted observation step executes the real Java source. All 23 library records
match the original class-only observations. Independent download verification
checked ZIP and JSON hashes, CRC, sole member, source SHA-256 against all four
committed sources, historical identities and report scope.

From the repository root:

```sh
python diagnostics/issue45-spdy-pipeline-probe/verify_pipeline_archive.py
python -m unittest discover -s diagnostics/issue45-spdy-pipeline-probe -p test_verify_pipeline_archive.py -v
```

CI verifies both historical archives and executes the new pipeline observation.
The reviewed repository pins are not a signature or independent trust root.
Do not overwrite the original archive or relabel its checkout.
No frames, actual Minecraft pipeline, runtime reachability or risk acceptance
were established. All four SPDY advisory occurrences remain release-blocking.
