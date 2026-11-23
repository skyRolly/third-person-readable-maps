package dev.skyrolly.issue45;

import java.lang.instrument.Instrumentation;
import java.io.File;
import net.bytebuddy.agent.builder.AgentBuilder;
import net.bytebuddy.asm.Advice;
import net.bytebuddy.dynamic.ClassFileLocator;

import static net.bytebuddy.matcher.ElementMatchers.named;
import static net.bytebuddy.matcher.ElementMatchers.nameStartsWith;
import static net.bytebuddy.matcher.ElementMatchers.isConstructor;

public final class AgentInstaller {
    private static ClassFileLocator locator;
    private AgentInstaller() {}

    public static void install(Instrumentation instrumentation, String agentPath) throws Exception {
        locator = ClassFileLocator.ForJarFile.of(new File(agentPath));
        new AgentBuilder.Default()
                .disableClassFormatChanges()
                .with(AgentBuilder.RedefinitionStrategy.RETRANSFORMATION)
                .with(new AgentBuilder.Listener.Adapter() {
                    @Override
                    public void onTransformation(net.bytebuddy.description.type.TypeDescription type,
                            ClassLoader loader, net.bytebuddy.utility.JavaModule module,
                            boolean loaded, net.bytebuddy.dynamic.DynamicType dynamicType) {
                        EventSink.pipelineClassTransformed(type.getName(), loader);
                    }

                    @Override
                    public void onError(String typeName, ClassLoader loader,
                            net.bytebuddy.utility.JavaModule module, boolean loaded,
                            Throwable throwable) {
                        EventSink.transformError(typeName, throwable.getClass().getName());
                    }
                })
                .ignore(nameStartsWith("net.bytebuddy.").or(nameStartsWith("dev.skyrolly.issue45.")))
                .type(named("io.netty.channel.DefaultChannelPipeline"))
                .transform((builder, type, loader, module, domain) -> builder
                        .visit(Advice.to(PipelineAdvice.class, locator).on(
                                named("callHandlerAdded0").or(named("callHandlerRemoved0")))))
                .type(named("io.netty.channel.DefaultChannelPipeline$HeadContext"))
                .transform((builder, type, loader, module, domain) -> builder
                        .visit(Advice.to(ChannelActiveAdvice.class, locator).on(
                                named("channelActive"))))
                .type(named("io.netty.channel.AbstractChannel"))
                .transform((builder, type, loader, module, domain) -> builder
                        .visit(Advice.to(ChannelCreatedAdvice.class, locator).on(isConstructor())))
                .installOn(instrumentation);
    }
}
