package dev.skyrolly.issue45;

import java.io.File;
import java.lang.instrument.Instrumentation;
import java.lang.reflect.Method;
import java.util.jar.JarFile;

public final class Issue45Agent {
    private Issue45Agent() {}

    public static void premain(String arguments, Instrumentation instrumentation) {
        try {
            File agentJar = new File(Issue45Agent.class.getProtectionDomain()
                    .getCodeSource().getLocation().toURI());
            instrumentation.appendToBootstrapClassLoaderSearch(new JarFile(agentJar));
            Class<?> sink = Class.forName("dev.skyrolly.issue45.EventSink", true, null);
            Method start = sink.getMethod("start", Instrumentation.class, String.class, String.class);
            start.invoke(null, instrumentation, arguments == null ? "" : arguments,
                    agentJar.getAbsolutePath());
            Class<?> installer = Class.forName("dev.skyrolly.issue45.AgentInstaller",
                    true, Issue45Agent.class.getClassLoader());
            installer.getMethod("install", Instrumentation.class, String.class)
                    .invoke(null, instrumentation, agentJar.getAbsolutePath());
        } catch (Throwable error) {
            System.err.println("[issue45-runtime] agent initialization failed: "
                    + error.getClass().getName());
            throw new IllegalStateException("Issue 45 runtime instrumentation failed: "
                    + error.getClass().getName());
        }
    }
}
