import java.io.InputStream;
import java.net.URL;
import java.net.URLClassLoader;
import java.nio.file.Files;
import java.nio.file.Path;
import java.security.MessageDigest;
import java.util.Arrays;
import java.util.HexFormat;

/** Isolated, non-initializing class-load control. No channel or frame traffic. */
public class SpdyClassProbe {
    private static final String TARGET = "io.netty.handler.codec.spdy.SpdyFrameCodec";

    private static String digest(InputStream stream) throws Exception {
        try (stream) {
            MessageDigest hash = MessageDigest.getInstance("SHA-256");
            byte[] buffer = new byte[8192];
            for (int n; (n = stream.read(buffer)) != -1;) {
                hash.update(buffer, 0, n);
            }
            return HexFormat.of().formatHex(hash.digest());
        }
    }

    private static void require(boolean condition, String message) {
        if (!condition) throw new IllegalStateException(message);
    }

    public static void main(String[] args) throws Exception {
        require(args.length >= 3, "expected HTTP JAR, JAR hash, class hash, optional dependencies");
        Path http = Path.of(args[0]).toRealPath();
        String jarHash = digest(Files.newInputStream(http));
        require(jarHash.equals(args[1]), "HTTP JAR digest mismatch");
        URL[] urls = new URL[args.length - 2];
        urls[0] = http.toUri().toURL();
        for (int i = 3; i < args.length; i++) {
            Path dependency = Path.of(args[i]).toRealPath();
            require(!dependency.equals(http), "HTTP JAR duplicated in dependencies");
            urls[i - 2] = dependency.toUri().toURL();
        }
        ClassLoader parent = ClassLoader.getPlatformClassLoader();
        // Excluding HTTP must actually make the target unavailable.
        try (URLClassLoader negative = new URLClassLoader(Arrays.copyOfRange(urls, 1, urls.length), parent)) {
            try {
                Class.forName(TARGET, false, negative);
                throw new IllegalStateException("negative control unexpectedly loaded target");
            } catch (ClassNotFoundException expected) {
                // Only absence of the requested class is accepted, not linkage failure.
            }
        }
        try (URLClassLoader positive = new URLClassLoader(urls, parent)) {
            Class<?> type = Class.forName(TARGET, false, positive);
            require(type.getClassLoader() == positive, "unexpected defining loader");
            Path source = Path.of(type.getProtectionDomain().getCodeSource().getLocation().toURI()).toRealPath();
            require(source.equals(http), "unexpected class code source");
            require(digest(Files.newInputStream(source)).equals(jarHash), "class code source changed");
            InputStream resource = type.getResourceAsStream("SpdyFrameCodec.class");
            require(resource != null, "class resource unavailable");
            String classHash = digest(resource);
            require(classHash.equals(args[2]), "class resource digest mismatch");
            System.out.println("negative=class_not_found");
            System.out.println("positive=defined_by_isolated_url_loader");
            System.out.println("code_source_sha256=" + jarHash);
            System.out.println("class_resource_sha256=" + classHash);
        }
    }
}
