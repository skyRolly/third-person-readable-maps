package dev.skyrolly.issue45;

import net.bytebuddy.asm.Advice;

public final class ChannelActiveAdvice {
    private ChannelActiveAdvice() {}

    @Advice.OnMethodEnter(suppress = Throwable.class)
    public static void enter(@Advice.Argument(0) Object context) {
        EventSink.channelActive(context);
    }
}
