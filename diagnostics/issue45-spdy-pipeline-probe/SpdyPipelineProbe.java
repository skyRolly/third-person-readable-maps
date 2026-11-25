import java.io.InputStream;
import java.lang.reflect.Array;
import java.net.URL;
import java.net.URLClassLoader;
import java.nio.file.Files;
import java.nio.file.Path;
import java.security.MessageDigest;
import java.util.Arrays;
import java.util.HexFormat;

/** Local embedded-channel identity check. No frame reads/writes or sockets. */
public class SpdyPipelineProbe {
    private static final String TARGET = "io.netty.handler.codec.spdy.SpdyFrameCodec";

    private static void require(boolean value, String message) {
        if (!value) throw new IllegalStateException(message);
    }

    private static String digest(InputStream input) throws Exception {
        try (input) {
            MessageDigest hash = MessageDigest.getInstance("SHA-256");
            byte[] buffer = new byte[8192];
            for (int n; (n = input.read(buffer)) != -1;) hash.update(buffer, 0, n);
            return HexFormat.of().formatHex(hash.digest());
        }
    }

    private static void identity(Class<?> type, URLClassLoader loader, Path jar, String hash) throws Exception {
        require(type.getClassLoader() == loader, "unexpected defining loader: " + type.getName());
        Path source = Path.of(type.getProtectionDomain().getCodeSource().getLocation().toURI()).toRealPath();
        require(source.equals(jar), "unexpected code source: " + type.getName());
        require(digest(Files.newInputStream(source)).equals(hash), "code-source digest mismatch");
    }

    public static void main(String[] args) throws Exception {
        require(args.length >= 5, "expected HTTP JAR/hash/class hash, transport JAR/hash, dependencies");
        Path http = Path.of(args[0]).toRealPath();
        Path transport = Path.of(args[3]).toRealPath();
        URL[] urls = new URL[args.length - 3];
        urls[0] = http.toUri().toURL();
        urls[1] = transport.toUri().toURL();
        require(!http.equals(transport), "duplicate primary JAR");
        for (int i = 5; i < args.length; i++) {
            Path other = Path.of(args[i]).toRealPath();
            require(!other.equals(http) && !other.equals(transport), "duplicate primary JAR");
            urls[i - 3] = other.toUri().toURL();
        }
        ClassLoader parent = ClassLoader.getPlatformClassLoader();
        try (URLClassLoader negative = new URLClassLoader(Arrays.copyOfRange(urls, 1, urls.length), parent)) {
            try {
                Class.forName(TARGET, false, negative);
                throw new IllegalStateException("HTTP-excluded loader unexpectedly defined target");
            } catch (ClassNotFoundException expected) {
                // Deliberately restricted control, not actual game reachability.
            }
        }
        String pipelineName;
        try (URLClassLoader loader = new URLClassLoader(urls, parent)) {
            Class<?> codec = Class.forName(TARGET, false, loader);
            identity(codec, loader, http, args[1]);
            InputStream resource = codec.getResourceAsStream("SpdyFrameCodec.class");
            require(resource != null, "class resource unavailable");
            require(digest(resource).equals(args[2]), "class resource digest mismatch");
            Class<?> version = Class.forName("io.netty.handler.codec.spdy.SpdyVersion", false, loader);
            identity(version, loader, http, args[1]);
            Class<?> handler = Class.forName("io.netty.channel.ChannelHandler", false, loader);
            Class<?> channel = Class.forName("io.netty.channel.embedded.EmbeddedChannel", false, loader);
            Class<?> pipeline = Class.forName("io.netty.channel.ChannelPipeline", false, loader);
            identity(channel, loader, transport, args[4]);
            identity(handler, loader, transport, args[4]);
            identity(pipeline, loader, transport, args[4]);
            Object instance = codec.getConstructor(version).newInstance(version.getField("SPDY_3_1").get(null));
            require(handler.isInstance(instance), "not a ChannelHandler");
            Object empty = Array.newInstance(handler, 0);
            Object embedded = channel.getConstructor(empty.getClass()).newInstance(empty);
            try {
                Object pipe = channel.getMethod("pipeline").invoke(embedded);
                identity(pipe.getClass(), loader, transport, args[4]);
                pipelineName = pipe.getClass().getName();
                String name = "synthetic-spdy-identity";
                var get = pipeline.getMethod("get", String.class);
                require(get.invoke(pipe, name) == null, "unexpected handler before insertion");
                pipeline.getMethod("addLast", String.class, handler).invoke(pipe, name, instance);
                require(get.invoke(pipe, name) == instance, "registered handler identity mismatch");
                require(pipeline.getMethod("remove", String.class).invoke(pipe, name) == instance,
                        "removed handler identity mismatch");
                require(get.invoke(pipe, name) == null, "handler retained after removal");
                // No writeInbound/writeOutbound, frame construction, or socket operations.
            } finally {
                require(Boolean.FALSE.equals(channel.getMethod("finishAndReleaseAll").invoke(embedded)),
                        "unexpected queued messages during cleanup");
            }
        }
        System.out.println("negative=class_not_found");
        System.out.println("handler=" + TARGET);
        System.out.println("channel=io.netty.channel.embedded.EmbeddedChannel");
        System.out.println("pipeline=" + pipelineName);
        System.out.println("registration=identity_matched_and_removed");
        System.out.println("handler_code_source_sha256=" + args[1]);
        System.out.println("handler_class_resource_sha256=" + args[2]);
        System.out.println("pipeline_code_source_sha256=" + args[4]);
        System.out.println("cleanup=no_queued_messages");
    }
}
