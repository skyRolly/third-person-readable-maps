package dev.skyrolly.issue45;

import net.bytebuddy.asm.Advice;

public final class PipelineAdvice {
    private PipelineAdvice() {}

    @Advice.OnMethodEnter(suppress = Throwable.class)
    public static void enter(@Advice.Origin("#m") String method,
                             @Advice.Argument(0) Object context) {
        EventSink.pipelineCallback(method, context);
    }
}
