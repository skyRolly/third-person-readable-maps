import java.io.ByteArrayInputStream;
import java.lang.reflect.Field;
import java.util.Arrays;
import net.jpountz.lz4.LZ4BlockInputStream;
import net.jpountz.lz4.LZ4Factory;
import net.jpountz.lz4.LZ4FastDecompressor;
import net.jpountz.lz4.LZ4SafeDecompressor;
import net.jpountz.util.Native;

/**
 * Bounded local regression probe for GHSA-cmp6-m4wj-q63q.
 *
 * The input vector is ported from the upstream copyBeyondOutput test added in
 * lz4-java commit 33d180cb70c4d93c80fb0dc3ab3002f457e93840. This does not
 * attempt a Minecraft world-file exploit or exercise untrusted network input.
 */
public final class Lz4AdvisoryProbe {
    private static byte[] sample(int dec, int len) {
        return new byte[] {
            (byte) 0xe0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
            (byte) len, (byte) dec, 0,
            (byte) 0xc0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0
        };
    }

    private static int runFast(LZ4FastDecompressor decompressor) {
        int nonzero = 0;
        int exceptions = 0;
        int cases = 0;
        for (int dec = 0; dec < 14; dec++) {
            for (int len = dec; len < 14; len++) {
                byte[] output = new byte[14 + 4 + len + 4 + 12];
                Arrays.fill(output, (byte) 0x77);
                try {
                    decompressor.decompress(sample(dec, len), output);
                    for (byte value : output) {
                        if (value != 0) nonzero++;
                    }
                    cases++;
                } catch (Throwable ignored) {
                    exceptions++;
                }
            }
        }
        System.out.println("FAST_CASES=" + cases);
        System.out.println("FAST_EXCEPTIONS=" + exceptions);
        System.out.println("FAST_NONZERO_OUTPUT_BYTES=" + nonzero);
        return nonzero;
    }

    private static int runSafe(LZ4SafeDecompressor decompressor) {
        int nonzero = 0;
        int exceptions = 0;
        int cases = 0;
        for (int dec = 0; dec < 14; dec++) {
            for (int len = dec; len < 14; len++) {
                byte[] output = new byte[14 + 4 + len + 4 + 12];
                Arrays.fill(output, (byte) 0x77);
                try {
                    decompressor.decompress(sample(dec, len), output);
                    for (byte value : output) {
                        if (value != 0) nonzero++;
                    }
                    cases++;
                } catch (Throwable ignored) {
                    exceptions++;
                }
            }
        }
        System.out.println("SAFE_CASES=" + cases);
        System.out.println("SAFE_EXCEPTIONS=" + exceptions);
        System.out.println("SAFE_NONZERO_OUTPUT_BYTES=" + nonzero);
        return nonzero;
    }

    private static Object field(Object target, String... names) throws Exception {
        for (String name : names) {
            try {
                Field field = target.getClass().getDeclaredField(name);
                field.setAccessible(true);
                return field.get(target);
            } catch (NoSuchFieldException ignored) {
                // Field names changed when the fork began storing both decompressor APIs.
            }
        }
        throw new NoSuchFieldException(String.join(" or ", names));
    }

    private static int streamIsolation() throws Exception {
        try (LZ4BlockInputStream first = new LZ4BlockInputStream(new ByteArrayInputStream(new byte[0]));
             LZ4BlockInputStream second = new LZ4BlockInputStream(new ByteArrayInputStream(new byte[0]))) {
            Object firstBuffer = field(first, "buffer");
            Object secondBuffer = field(second, "buffer");
            Object firstCompressedBuffer = field(first, "compressedBuffer");
            Object secondCompressedBuffer = field(second, "compressedBuffer");
            Object firstDecompressor = field(first, "decompressor", "fastDecompressor");
            System.out.println("STREAM_DECOMPRESSOR_CLASS=" + firstDecompressor.getClass().getName());
            return firstBuffer != null && secondBuffer != null && firstBuffer != secondBuffer &&
                    firstCompressedBuffer != null && secondCompressedBuffer != null &&
                    firstCompressedBuffer != secondCompressedBuffer ? 1 : 0;
        }
    }

    public static void main(String[] args) throws Exception {
        LZ4Factory fastest = LZ4Factory.fastestInstance();
        LZ4Factory safe = LZ4Factory.safeInstance();
        LZ4Factory javaOnly = LZ4Factory.fastestJavaInstance();
        System.out.println("NATIVE_LOADED_AFTER=" + (Native.isLoaded() ? 1 : 0));
        System.out.println("FASTEST_FAST_CLASS=" + fastest.fastDecompressor().getClass().getName());
        System.out.println("SAFE_FAST_CLASS=" + safe.fastDecompressor().getClass().getName());
        System.out.println("JAVA_ONLY_FAST_CLASS=" + javaOnly.fastDecompressor().getClass().getName());
        int fastestFast = runFast(fastest.fastDecompressor());
        int safeFast = runFast(safe.fastDecompressor());
        int javaOnlyFast = runFast(javaOnly.fastDecompressor());
        runSafe(fastest.safeDecompressor());
        runSafe(safe.safeDecompressor());
        runSafe(javaOnly.safeDecompressor());
        System.out.println("FASTEST_FAST_NONZERO_OUTPUT_BYTES=" + fastestFast);
        System.out.println("SAFE_FAST_NONZERO_OUTPUT_BYTES=" + safeFast);
        System.out.println("JAVA_ONLY_FAST_NONZERO_OUTPUT_BYTES=" + javaOnlyFast);
        System.out.println("STREAM_BUFFERS_DISTINCT=" + streamIsolation());
    }
}
