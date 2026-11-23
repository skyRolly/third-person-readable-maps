package dev.skyrolly.issue45;

import java.io.BufferedWriter;
import java.io.File;
import java.io.IOException;
import java.io.OutputStreamWriter;
import java.lang.instrument.Instrumentation;
import java.lang.management.ManagementFactory;
import java.lang.reflect.Field;
import java.lang.reflect.Method;
import java.net.InetAddress;
import java.net.InetSocketAddress;
import java.net.SocketAddress;
import java.net.URI;
import java.net.URL;
import java.net.URLClassLoader;
import java.nio.charset.StandardCharsets;
import java.nio.channels.Channels;
import java.nio.channels.SeekableByteChannel;
import java.nio.file.OpenOption;
import java.nio.file.StandardOpenOption;
import java.nio.file.attribute.AclEntry;
import java.nio.file.attribute.AclEntryPermission;
import java.nio.file.attribute.AclEntryType;
import java.nio.file.attribute.FileAttribute;
import java.nio.file.attribute.PosixFilePermissions;
import java.nio.file.attribute.UserPrincipal;
import java.nio.file.Files;
import java.nio.file.Path;
import java.security.MessageDigest;
import java.security.ProtectionDomain;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Collections;
import java.util.Comparator;
import java.util.Enumeration;
import java.util.EnumSet;
import java.util.HashMap;
import java.util.HashSet;
import java.util.IdentityHashMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Properties;
import java.util.Set;
import java.util.UUID;

public final class EventSink {
    private static final Object LOCK = new Object();
    private static final Set<String> HANDLERS = new HashSet<String>();
    private static final Set<String> CONNECTED_CHANNELS = new HashSet<String>();
    private static final Set<String> ACTIVE_CONNECTED_CHANNELS = new HashSet<String>();
    private static final Map<String, Map<String, Object>> SOURCE_CACHE =
            Collections.synchronizedMap(new HashMap<String, Map<String, Object>>());
    private static final String RUN_ID = UUID.randomUUID().toString();
    private static Instrumentation instrumentation;
    private static BufferedWriter output;
    private static Properties config;
    private static File agentJar;
    private static int transformedPipelineClasses;
    private static int callbackCount;
    private static int connectedSocketCallbackCount;
    private static int activeSnapshotCount;
    private static int channelCreationCount;
    private static boolean failed;

    private EventSink() {}

    public static void start(Instrumentation inst, String args, String agentPath) throws Exception {
        instrumentation = inst;
        agentJar = new File(agentPath);
        File configFile = new File(args);
        config = new Properties();
        try (java.io.Reader reader = Files.newBufferedReader(configFile.toPath(), StandardCharsets.UTF_8)) {
            config.load(reader);
        }
        String outputPath = required("output");
        Path target = new File(outputPath).toPath().toAbsolutePath().normalize();
        Path parent = target.getParent();
        if (parent != null) Files.createDirectories(parent);
        output = openPrivateOutput(target);
        write(event("process_start", processStart()));
        write(event("diagnostic", map("run_id", RUN_ID,
                "diagnostic_agent_sha256", sha256File(agentJar),
                "config_sha256", sha256File(configFile),
                "diagnostic_artifact_verified", true)));
        Runtime.getRuntime().addShutdownHook(new Thread(new Runnable() {
            @Override public void run() { finish(); }
        }, "issue45-runtime-finalizer"));
    }

    private static BufferedWriter openPrivateOutput(Path target) throws Exception {
        // CREATE_NEW prevents replacement of existing evidence or a symlink target.
        Set<OpenOption> options = new HashSet<OpenOption>();
        options.add(StandardOpenOption.CREATE_NEW);
        options.add(StandardOpenOption.WRITE);
        SeekableByteChannel channel;
        if (Files.getFileStore(target.getParent()).supportsFileAttributeView("posix")) {
            channel = Files.newByteChannel(target, options,
                    PosixFilePermissions.asFileAttribute("rw-------"));
        } else if (Files.getFileStore(target.getParent()).supportsFileAttributeView("acl")) {
            UserPrincipal owner = Files.getOwner(target.getParent());
            AclEntry privateEntry = AclEntry.newBuilder().setType(AclEntryType.ALLOW)
                    .setPrincipal(owner).setPermissions(EnumSet.allOf(AclEntryPermission.class)).build();
            final List<AclEntry> entries = Collections.singletonList(privateEntry);
            FileAttribute<List<AclEntry>> privateAcl = new FileAttribute<List<AclEntry>>() {
                @Override public String name() { return "acl:acl"; }
                @Override public List<AclEntry> value() { return entries; }
            };
            channel = Files.newByteChannel(target, options, privateAcl);
        } else {
            throw new IOException("output filesystem cannot create owner-only diagnostic evidence");
        }
        return new BufferedWriter(new OutputStreamWriter(Channels.newOutputStream(channel),
                StandardCharsets.UTF_8));
    }

    public static void pipelineClassTransformed(String name, ClassLoader loader) {
        synchronized (LOCK) {
            transformedPipelineClasses++;
            writeQuietly(event("pipeline_class_transformed", map("class", name,
                    "class_loader", loaderName(loader))));
        }
    }

    public static void transformError(String name, String errorType) {
        synchronized (LOCK) {
            failed = true;
            writeQuietly(event("pipeline_transform_error", map("class", name,
                    "error_type", errorType)));
        }
    }

    public static void pipelineCallback(String method, Object context) {
        try {
            Object handler = invoke(context, "handler");
            Object channel = invoke(context, "channel");
            String handlerName = sanitizeHandlerName(String.valueOf(invoke(context, "name")));
            int channelIdentity = System.identityHashCode(channel);
            String channelFingerprint = channelFingerprint(channel);
            String handlerClass = handler.getClass().getName();
            String peer = peerCategory(channel);
            String eventType = method.equals("callHandlerAdded0")
                    ? "handler_added" : "handler_removed";
            synchronized (LOCK) {
                callbackCount++;
                HANDLERS.add(handlerClass);
                Map<String, Object> details = map("channel_fingerprint", channelFingerprint,
                        "channel_identity", channelIdentity,
                        "channel_type", channel.getClass().getName(),
                        "channel_loader", loaderName(channel.getClass().getClassLoader()),
                        "handler_name", handlerName,
                        "handler_class", handlerClass,
                        "handler_code_source", codeSource(handler.getClass()),
                        "channel_locality", locality(channel, "localAddress"),
                        "channel_peer_category", peer,
                        "handler_limit_fields", limitFields(handler),
                        "pipeline_installation_context", callContext());
                if (peer.equals("loopback") || peer.equals("private_or_link_local")
                        || peer.equals("non_local_inet_peer_address_present")) {
                    connectedSocketCallbackCount++;
                    CONNECTED_CHANNELS.add(channelFingerprint);
                }
                writeQuietly(event(eventType, details));
            }
        } catch (Throwable error) {
            synchronized (LOCK) {
                failed = true;
                writeQuietly(event("pipeline_observation_error", map(
                        "error_type", error.getClass().getName())));
            }
        }
    }

    public static void channelActive(Object context) {
        try {
            Object channel = invoke(context, "channel");
            Object pipeline = invoke(channel, "pipeline");
            @SuppressWarnings("unchecked")
            List<String> names = (List<String>) invoke(pipeline, "names");
            List<Map<String, Object>> handlers = new ArrayList<Map<String, Object>>();
            for (String name : names) {
                Object handler = invoke(pipeline, "get", name);
                if (handler == null) continue;
                handlers.add(map("handler_name", sanitizeHandlerName(name),
                        "handler_class", handler.getClass().getName(),
                        "handler_code_source", codeSource(handler.getClass()),
                        "handler_limit_fields", limitFields(handler)));
            }
            String peer = peerCategory(channel);
            String fingerprint = channelFingerprint(channel);
            synchronized (LOCK) {
                activeSnapshotCount++;
                if (peer.equals("loopback") || peer.equals("private_or_link_local")
                        || peer.equals("non_local_inet_peer_address_present")) {
                    ACTIVE_CONNECTED_CHANNELS.add(fingerprint);
                    CONNECTED_CHANNELS.add(fingerprint);
                }
                writeQuietly(event("channel_active_pipeline_snapshot", map(
                        "channel_fingerprint", fingerprint,
                        "channel_type", channel.getClass().getName(),
                        "channel_loader", loaderName(channel.getClass().getClassLoader()),
                        "channel_locality", locality(channel, "localAddress"),
                        "channel_peer_category", peer,
                        "pipeline_handlers", handlers,
                        "pipeline_mutation_context", callContext())));
            }
        } catch (Throwable error) {
            synchronized (LOCK) {
                failed = true;
                writeQuietly(event("pipeline_observation_error", map(
                        "error_type", error.getClass().getName())));
            }
        }
    }

    public static void channelCreated(Object channel) {
        try {
            String peer = peerCategory(channel);
            String fingerprint = channelFingerprint(channel);
            synchronized (LOCK) {
                channelCreationCount++;
                writeQuietly(event("channel_created", map(
                        "channel_fingerprint", fingerprint,
                        "channel_type", channel.getClass().getName(),
                        "channel_loader", loaderName(channel.getClass().getClassLoader()),
                        "channel_code_source", codeSource(channel.getClass()),
                        "initial_locality", locality(channel, "localAddress"),
                        "initial_peer_category", peer,
                        "channel_creation_context", callContext())));
            }
        } catch (Throwable error) {
            synchronized (LOCK) {
                failed = true;
                writeQuietly(event("pipeline_observation_error", map(
                        "error_type", error.getClass().getName())));
            }
        }
    }

    private static Map<String, Object> processStart() {
        Map<String, Object> process = map(
                "run_id", RUN_ID,
                "minecraft_version", config.getProperty("minecraftVersion", ""),
                "distribution", config.getProperty("distribution", ""),
                "launcher", config.getProperty("launcher", ""),
                "fabric_loader_version", config.getProperty("fabricLoaderVersion", ""),
                "source_sha", config.getProperty("sourceSha", ""),
                "product_jar", configuredArtifact(config.getProperty("productJar")),
                "java_executable", sanitizePath(System.getProperty("java.home") + File.separator
                        + "bin" + File.separator + (isWindows() ? "java.exe" : "java")),
                "java_executable_sha256", javaExecutableSha256(),
                "java_version", System.getProperty("java.version", ""),
                "java_vendor", System.getProperty("java.vendor", ""),
                "os_name", System.getProperty("os.name", ""),
                "os_version", System.getProperty("os.version", ""),
                "architecture", System.getProperty("os.arch", ""),
                "java_main_class", mainClass(),
                "java_main_class_loaded", mainClassLoaded(),
                "jvm_arguments_sanitized", sanitizedJvmArgs(),
                "effective_classpath_sanitized", classpath(),
                "additional_java_agents", javaAgents(),
                "mods_directory_jars", modsDirectoryJars(),
                "networking_properties", safeNetworkingProperties(),
                "environment_variables_collected", false,
                "process_command_collected", false,
                "run_outcome", "running");
        return process;
    }

    private static void finish() {
        synchronized (LOCK) {
            try {
                List<Map<String, Object>> allLoaded = loadedNettyClasses();
                List<Map<String, Object>> relevantLoaded = relevantNettyClasses(allLoaded);
                Map<String, Object> end = map("run_id", RUN_ID,
                        "run_outcome", failed ? "diagnostic_incomplete" : "shutdown_hook_executed",
                        "jvm_shutdown_hook_executed", true,
                        "jvm_exit_status", "not_available_from_shutdown_hook",
                        "pipeline_class_transformed_count", transformedPipelineClasses,
                        "pipeline_callback_count", callbackCount,
                        "connected_socket_pipeline_callback_count", connectedSocketCallbackCount,
                        "channel_creation_event_count", channelCreationCount,
                        "channel_creation_hook_execution_confirmed", channelCreationCount > 0,
                        "connected_socket_channel_fingerprints", sorted(CONNECTED_CHANNELS),
                        "channel_active_pipeline_snapshot_count", activeSnapshotCount,
                        "active_socket_channel_fingerprints", sorted(ACTIVE_CONNECTED_CHANNELS),
                        "channel_active_hook_execution_confirmed", activeSnapshotCount > 0,
                        "pipeline_hook_execution_confirmed", transformedPipelineClasses > 0
                                && callbackCount > 0 && !failed,
                        "handler_classes_observed", sorted(HANDLERS),
                        "loaded_netty_class_count", allLoaded.size(),
                        "loaded_netty_classes", relevantLoaded,
                        "loaded_lz4_decoder_class_count", countName(relevantLoaded,
                                "io.netty.handler.codec.compression.Lz4FrameDecoder"),
                        "loaded_netty_artifacts", artifactGroups(allLoaded),
                        "loaded_fabric_loader_classes", loadedFabricClasses(),
                        "loaded_code_source_groups", loadedCodeSourceGroups(),
                        "loader_netty_artifacts", loaderNettyArtifacts(),
                        "agent_errors", failed ? "one_or_more_observation_errors" : "none");
                write(event("process_end", end));
                if (output != null) output.close();
            } catch (Throwable error) {
                System.err.println("[issue45-runtime] final evidence write failed: "
                        + error.getClass().getName());
            }
        }
    }

    private static int countName(List<Map<String, Object>> values, String name) {
        for (Map<String, Object> value : values) if (name.equals(value.get("class"))) return 1;
        return 0;
    }

    private static List<Map<String, Object>> loadedNettyClasses() {
        List<Map<String, Object>> values = new ArrayList<Map<String, Object>>();
        for (Class<?> type : instrumentation.getAllLoadedClasses()) {
            if (!type.getName().startsWith("io.netty.")) continue;
            Map<String, Object> entry = map("class", type.getName(),
                    "class_loader", loaderName(type.getClassLoader()),
                    "package_version", type.getPackage() == null ? ""
                            : nullToEmpty(type.getPackage().getImplementationVersion()),
                    "code_source", codeSource(type));
            values.add(entry);
        }
        Collections.sort(values, new Comparator<Map<String, Object>>() {
            @Override public int compare(Map<String, Object> a, Map<String, Object> b) {
                return String.valueOf(a.get("class")).compareTo(String.valueOf(b.get("class")));
            }
        });
        return values;
    }

    private static List<Map<String, Object>> loadedFabricClasses() {
        List<Map<String, Object>> values = new ArrayList<Map<String, Object>>();
        for (Class<?> type : instrumentation.getAllLoadedClasses()) {
            if (!(type.getName().startsWith("net.fabricmc.loader.")
                    || type.getName().equals("net.fabricmc.api.ModInitializer"))) continue;
            values.add(map("class", type.getName(),
                    "package_version", type.getPackage() == null ? ""
                            : nullToEmpty(type.getPackage().getImplementationVersion()),
                    "code_source", codeSource(type)));
        }
        Collections.sort(values, new Comparator<Map<String, Object>>() {
            @Override public int compare(Map<String, Object> a, Map<String, Object> b) {
                return String.valueOf(a.get("class")).compareTo(String.valueOf(b.get("class")));
            }
        });
        return values;
    }

    private static List<Map<String, Object>> loadedCodeSourceGroups() {
        Map<String, Map<String, Object>> groups = new LinkedHashMap<String, Map<String, Object>>();
        for (Class<?> type : instrumentation.getAllLoadedClasses()) {
            try {
                File file = codeSourceFile(type);
                if (file == null || !file.isFile()) continue;
                String path = file.getCanonicalPath();
                Map<String, Object> group = groups.get(path);
                if (group == null) {
                    group = map("artifact", file.getName(), "path_redacted", sanitizePath(file.getAbsolutePath()),
                            "size_bytes", file.length(), "loaded_class_count", 0,
                            "sha1", "", "sha256", "", "hash_verified", false,
                            "example_loaded_classes", new HashSet<String>(),
                            "class_loaders", new HashSet<String>());
                    groups.put(path, group);
                }
                group.put("loaded_class_count", ((Number) group.get("loaded_class_count")).intValue() + 1);
                @SuppressWarnings("unchecked") Set<String> examples = (Set<String>) group.get("example_loaded_classes");
                String name = type.getName();
                boolean relevant = name.startsWith("io.netty.") || name.startsWith("net.minecraft.")
                        || name.startsWith("net.fabricmc.") || HANDLERS.contains(name);
                if (relevant) {
                    if (examples.size() < 16) examples.add(name);
                    Map<String, Object> identity = codeSource(type);
                    if (Boolean.TRUE.equals(identity.get("hash_verified"))) {
                        group.put("sha256", identity.get("sha256"));
                        group.put("sha1", identity.get("sha1"));
                        group.put("hash_verified", true);
                    }
                }
                @SuppressWarnings("unchecked") Set<String> loaders = (Set<String>) group.get("class_loaders");
                loaders.add(loaderName(type.getClassLoader()));
            } catch (Throwable ignored) { }
        }
        List<Map<String, Object>> result = new ArrayList<Map<String, Object>>(groups.values());
        Collections.sort(result, new Comparator<Map<String, Object>>() {
            @Override public int compare(Map<String, Object> a, Map<String, Object> b) {
                return String.valueOf(a.get("artifact")).compareTo(String.valueOf(b.get("artifact")));
            }
        });
        return result;
    }

    private static List<Map<String, Object>> loaderNettyArtifacts() {
        // A server child loader may expose a Netty JAR without using its classes.
        Set<ClassLoader> seen = Collections.newSetFromMap(new IdentityHashMap<ClassLoader, Boolean>());
        Map<String, Map<String, Object>> found = new LinkedHashMap<String, Map<String, Object>>();
        for (Class<?> type : instrumentation.getAllLoadedClasses()) {
            ClassLoader loader = type.getClassLoader();
            if (loader == null || !seen.add(loader) || !(loader instanceof URLClassLoader)) continue;
            for (URL url : ((URLClassLoader) loader).getURLs()) {
                try {
                    if (!"file".equalsIgnoreCase(url.getProtocol())) continue;
                    File file = new File(url.toURI()).getCanonicalFile();
                    String name = file.getName().toLowerCase(java.util.Locale.ROOT);
                    if (!name.startsWith("netty-") || !name.endsWith(".jar")
                            || !file.isFile() || file.length() > 64L * 1024 * 1024) continue;
                    String key = file.getCanonicalPath();
                    if (!found.containsKey(key)) {
                        found.put(key, map("artifact", file.getName(), "path_redacted",
                                sanitizePath(file.getAbsolutePath()), "size_bytes", file.length(),
                                "sha1", sha1File(file), "sha256", sha256File(file),
                                "hash_verified", true, "availability_only", true,
                                "discovered_via", "loaded_class_loader_url"));
                    }
                } catch (Throwable ignored) {
                    // Inaccessible loader URLs are not evidence of module availability.
                }
            }
        }
        List<Map<String, Object>> result = new ArrayList<Map<String, Object>>(found.values());
        Collections.sort(result, new Comparator<Map<String, Object>>() {
            @Override public int compare(Map<String, Object> a, Map<String, Object> b) {
                return String.valueOf(a.get("artifact")).compareTo(String.valueOf(b.get("artifact")));
            }
        });
        return result;
    }

    private static List<Map<String, Object>> javaAgents() {
        List<Map<String, Object>> result = new ArrayList<Map<String, Object>>();
        for (String arg : ManagementFactory.getRuntimeMXBean().getInputArguments()) {
            if (!(arg.startsWith("-javaagent:") || arg.startsWith("-agentpath:"))) continue;
            String value = arg.substring(arg.indexOf(':') + 1);
            int equals = value.indexOf('=');
            String path = equals < 0 ? value : value.substring(0, equals);
            File file = new File(path);
            try {
                result.add(map("agent_type", arg.startsWith("-javaagent:") ? "javaagent" : "native_agent",
                        "artifact", file.getName(), "path_redacted", sanitizePath(file.getAbsolutePath()),
                        "sha256", file.isFile() ? sha256File(file) : "",
                        "hash_verified", file.isFile()));
            } catch (Throwable error) {
                result.add(map("agent_type", arg.startsWith("-javaagent:") ? "javaagent" : "native_agent",
                        "artifact", file.getName(), "hash_verified", false,
                        "error_type", error.getClass().getName()));
            }
        }
        return result;
    }

    private static List<Map<String, Object>> modsDirectoryJars() {
        String value = config.getProperty("modsDirectory", "").trim();
        if (value.isEmpty()) return Collections.emptyList();
        File directory = new File(value);
        if (!directory.isDirectory()) return Collections.emptyList();
        File[] files = directory.listFiles();
        List<Map<String, Object>> result = new ArrayList<Map<String, Object>>();
        if (files == null) return result;
        Arrays.sort(files, new Comparator<File>() {
            @Override public int compare(File a, File b) { return a.getName().compareTo(b.getName()); }
        });
        for (File file : files) {
            if (!file.isFile() || !file.getName().toLowerCase().endsWith(".jar")) continue;
            try { result.add(map("artifact", file.getName(), "size_bytes", file.length(),
                    "sha256", sha256File(file), "hash_verified", true)); }
            catch (Throwable error) { result.add(map("artifact", file.getName(), "hash_verified", false,
                    "error_type", error.getClass().getName())); }
        }
        return result;
    }

    private static List<Map<String, Object>> relevantNettyClasses(List<Map<String, Object>> classes) {
        List<Map<String, Object>> result = new ArrayList<Map<String, Object>>();
        for (Map<String, Object> item : classes) {
            String name = String.valueOf(item.get("class"));
            if (name.equals("io.netty.channel.DefaultChannelPipeline")
                    || name.equals("io.netty.channel.ChannelPipeline")
                    || name.equals("io.netty.util.Version")
                    || name.startsWith("io.netty.handler.codec.compression.")) result.add(item);
        }
        return result;
    }

    private static List<Map<String, Object>> artifactGroups(List<Map<String, Object>> classes) {
        Map<String, Map<String, Object>> groups = new LinkedHashMap<String, Map<String, Object>>();
        for (Map<String, Object> item : classes) {
            Object src = item.get("code_source");
            if (!(src instanceof Map)) continue;
            Map<?, ?> source = (Map<?, ?>) src;
            String key = String.valueOf(source.get("sha256"));
            if (!key.matches("[0-9a-f]{64}")) continue;
            Map<String, Object> group = groups.get(key);
            if (group == null) {
                group = map("sha1", source.get("sha1"), "sha256", key, "artifact", source.get("artifact"),
                        "path_redacted", source.get("path_redacted"),
                        "size_bytes", source.get("size_bytes"),
                        "hash_verified", Boolean.TRUE.equals(source.get("hash_verified")),
                        "loaded_class_count", 0, "package_versions", new HashSet<String>(),
                        "relevant_loaded_classes", new HashSet<String>());
                groups.put(key, group);
            }
            group.put("loaded_class_count", ((Number) group.get("loaded_class_count")).intValue() + 1);
            @SuppressWarnings("unchecked") Set<String> versions = (Set<String>) group.get("package_versions");
            versions.add(String.valueOf(item.get("package_version")));
            String name = String.valueOf(item.get("class"));
            if (name.startsWith("io.netty.handler.codec.compression.")
                    || name.equals("io.netty.channel.DefaultChannelPipeline")
                    || name.equals("io.netty.channel.ChannelPipeline")
                    || name.equals("io.netty.util.Version")) {
                @SuppressWarnings("unchecked") Set<String> relevant = (Set<String>) group.get("relevant_loaded_classes");
                relevant.add(name);
            }
        }
        List<Map<String, Object>> result = new ArrayList<Map<String, Object>>(groups.values());
        Collections.sort(result, new Comparator<Map<String, Object>>() {
            @Override public int compare(Map<String, Object> a, Map<String, Object> b) {
                return String.valueOf(a.get("artifact")).compareTo(String.valueOf(b.get("artifact")));
            }
        });
        return result;
    }

    private static Map<String, Object> codeSource(Class<?> type) {
        try {
            File file = codeSourceFile(type);
            if (file == null) return map("status", "no_code_source");
            if (file.isFile()) {
                String key = file.getCanonicalPath();
                Map<String, Object> cached = SOURCE_CACHE.get(key);
                if (cached != null) return cached;
                Map<String, Object> identity = map("status", "hashed", "artifact", file.getName(),
                        "path_redacted", sanitizePath(file.getAbsolutePath()),
                        "size_bytes", file.length(), "sha1", sha1File(file), "sha256", sha256File(file),
                        "hash_verified", true);
                SOURCE_CACHE.put(key, identity);
                return identity;
            }
            return map("status", "directory", "artifact", file.getName(),
                    "path_redacted", sanitizePath(file.getAbsolutePath()),
                    "hash_verified", false);
        } catch (Throwable error) {
            return map("status", "hash_error", "error_type", error.getClass().getName());
        }
    }

    private static File codeSourceFile(Class<?> type) throws Exception {
        ProtectionDomain pd = type.getProtectionDomain();
        if (pd == null || pd.getCodeSource() == null || pd.getCodeSource().getLocation() == null) return null;
        URI uri = pd.getCodeSource().getLocation().toURI();
        return new File(uri);
    }

    private static Map<String, Object> configuredArtifact(String path) {
        if (path == null || path.trim().isEmpty()) return map("status", "not_configured");
        try {
            File file = new File(path);
            return map("status", file.isFile() ? "hashed" : "missing",
                    "artifact", file.getName(), "path_redacted", sanitizePath(file.getAbsolutePath()),
                    "size_bytes", file.isFile() ? file.length() : 0,
                    "sha256", file.isFile() ? sha256File(file) : "",
                    "hash_verified", file.isFile());
        } catch (Throwable error) {
            return map("status", "hash_error", "error_type", error.getClass().getName());
        }
    }

    private static String javaExecutableSha256() {
        File executable = new File(System.getProperty("java.home") + File.separator + "bin"
                + File.separator + (isWindows() ? "java.exe" : "java"));
        try { return executable.isFile() ? sha256File(executable) : ""; }
        catch (Throwable ignored) { return ""; }
    }

    private static List<Map<String, Object>> classpath() {
        List<Map<String, Object>> result = new ArrayList<Map<String, Object>>();
        String cp = System.getProperty("java.class.path", "");
        for (String item : cp.split(java.util.regex.Pattern.quote(File.pathSeparator))) {
            if (item.trim().isEmpty()) continue;
            File path = new File(item);
            boolean hashNetty = path.isFile() && path.getName().toLowerCase().startsWith("netty-")
                    && path.getName().toLowerCase().endsWith(".jar");
            try {
                result.add(map("path_redacted", sanitizePath(path.getAbsolutePath()),
                        "kind", path.isFile() ? "file" : path.isDirectory() ? "directory" : "missing",
                        "artifact", path.getName(), "size_bytes", path.isFile() ? path.length() : 0,
                        "sha1", hashNetty ? sha1File(path) : "",
                        "sha256", hashNetty ? sha256File(path) : "",
                        "hash_verified", hashNetty));
            } catch (Throwable error) {
                result.add(map("path_redacted", sanitizePath(path.getAbsolutePath()),
                        "kind", path.isFile() ? "file" : path.isDirectory() ? "directory" : "missing",
                        "artifact", path.getName(), "sha1", "", "sha256", "",
                        "hash_verified", false, "error_type", error.getClass().getName()));
            }
        }
        return result;
    }

    private static List<String> sanitizedJvmArgs() {
        // Values of arbitrary -D properties and unknown JVM flags are never copied.
        // An unfamiliar key such as apiKey must not become a cleartext evidence field.
        List<String> result = new ArrayList<String>();
        for (String arg : ManagementFactory.getRuntimeMXBean().getInputArguments()) {
            if (arg.startsWith("-D")) {
                int equals = arg.indexOf('=', 2);
                int colon = arg.indexOf(':', 2);
                int separator = equals < 0 ? colon : colon < 0 ? equals : Math.min(equals, colon);
                String key = separator < 0 ? arg.substring(2) : arg.substring(2, separator);
                boolean knownMarker = key.matches("(?i)(accessToken|token|password|passwd|session|cookie|authorization|clientSecret|secret|credential|username|uuid|xuid|server|host)");
                String prefix = knownMarker ? "-D" + key : "-D<redacted>";
                result.add(separator < 0 ? prefix : prefix + arg.charAt(separator) + "<redacted>");
            } else if (arg.matches("-Xm[sx][0-9]+[kKmMgG]?")
                    || arg.matches("-XX:[+-](UseG1GC|UseZGC|UseSerialGC|UseParallelGC)")
                    || arg.equals("-ea") || arg.equals("-da")) {
                result.add(arg);
            } else if (arg.startsWith("-javaagent:")) {
                result.add("-javaagent:<redacted>");
            } else if (arg.startsWith("-agentpath:")) {
                result.add("-agentpath:<redacted>");
            } else {
                result.add("<redacted>");
            }
        }
        return result;
    }

    private static String mainClass() {
        String command = System.getProperty("sun.java.command", "").trim();
        if (command.isEmpty()) return "";
        int end = command.indexOf(' ');
        String value = end < 0 ? command : command.substring(0, end);
        if (value.toLowerCase().endsWith(".jar")) value = new File(value).getName();
        return sanitizePath(value.replaceAll("[^A-Za-z0-9_.$/-]", ""));
    }

    private static boolean mainClassLoaded() {
        String main = mainClass();
        if (main.isEmpty() || main.endsWith(".jar")) return false;
        for (Class<?> type : instrumentation.getAllLoadedClasses()) {
            if (type.getName().equals(main)) return true;
        }
        return false;
    }

    private static boolean sensitiveKey(String arg) {
        return arg.matches("(?i).*(access[-_]?token|token|password|passwd|session|cookie|authorization|client[-_]?secret|secret|credential|user(?:name)?|uuid|xuid|server|host)([=:].*)?");
    }

    private static Map<String, Object> safeNetworkingProperties() {
        Properties all = System.getProperties();
        Map<String, Object> safe = new TreeMapStringObject();
        Enumeration<?> names = all.propertyNames();
        while (names.hasMoreElements()) {
            String key = String.valueOf(names.nextElement());
            if (!(key.startsWith("io.netty.allocator.")
                    || key.startsWith("io.netty.handler.codec.compression.")
                    || key.equals("networkCompressionThreshold"))) continue;
            String value = all.getProperty(key, "");
            safe.put(key, value.matches("(?i)(true|false|[0-9]{1,12})") ? value : "<redacted>");
        }
        return safe;
    }

    private static String peerCategory(Object channel) {
        try {
            Object address = invoke(channel, "remoteAddress");
            if (!(address instanceof SocketAddress)) return "not_connected";
            if (!(address instanceof InetSocketAddress)) return "non_inet_socket_address";
            InetAddress ip = ((InetSocketAddress) address).getAddress();
            if (ip == null) return "unresolved_inet_address";
            if (ip.isLoopbackAddress()) return "loopback";
            if (ip.isSiteLocalAddress() || ip.isLinkLocalAddress()) return "private_or_link_local";
            return "non_local_inet_peer_address_present";
        } catch (Throwable error) { return "unavailable"; }
    }

    private static String locality(Object channel, String method) {
        try {
            Object address = invoke(channel, method);
            if (!(address instanceof InetSocketAddress)) return address == null ? "unknown" : "non_inet";
            InetAddress ip = ((InetSocketAddress) address).getAddress();
            if (ip == null) return "unresolved";
            if (ip.isLoopbackAddress()) return "loopback";
            if (ip.isSiteLocalAddress() || ip.isLinkLocalAddress()) return "private_or_link_local";
            return "non_local_inet_address";
        } catch (Throwable error) { return "unavailable"; }
    }

    private static Map<String, Object> limitFields(Object handler) {
        Map<String, Object> values = new TreeMapStringObject();
        String handlerType = handler.getClass().getName().toLowerCase();
        if (!(handlerType.contains("compress") || handlerType.contains("decoder"))) return values;
        Class<?> type = handler.getClass();
        for (int depth = 0; type != null && depth < 5; type = type.getSuperclass(), depth++) {
            for (Field field : type.getDeclaredFields()) {
                String name = field.getName().toLowerCase();
                if (!(name.contains("decompress") || name.contains("frame") || name.contains("bufferedbytes")
                        || name.equals("maxoutputlength") || name.equals("maxallocationsize"))) continue;
                if (!(field.getType() == int.class || field.getType() == long.class
                        || field.getType() == Integer.class || field.getType() == Long.class)) continue;
                try {
                    if (!field.trySetAccessible()) {
                        values.put(field.getName(), "inaccessible");
                        continue;
                    }
                    Object value = field.get(handler);
                    if (value instanceof Number) values.put(field.getName(), ((Number) value).longValue());
                } catch (Throwable ignored) { values.put(field.getName(), "inaccessible"); }
            }
        }
        return values;
    }

    private static String sanitizeHandlerName(String name) {
        return name.replaceAll("(?i)(?:[a-z0-9-]+\\.)+[a-z]{2,}", "<address>")
                .replaceAll("\\b(?:[0-9]{1,3}\\.){3}[0-9]{1,3}\\b", "<address>")
                .replaceAll("(?i)(?:[0-9a-f]{0,4}:){2,}[0-9a-f:.]+", "<address>")
                .replaceAll(":\\d{1,5}\\b", ":<port>");
    }

    private static List<String> callContext() {
        List<String> frames = new ArrayList<String>();
        for (StackTraceElement frame : Thread.currentThread().getStackTrace()) {
            String name = frame.getClassName();
            if (name.equals("java.lang.Thread") || name.startsWith("dev.skyrolly.issue45.")
                    || name.startsWith("net.bytebuddy.")) continue;
            frames.add(name + "." + frame.getMethodName());
            if (frames.size() == 24) break;
        }
        return frames;
    }

    private static Object invoke(Object target, String methodName) throws Exception {
        Method method = target.getClass().getMethod(methodName);
        if (!method.trySetAccessible()) {
            throw new IllegalAccessException("method is not accessible: " + methodName);
        }
        return method.invoke(target);
    }

    private static Object invoke(Object target, String methodName, String argument) throws Exception {
        Method method = target.getClass().getMethod(methodName, String.class);
        if (!method.trySetAccessible()) {
            throw new IllegalAccessException("method is not accessible: " + methodName);
        }
        return method.invoke(target, argument);
    }

    private static String safeInvokeString(Object target, String methodName) {
        try {
            Object value = invoke(target, methodName);
            try { return String.valueOf(invoke(value, "asShortText")); }
            catch (Throwable ignored) { return value.getClass().getName(); }
        } catch (Throwable error) { return "unavailable"; }
    }

    private static String channelFingerprint(Object channel) throws Exception {
        return sha256Text(channel.getClass().getName() + ":" + safeInvokeString(channel, "id")
                + ":" + System.identityHashCode(channel));
    }

    private static String loaderName(ClassLoader loader) {
        return loader == null ? "bootstrap" : loader.getClass().getName();
    }

    private static String required(String key) {
        String value = config.getProperty(key);
        if (value == null || value.trim().isEmpty()) throw new IllegalArgumentException("missing " + key);
        return value.trim();
    }

    private static String sanitizePath(String path) {
        String result = path;
        String home = System.getProperty("user.home", "");
        if (!home.isEmpty()) result = result.replace(home, "<HOME>");
        result = result.replaceAll("(?i)(/Users/)[^/]+", "$1<USER>")
                .replaceAll("(?i)(C:\\\\Users\\\\)[^\\\\]+", "$1<USER>")
                .replaceAll("(?i)(access[-_]?token|token|password|passwd|session|cookie|authorization|client[-_]?secret|secret|credential|username|user[-_]?name|uuid|xuid)=([^&/ ,]+)", "$1=<redacted>");
        return result;
    }

    private static String sha256File(File file) throws Exception {
        MessageDigest digest = MessageDigest.getInstance("SHA-256");
        try (java.io.InputStream input = Files.newInputStream(file.toPath())) {
            byte[] buffer = new byte[65536];
            int count;
            while ((count = input.read(buffer)) != -1) digest.update(buffer, 0, count);
        }
        StringBuilder result = new StringBuilder();
        for (byte value : digest.digest()) result.append(String.format("%02x", value & 0xff));
        return result.toString();
    }

    private static String sha1File(File file) throws Exception {
        MessageDigest digest = MessageDigest.getInstance("SHA-1");
        try (java.io.InputStream input = Files.newInputStream(file.toPath())) {
            byte[] buffer = new byte[65536];
            int count;
            while ((count = input.read(buffer)) != -1) digest.update(buffer, 0, count);
        }
        StringBuilder result = new StringBuilder();
        for (byte value : digest.digest()) result.append(String.format("%02x", value & 0xff));
        return result.toString();
    }

    private static String sha256Text(String value) throws Exception {
        MessageDigest digest = MessageDigest.getInstance("SHA-256");
        StringBuilder result = new StringBuilder();
        for (byte item : digest.digest(value.getBytes(StandardCharsets.UTF_8))) {
            result.append(String.format("%02x", item & 0xff));
        }
        return result.toString();
    }

    private static Map<String, Object> event(String type, Map<String, Object> fields) {
        Map<String, Object> value = new LinkedHashMap<String, Object>();
        value.put("schema", "issue45-runtime-observation/v1");
        value.put("run_id", RUN_ID);
        value.put("event", type);
        value.put("timestamp_utc", java.time.Instant.now().toString());
        value.putAll(fields);
        return value;
    }

    private static Map<String, Object> map(Object... pairs) {
        Map<String, Object> result = new LinkedHashMap<String, Object>();
        for (int i = 0; i + 1 < pairs.length; i += 2) result.put(String.valueOf(pairs[i]), pairs[i + 1]);
        return result;
    }

    private static List<String> sorted(Set<String> values) {
        List<String> result = new ArrayList<String>(values);
        Collections.sort(result);
        return result;
    }

    private static void write(Map<String, Object> value) throws Exception {
        synchronized (LOCK) {
            output.write(json(value));
            output.write('\n');
            output.flush();
        }
    }

    private static void writeQuietly(Map<String, Object> value) {
        try { if (output != null) write(value); }
        catch (Throwable error) { failed = true; }
    }

    private static String json(Object value) {
        if (value == null) return "null";
        if (value instanceof String || value instanceof Character) return quote(String.valueOf(value));
        if (value instanceof Number || value instanceof Boolean) return String.valueOf(value);
        if (value instanceof Map) {
            StringBuilder out = new StringBuilder("{");
            boolean first = true;
            for (Object entryObject : ((Map<?, ?>) value).entrySet()) {
                Map.Entry<?, ?> entry = (Map.Entry<?, ?>) entryObject;
                if (!first) out.append(','); first = false;
                out.append(quote(String.valueOf(entry.getKey()))).append(':').append(json(entry.getValue()));
            }
            return out.append('}').toString();
        }
        if (value instanceof Iterable) {
            StringBuilder out = new StringBuilder("["); boolean first = true;
            for (Object item : (Iterable<?>) value) { if (!first) out.append(','); first = false; out.append(json(item)); }
            return out.append(']').toString();
        }
        if (value.getClass().isArray()) return json(Arrays.asList((Object[]) value));
        return quote(String.valueOf(value));
    }

    private static String quote(String value) {
        StringBuilder out = new StringBuilder("\"");
        for (int i = 0; i < value.length(); i++) {
            char c = value.charAt(i);
            if (c == '"') out.append("\\\"");
            else if (c == '\\') out.append("\\\\");
            else if (c == '\n') out.append("\\n");
            else if (c == '\r') out.append("\\r");
            else if (c == '\t') out.append("\\t");
            else if (c < 32) out.append(String.format("\\u%04x", (int) c));
            else out.append(c);
        }
        return out.append('"').toString();
    }

    private static String nullToEmpty(String value) { return value == null ? "" : value; }
    private static boolean isWindows() { return System.getProperty("os.name", "").toLowerCase().contains("win"); }

    private static final class TreeMapStringObject extends java.util.TreeMap<String, Object> {
        private static final long serialVersionUID = 1L;
    }
}
