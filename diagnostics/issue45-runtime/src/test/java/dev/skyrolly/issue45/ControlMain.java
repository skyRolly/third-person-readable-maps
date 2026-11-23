package dev.skyrolly.issue45;

import io.netty.channel.Channel;
import io.netty.channel.ChannelHandler;
import io.netty.channel.ChannelInitializer;
import io.netty.channel.ChannelInboundHandlerAdapter;
import io.netty.channel.embedded.EmbeddedChannel;
import io.netty.handler.codec.compression.JdkZlibDecoder;
import io.netty.handler.codec.compression.Lz4FrameDecoder;
import io.netty.handler.codec.compression.ZlibWrapper;

public final class ControlMain {
    private ControlMain() {}

    private static EmbeddedChannel newControl(final String name, final ChannelHandler handler) {
        // Initialize the pipeline before registration/activation so that the
        // channel-active snapshot proves the inventory contains the decoder.
        return new EmbeddedChannel(new ChannelInitializer<Channel>() {
            @Override protected void initChannel(Channel channel) {
                channel.pipeline().addLast(name, handler);
            }
        });
    }

    public static void main(String[] args) {
        EmbeddedChannel lz4 = newControl("control-lz4", new Lz4FrameDecoder());
        EmbeddedChannel zlib = newControl("control-zlib", new JdkZlibDecoder(ZlibWrapper.ZLIB));
        EmbeddedChannel plain = newControl("control-plain", new ChannelInboundHandlerAdapter());
        lz4.finishAndReleaseAll();
        zlib.finishAndReleaseAll();
        plain.finishAndReleaseAll();
    }
}
