# Packaged-JAR linkage verification contract

Run `python3 -m unittest discover -s tests` and
`python3 scripts/verify_supported_apis.py --jar build/libs` after a clean
build. The verifier reads the packaged class files and checks each declared
Minecraft version against its integrity-checked client, mappings and declared
game libraries. Candidate, mapped game and selected game-library classes share
one resolver; external library names are never Minecraft-remapped. The verifier
checks each distinct Linux, Windows and macOS library classpath selected by the
supported metadata OS-name rules. Unknown rule conditions, ambiguous libraries
within one platform and duplicate library classes fail closed.
The preliminary constant-pool member check uses that same selected composite
classpath, so a reference whose game-owned symbolic owner inherits a member
from a runtime library is resolved on every applicable platform. Consumed
instructions still receive the separate access, kind and staticness checks.

The checked subset includes consumed field and method instructions, constructor
calls, class/interface invocation kind, staticness, applicable access, field
initialization context and consumed method handles. Writes to final fields are
accepted only in the declaring effective class's appropriate initializer;
final-field setter handles and unproven write contexts are rejected. A Mixin
member without a target collision is checked in its effective target context;
collisions and references from another class to a Mixin are unsupported.
Mixin injection annotations are limited to one HEAD or TAIL target, the modeled
`cancellable` option, and the required configuration; unsupported options
fail closed. Consumed method-type, method-handle and dynamic descriptors receive
class-access checks. Ordinary method descriptors do not by themselves imply
that the caller must access each named type.

The verifier deliberately rejects non-constructor `invokespecial` uses outside
the bounded same-class private case and cross-package protected instance instructions whose receiver would require
dataflow proof. A protected method handle is accepted only when its symbolic
receiver is constrained to the caller or a subtype. Dynamic constants and
unrecognized dynamic bootstraps are rejected; the supported invokedynamic form
is the standard three-argument `LambdaMetafactory.metafactory` bootstrap.
These restrictions can reject valid programs and must be revisited before
introducing an unsupported pattern. The fixtures include positive and negative
cases and exercise the actual namespace-adapter entry point.

Private access between Java 11+ nestmates requires parsed `NestHost` and
`NestMembers` attributes, reciprocal host membership, the same runtime package,
and the same verified candidate, game, or library-archive origin. The model
deliberately rejects cross-archive nests because a common runtime class loader
is not established. Mixin references use the transformed target as caller;
the original Mixin's nest privileges are not transferred. Same-class private
non-constructor `invokespecial` is supported for Java 8 compiler accessors;
other non-constructor special selection remains unsupported. Final-field writes
still require the declaring class and initializer, even for nestmates.

Ordinary descriptors require referenced game and dependency classes to exist;
they do not by themselves make a package-private type inaccessible to a caller.
Actual class instructions, class constants, consumed method-type and
method-handle descriptor classes are checked for accessibility, including
candidate-owned classes. A Mixin's direct self `checkcast` is checked against
its transformed target; other class uses referring to a Mixin are outside the
supported transformation subset and fail closed.

Direct candidate superclasses and superinterfaces are checked independently of
ordinary descriptors: the class must exist, be the correct class/interface
kind, be accessible, and not be final when extended. Duplicate interfaces,
cycles, missing hierarchy edges and sealed supertypes are rejected. The model
also rejects sealed candidate declarations rather than claiming to prove their
module and permitted-subclass rules. `java/lang/Object` is the supported direct
platform superclass for candidate classes; other direct candidate platform
supertypes are rejected. Platform hierarchy edges within the game or libraries
are left to the configured Java runtime. For non-public access the bounded
runtime-package model requires matching package names and verified candidate,
game, or single-library-archive origin; cross-archive same-package access is
rejected when common class-loader identity is not established.

Mixins are not treated as ordinary runtime subclasses. Their declared
superclass must occur in the target's superclass ancestry, and interfaces they
contribute are checked as accesses from the transformed target. References to
another Mixin, unsupported platform superinterfaces and unproven transformations
fail closed. A Java 8 private helper invoked on the same Mixin is resolved with
the effective target as both owner and caller; a different Mixin, a collision,
or a non-private or otherwise unsupported special invocation is still rejected.
The default `java/lang/Object` superclass is accepted after the target and all
reachable non-platform hierarchy edges have been validated, even when the
target ancestry crosses a platform superclass. Other explicit superclass
relationships must be established by the bounded lookup; unresolvable platform
ancestry is not assumed. Platform class validity remains the runtime JVM's
responsibility. Enum and record fixtures exercise only this static hierarchy
model, not a claim that every transformation of those targets is supported.
The bounded resolver does not load platform class metadata. A member reference
whose symbolic owner is a game, library or candidate class, but whose only
declaration lies in an unresolved platform superclass or interface, therefore
fails closed as a missing member or game reference even when the JVM could resolve it. Direct
platform-owned references remain delegated to the configured Java runtime.

| Reference | Verification within this contract | Boundary |
|---|---|---|
| Ordinary descriptor | Required game/library class exists | Descriptor alone is not an access to its type. |
| Class instruction, constant, method type/handle descriptor | Existence and applicable class access | Platform APIs rely on the Java target and JVM. |
| Candidate superclass or superinterface | Existence, kind, access, finality, ancestry/cycle and supported sealing | Non-Object candidate platform supertypes and sealed hierarchies are rejected. |
| Mixin superclass and contributed interface | Target ancestry and effective-target access | Arbitrary Mixin hierarchy and interface targets are unsupported. |
| Field, method, constructor or handle | Resolution, owner/member access, staticness and invocation kind | Unproven special selection and protected receiver dataflow fail closed. |
| Final field write | Effective declaring class and initializer context | Setter handles and unproven contexts fail closed. |
| Private nestmate access | Reciprocal metadata, package and verified origin | Cross-archive nest identity is not assumed. |
| Supported dynamic bootstrap | Known LambdaMetafactory form and consumed references | Other dynamic bootstraps and runtime-generated linkage are rejected or unproven. |

This is not a complete JVM bytecode verifier or a proof of every transformed
Mixin behavior. Platform APIs rely on the configured Java `--release` target
and the runtime JVM; Fabric/Mixin callback internals rely on the declared
loader. The checker does not prove arbitrary operand-stack dataflow, all lambda
adaptation behavior, reflective calls, native code, or runtime-generated code.
The 1.0.0 artifacts still need their separately recorded runtime, graphical,
security and independent review gates. A passing static check is not visual or
release acceptance.
