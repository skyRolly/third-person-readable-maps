package dev.skyrolly.issue45;

import net.bytebuddy.asm.Advice;

public final class ChannelCreatedAdvice {
    private ChannelCreatedAdvice() {}

    @Advice.OnMethodExit(suppress = Throwable.class)
    public static void exit(@Advice.This Object channel) {
        EventSink.channelCreated(channel);
    }
}
