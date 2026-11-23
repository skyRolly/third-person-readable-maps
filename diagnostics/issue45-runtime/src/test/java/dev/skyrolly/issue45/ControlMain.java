package dev.skyrolly.issue45;

import io.netty.channel.ChannelInboundHandlerAdapter;
import io.netty.channel.embedded.EmbeddedChannel;
import io.netty.handler.codec.compression.JdkZlibDecoder;
import io.netty.handler.codec.compression.Lz4FrameDecoder;
import io.netty.handler.codec.compression.ZlibWrapper;

public final class ControlMain {
    private ControlMain() {}

    public static void main(String[] args) {
        EmbeddedChannel lz4 = new EmbeddedChannel();
        lz4.pipeline().addLast("control-lz4", new Lz4FrameDecoder());
        EmbeddedChannel zlib = new EmbeddedChannel();
        zlib.pipeline().addLast("control-zlib", new JdkZlibDecoder(ZlibWrapper.ZLIB));
        EmbeddedChannel plain = new EmbeddedChannel();
        plain.pipeline().addLast("control-plain", new ChannelInboundHandlerAdapter());
        lz4.finishAndReleaseAll();
        zlib.finishAndReleaseAll();
        plain.finishAndReleaseAll();
    }
}
