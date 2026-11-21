package tprm.probe;

import java.lang.instrument.ClassFileTransformer;
import java.lang.instrument.Instrumentation;
import java.security.ProtectionDomain;
import java.util.HashMap;
import java.util.Map;
import org.objectweb.asm.ClassReader;
import org.objectweb.asm.ClassVisitor;
import org.objectweb.asm.ClassWriter;
import org.objectweb.asm.MethodVisitor;
import org.objectweb.asm.Opcodes;

/** Diagnostic agent for one known 1.21.11 proposal JAR, not a product mod. */
public final class MapDataAgent {
    private static final Map<String, Boolean> STATES = new HashMap<>();

    public static synchronized void observe(Object id, Object data) {
        try {
            String key = String.valueOf(id);
            boolean available = data != null;
            Boolean previous = STATES.put(key, available);
            if (previous == null || previous.booleanValue() != available) {
                System.out.println("TPRM_MAP_PROBE time_ms=" + System.currentTimeMillis()
                        + " id=" + key + " data_available=" + available);
            }
        } catch (Throwable failure) {
            System.out.println("TPRM_MAP_PROBE observer_error=" + failure.getClass().getSimpleName());
        }
    }

    public static void premain(String ignored, Instrumentation instrumentation) {
        instrumentation.addTransformer(new ClassFileTransformer() {
            @Override public byte[] transform(Module module, ClassLoader loader, String name,
                    Class<?> type, ProtectionDomain domain, byte[] bytes) {
                if (!"tech/rolly/thirdpersonreadablemaps/ReadableMapSurface".equals(name)) return null;
                ClassReader reader = new ClassReader(bytes);
                ClassWriter writer = new ClassWriter(reader, ClassWriter.COMPUTE_MAXS);
                int[] matches = {0};
                reader.accept(new ClassVisitor(Opcodes.ASM9, writer) {
                    @Override public MethodVisitor visitMethod(int access, String method, String desc,
                            String signature, String[] exceptions) {
                        MethodVisitor base = super.visitMethod(access, method, desc, signature, exceptions);
                        if (!"submitReadableMap".equals(method)) return base;
                        return new MethodVisitor(Opcodes.ASM9, base) {
                            @Override public void visitMethodInsn(int opcode, String owner, String called,
                                    String descriptor, boolean isInterface) {
                                super.visitMethodInsn(opcode, owner, called, descriptor, isInterface);
                                if (opcode == Opcodes.INVOKESTATIC && owner.equals("net/minecraft/class_1806")
                                        && called.equals("method_8001")
                                        && descriptor.equals("(Lnet/minecraft/class_1799;Lnet/minecraft/class_1937;)Lnet/minecraft/class_22;")) {
                                    matches[0]++;
                                    super.visitInsn(Opcodes.DUP);
                                    super.visitMethodInsn(Opcodes.INVOKESTATIC, "java/util/Objects", "nonNull",
                                            "(Ljava/lang/Object;)Z", false);
                                    super.visitMethodInsn(Opcodes.INVOKESTATIC, "java/lang/Boolean", "toString",
                                            "(Z)Ljava/lang/String;", false);
                                    super.visitLdcInsn("TPRM_MAP_PROBE data_available=");
                                    super.visitInsn(Opcodes.SWAP);
                                    super.visitMethodInsn(Opcodes.INVOKEVIRTUAL, "java/lang/String", "concat",
                                            "(Ljava/lang/String;)Ljava/lang/String;", false);
                                    super.visitLdcInsn(" id=");
                                    super.visitMethodInsn(Opcodes.INVOKEVIRTUAL, "java/lang/String", "concat",
                                            "(Ljava/lang/String;)Ljava/lang/String;", false);
                                    super.visitVarInsn(Opcodes.ALOAD, 7);
                                    super.visitMethodInsn(Opcodes.INVOKESTATIC, "java/lang/String", "valueOf",
                                            "(Ljava/lang/Object;)Ljava/lang/String;", false);
                                    super.visitMethodInsn(Opcodes.INVOKEVIRTUAL, "java/lang/String", "concat",
                                            "(Ljava/lang/String;)Ljava/lang/String;", false);
                                    super.visitFieldInsn(Opcodes.GETSTATIC, "java/lang/System", "out", "Ljava/io/PrintStream;");
                                    super.visitInsn(Opcodes.SWAP);
                                    super.visitMethodInsn(Opcodes.INVOKEVIRTUAL, "java/io/PrintStream", "println",
                                            "(Ljava/lang/String;)V", false);
                                }
                            }
                        };
                    }
                }, 0);
                if (matches[0] != 1) throw new IllegalStateException("Unexpected map lookup count: " + matches[0]);
                System.out.println("TPRM_MAP_PROBE transformed_readable_map_surface lookup_count=" + matches[0]);
                return writer.toByteArray();
            }
        });
        System.out.println("TPRM_MAP_PROBE agent_started");
    }
}
