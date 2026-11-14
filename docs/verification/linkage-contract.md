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

The verifier deliberately rejects all non-constructor `invokespecial` uses and
cross-package protected instance instructions whose receiver would require
dataflow proof. A protected method handle is accepted only when its symbolic
receiver is constrained to the caller or a subtype. Dynamic constants and
unrecognized dynamic bootstraps are rejected; the supported invokedynamic form
is the standard three-argument `LambdaMetafactory.metafactory` bootstrap.
These restrictions can reject valid programs and must be revisited before
introducing an unsupported pattern. The fixtures include positive and negative
cases and exercise the actual namespace-adapter entry point.

This is not a complete JVM bytecode verifier or a proof of every transformed
Mixin behavior. Platform APIs rely on the configured Java `--release` target
and the runtime JVM; Fabric/Mixin callback internals rely on the declared
loader. The checker does not prove arbitrary operand-stack dataflow, all lambda
adaptation behavior, reflective calls, native code, or runtime-generated code.
The 1.0.0 artifacts still need their separately recorded runtime, graphical,
security and independent review gates. A passing static check is not visual or
release acceptance.
