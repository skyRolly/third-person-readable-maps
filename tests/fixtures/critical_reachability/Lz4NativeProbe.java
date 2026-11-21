import java.io.ByteArrayInputStream;
import java.io.File;
import net.jpountz.lz4.LZ4BlockInputStream;
import net.jpountz.util.Native;

public class Lz4NativeProbe {
    public static void main(String[] args) throws Exception {
        System.out.println("JAVA_TMPDIR_PRIVATE="
                + (args[0].equals(System.getProperty("java.io.tmpdir")) ? 1 : 0));
        String[] nativePath = System.getProperty("java.library.path", "").split(File.pathSeparator);
        System.out.println("NATIVE_LIBRARY_PATH_ISOLATED="
                + (nativePath.length == 1 && new File(nativePath[0]).isDirectory()
                        && new File(nativePath[0]).list().length == 0 ? 1 : 0));
        System.out.println("NATIVE_LOADED_BEFORE=" + (Native.isLoaded() ? 1 : 0));
        try (LZ4BlockInputStream stream = new LZ4BlockInputStream(new ByteArrayInputStream(new byte[0]))) {
            // Construction selects the same fastestInstance path as RegionFileVersion.
        }
        System.out.println("NATIVE_LOADED_AFTER=" + (Native.isLoaded() ? 1 : 0));
        String[] files = new File(args[0]).list();
        int lockFiles = 0;
        int prefixedFiles = 0;
        if (files != null) {
            for (String file : files) {
                if (file.endsWith(".lck")) {
                    lockFiles++;
                }
                if (file.startsWith("liblz4-java-")) {
                    prefixedFiles++;
                }
            }
        }
        System.out.println("TEMP_LOCK_FILES=" + lockFiles);
        System.out.println("TEMP_PREFIX_FILES=" + prefixedFiles);
    }
}
