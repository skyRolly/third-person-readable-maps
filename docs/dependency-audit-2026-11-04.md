# Initial dependency advisory audit — 2026-11-04

Historical initial package-match report. The [individual ledger](security-advisories.md)
and [monitoring record](dependency-monitoring.md) contain the current reviewed
status, full advisory records and additional runtime coverage. The recovered
1.21.11 hosted snapshot contains 86 packages, including Gradle core, rather than
the initial 85. Its affected-package count remains 10. Four-version runtime
manifest auditing adds matches for different 26.2 package versions; package counts
below must not be read as unique-advisory counts or a complete runtime inventory.

The read-only Gradle snapshots below were generated at the pinned branch heads
and queried against OSV on 2026-11-04. A match is a version-level advisory,
not a finding of reachability or exploitability in this mod. Maintainers
must triage the linked advisories and upstream exposure. These packages
were resolved from `libraries.minecraft.net`; do not force overrides in
the mod to silence the report. The 26.1–26.2 snapshot covers the 26.1
build target, not the libraries of each other runtime version. See the
[coverage limits and recurring workflow](releasing.md#dependency-maintenance).

## mc/1.21.11

Source `1bbd3f41b97ea5d0b78ae1909e846462078bdf9d`; 85 Maven packages queried, 0 snapshot entries unscanned, 10 packages with advisory matches.

- `at.yawk.lz4/lz4-java@1.8.1`: [GHSA-343h-94h5-c4wr](https://osv.dev/vulnerability/GHSA-343h-94h5-c4wr), [GHSA-4v53-57pg-c464](https://osv.dev/vulnerability/GHSA-4v53-57pg-c464), [GHSA-6cx8-rjf8-pr8g](https://osv.dev/vulnerability/GHSA-6cx8-rjf8-pr8g), [GHSA-cmp6-m4wj-q63q](https://osv.dev/vulnerability/GHSA-cmp6-m4wj-q63q), [GHSA-gm45-99xc-r7wv](https://osv.dev/vulnerability/GHSA-gm45-99xc-r7wv), [GHSA-mcr4-qmvw-px4g](https://osv.dev/vulnerability/GHSA-mcr4-qmvw-px4g), [GHSA-xx22-p4ch-683r](https://osv.dev/vulnerability/GHSA-xx22-p4ch-683r)
- `com.google.guava/guava@33.5.0-jre`: [GHSA-xxph-c9ww-hj94](https://osv.dev/vulnerability/GHSA-xxph-c9ww-hj94)
- `io.netty/netty-codec-compression@4.2.7.Final`: [GHSA-558v-64gr-wgg4](https://osv.dev/vulnerability/GHSA-558v-64gr-wgg4), [GHSA-mj4r-2hfc-f8p6](https://osv.dev/vulnerability/GHSA-mj4r-2hfc-f8p6)
- `io.netty/netty-codec-http@4.2.7.Final`: [GHSA-38f8-5428-x5cv](https://osv.dev/vulnerability/GHSA-38f8-5428-x5cv), [GHSA-4mp9-239f-g9hg](https://osv.dev/vulnerability/GHSA-4mp9-239f-g9hg), [GHSA-57rv-r2g8-2cj3](https://osv.dev/vulnerability/GHSA-57rv-r2g8-2cj3), [GHSA-6cqp-g7gg-8hr5](https://osv.dev/vulnerability/GHSA-6cqp-g7gg-8hr5), [GHSA-6jqx-86gh-f27w](https://osv.dev/vulnerability/GHSA-6jqx-86gh-f27w), [GHSA-84h7-rjj3-6jx4](https://osv.dev/vulnerability/GHSA-84h7-rjj3-6jx4), [GHSA-8c42-7qj2-3j46](https://osv.dev/vulnerability/GHSA-8c42-7qj2-3j46), [GHSA-f6hv-jmp6-3vwv](https://osv.dev/vulnerability/GHSA-f6hv-jmp6-3vwv), [GHSA-gcjf-9mgh-3p7g](https://osv.dev/vulnerability/GHSA-gcjf-9mgh-3p7g), [GHSA-hvcg-qmg6-jm4c](https://osv.dev/vulnerability/GHSA-hvcg-qmg6-jm4c), [GHSA-jppx-w49h-x2qq](https://osv.dev/vulnerability/GHSA-jppx-w49h-x2qq), [GHSA-m4cv-j2px-7723](https://osv.dev/vulnerability/GHSA-m4cv-j2px-7723), [GHSA-mvh2-crg5-v77c](https://osv.dev/vulnerability/GHSA-mvh2-crg5-v77c), [GHSA-pwqr-wmgm-9rr8](https://osv.dev/vulnerability/GHSA-pwqr-wmgm-9rr8), [GHSA-q4f6-jm68-57ww](https://osv.dev/vulnerability/GHSA-q4f6-jm68-57ww), [GHSA-v8h7-rr48-vmmv](https://osv.dev/vulnerability/GHSA-v8h7-rr48-vmmv), [GHSA-xxqh-mfjm-7mv9](https://osv.dev/vulnerability/GHSA-xxqh-mfjm-7mv9)
- `io.netty/netty-handler@4.2.7.Final`: [GHSA-3qp7-7mw8-wx86](https://osv.dev/vulnerability/GHSA-3qp7-7mw8-wx86), [GHSA-c4c3-7fpv-j4q5](https://osv.dev/vulnerability/GHSA-c4c3-7fpv-j4q5), [GHSA-c653-97m9-rcg9](https://osv.dev/vulnerability/GHSA-c653-97m9-rcg9), [GHSA-fccg-mwvh-qqg4](https://osv.dev/vulnerability/GHSA-fccg-mwvh-qqg4), [GHSA-x4gw-5cx5-pgmh](https://osv.dev/vulnerability/GHSA-x4gw-5cx5-pgmh)
- `io.netty/netty-transport-classes-epoll@4.2.7.Final`: [GHSA-rwm7-x88c-3g2p](https://osv.dev/vulnerability/GHSA-rwm7-x88c-3g2p)
- `io.netty/netty-transport-native-epoll@4.2.7.Final`: [GHSA-w573-9ffj-6ff9](https://osv.dev/vulnerability/GHSA-w573-9ffj-6ff9)
- `io.netty/netty-transport-native-kqueue@4.2.7.Final`: [GHSA-w573-9ffj-6ff9](https://osv.dev/vulnerability/GHSA-w573-9ffj-6ff9)
- `org.apache.logging.log4j/log4j-api@2.25.2`: [GHSA-qv9r-c865-cp47](https://osv.dev/vulnerability/GHSA-qv9r-c865-cp47)
- `org.apache.logging.log4j/log4j-core@2.25.2`: [GHSA-3pxv-7cmr-fjr4](https://osv.dev/vulnerability/GHSA-3pxv-7cmr-fjr4), [GHSA-445c-vh5m-36rj](https://osv.dev/vulnerability/GHSA-445c-vh5m-36rj), [GHSA-6hg6-v5c8-fphq](https://osv.dev/vulnerability/GHSA-6hg6-v5c8-fphq), [GHSA-h383-gmxw-35v2](https://osv.dev/vulnerability/GHSA-h383-gmxw-35v2), [GHSA-vc5p-v9hr-52mj](https://osv.dev/vulnerability/GHSA-vc5p-v9hr-52mj)

## mc/26.1-26.2

Source `6891b6080e4bea981f7a7399a061b32f95f3452e`; 84 Maven packages queried, 0 snapshot entries unscanned, 10 packages with advisory matches.

- `at.yawk.lz4/lz4-java@1.10.1`: [GHSA-343h-94h5-c4wr](https://osv.dev/vulnerability/GHSA-343h-94h5-c4wr), [GHSA-4v53-57pg-c464](https://osv.dev/vulnerability/GHSA-4v53-57pg-c464), [GHSA-6cx8-rjf8-pr8g](https://osv.dev/vulnerability/GHSA-6cx8-rjf8-pr8g), [GHSA-gm45-99xc-r7wv](https://osv.dev/vulnerability/GHSA-gm45-99xc-r7wv), [GHSA-mcr4-qmvw-px4g](https://osv.dev/vulnerability/GHSA-mcr4-qmvw-px4g), [GHSA-xx22-p4ch-683r](https://osv.dev/vulnerability/GHSA-xx22-p4ch-683r)
- `com.google.guava/guava@33.5.0-jre`: [GHSA-xxph-c9ww-hj94](https://osv.dev/vulnerability/GHSA-xxph-c9ww-hj94)
- `io.netty/netty-codec-compression@4.2.7.Final`: [GHSA-558v-64gr-wgg4](https://osv.dev/vulnerability/GHSA-558v-64gr-wgg4), [GHSA-mj4r-2hfc-f8p6](https://osv.dev/vulnerability/GHSA-mj4r-2hfc-f8p6)
- `io.netty/netty-codec-http@4.2.7.Final`: [GHSA-38f8-5428-x5cv](https://osv.dev/vulnerability/GHSA-38f8-5428-x5cv), [GHSA-4mp9-239f-g9hg](https://osv.dev/vulnerability/GHSA-4mp9-239f-g9hg), [GHSA-57rv-r2g8-2cj3](https://osv.dev/vulnerability/GHSA-57rv-r2g8-2cj3), [GHSA-6cqp-g7gg-8hr5](https://osv.dev/vulnerability/GHSA-6cqp-g7gg-8hr5), [GHSA-6jqx-86gh-f27w](https://osv.dev/vulnerability/GHSA-6jqx-86gh-f27w), [GHSA-84h7-rjj3-6jx4](https://osv.dev/vulnerability/GHSA-84h7-rjj3-6jx4), [GHSA-8c42-7qj2-3j46](https://osv.dev/vulnerability/GHSA-8c42-7qj2-3j46), [GHSA-f6hv-jmp6-3vwv](https://osv.dev/vulnerability/GHSA-f6hv-jmp6-3vwv), [GHSA-gcjf-9mgh-3p7g](https://osv.dev/vulnerability/GHSA-gcjf-9mgh-3p7g), [GHSA-hvcg-qmg6-jm4c](https://osv.dev/vulnerability/GHSA-hvcg-qmg6-jm4c), [GHSA-jppx-w49h-x2qq](https://osv.dev/vulnerability/GHSA-jppx-w49h-x2qq), [GHSA-m4cv-j2px-7723](https://osv.dev/vulnerability/GHSA-m4cv-j2px-7723), [GHSA-mvh2-crg5-v77c](https://osv.dev/vulnerability/GHSA-mvh2-crg5-v77c), [GHSA-pwqr-wmgm-9rr8](https://osv.dev/vulnerability/GHSA-pwqr-wmgm-9rr8), [GHSA-q4f6-jm68-57ww](https://osv.dev/vulnerability/GHSA-q4f6-jm68-57ww), [GHSA-v8h7-rr48-vmmv](https://osv.dev/vulnerability/GHSA-v8h7-rr48-vmmv), [GHSA-xxqh-mfjm-7mv9](https://osv.dev/vulnerability/GHSA-xxqh-mfjm-7mv9)
- `io.netty/netty-handler@4.2.7.Final`: [GHSA-3qp7-7mw8-wx86](https://osv.dev/vulnerability/GHSA-3qp7-7mw8-wx86), [GHSA-c4c3-7fpv-j4q5](https://osv.dev/vulnerability/GHSA-c4c3-7fpv-j4q5), [GHSA-c653-97m9-rcg9](https://osv.dev/vulnerability/GHSA-c653-97m9-rcg9), [GHSA-fccg-mwvh-qqg4](https://osv.dev/vulnerability/GHSA-fccg-mwvh-qqg4), [GHSA-x4gw-5cx5-pgmh](https://osv.dev/vulnerability/GHSA-x4gw-5cx5-pgmh)
- `io.netty/netty-transport-classes-epoll@4.2.7.Final`: [GHSA-rwm7-x88c-3g2p](https://osv.dev/vulnerability/GHSA-rwm7-x88c-3g2p)
- `io.netty/netty-transport-native-epoll@4.2.7.Final`: [GHSA-w573-9ffj-6ff9](https://osv.dev/vulnerability/GHSA-w573-9ffj-6ff9)
- `io.netty/netty-transport-native-kqueue@4.2.7.Final`: [GHSA-w573-9ffj-6ff9](https://osv.dev/vulnerability/GHSA-w573-9ffj-6ff9)
- `org.apache.logging.log4j/log4j-api@2.25.2`: [GHSA-qv9r-c865-cp47](https://osv.dev/vulnerability/GHSA-qv9r-c865-cp47)
- `org.apache.logging.log4j/log4j-core@2.25.2`: [GHSA-3pxv-7cmr-fjr4](https://osv.dev/vulnerability/GHSA-3pxv-7cmr-fjr4), [GHSA-445c-vh5m-36rj](https://osv.dev/vulnerability/GHSA-445c-vh5m-36rj), [GHSA-6hg6-v5c8-fphq](https://osv.dev/vulnerability/GHSA-6hg6-v5c8-fphq), [GHSA-h383-gmxw-35v2](https://osv.dev/vulnerability/GHSA-h383-gmxw-35v2), [GHSA-vc5p-v9hr-52mj](https://osv.dev/vulnerability/GHSA-vc5p-v9hr-52mj)

## mc/26.3

Source `0839b2cc31ec2a57ffeae82a8b8f892a649f8eaf`; 86 Maven packages queried, 0 snapshot entries unscanned, 5 packages with advisory matches.

- `at.yawk.lz4/lz4-java@1.10.1`: [GHSA-343h-94h5-c4wr](https://osv.dev/vulnerability/GHSA-343h-94h5-c4wr), [GHSA-4v53-57pg-c464](https://osv.dev/vulnerability/GHSA-4v53-57pg-c464), [GHSA-6cx8-rjf8-pr8g](https://osv.dev/vulnerability/GHSA-6cx8-rjf8-pr8g), [GHSA-gm45-99xc-r7wv](https://osv.dev/vulnerability/GHSA-gm45-99xc-r7wv), [GHSA-mcr4-qmvw-px4g](https://osv.dev/vulnerability/GHSA-mcr4-qmvw-px4g), [GHSA-xx22-p4ch-683r](https://osv.dev/vulnerability/GHSA-xx22-p4ch-683r)
- `com.google.guava/guava@33.6.0-jre`: [GHSA-xxph-c9ww-hj94](https://osv.dev/vulnerability/GHSA-xxph-c9ww-hj94)
- `io.netty/netty-codec-http@4.2.16.Final`: [GHSA-8c42-7qj2-3j46](https://osv.dev/vulnerability/GHSA-8c42-7qj2-3j46)
- `io.netty/netty-handler@4.2.16.Final`: [GHSA-c4c3-7fpv-j4q5](https://osv.dev/vulnerability/GHSA-c4c3-7fpv-j4q5), [GHSA-fccg-mwvh-qqg4](https://osv.dev/vulnerability/GHSA-fccg-mwvh-qqg4)
- `org.apache.logging.log4j/log4j-api@2.26.0`: [GHSA-qv9r-c865-cp47](https://osv.dev/vulnerability/GHSA-qv9r-c865-cp47)
