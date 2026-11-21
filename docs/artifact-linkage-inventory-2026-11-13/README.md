# Actual artifact linkage operations — 2026-11-13

The [collector](collect.py) reads every class in the 13 locally rebuilt
proposed JARs, verifies each artifact digest and source commit against the
build index, and verifies that the class-file parser is byte-identical to the
parser committed on every proposed product head. The [index](index.json)
records the resulting counts and exact identities. Operations whose owner is a
mod class but whose member is not declared there are conservatively treated as
external or inherited, because a Mixin can rewrite them to its target.

No proposed artifact contains an external-or-inherited `putfield` or
`putstatic`, or an external-or-inherited non-constructor `invokespecial`.
This bounds two known verifier limitations for these particular artifact bytes;
it does not establish protected-receiver dataflow, all constructor semantics,
descriptor accessibility, dynamic linkage, or correctness of future JARs.
Instruction counts are not a substitute for the per-version checks or runtime
tests. Retest this inventory whenever the source, verifier or artifact changes.
