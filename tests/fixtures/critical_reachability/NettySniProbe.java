import io.netty.channel.ChannelHandlerContext;
import io.netty.channel.embedded.EmbeddedChannel;
import io.netty.handler.ssl.SniHandler;
import io.netty.handler.ssl.SslContext;
import io.netty.buffer.Unpooled;
import io.netty.util.Mapping;
import java.io.ByteArrayOutputStream;
import java.nio.charset.StandardCharsets;

public class NettySniProbe {
    private static final class ObservedSniHandler extends SniHandler {
        private int fallbackSelections;
        private int hostSelections;

        @SuppressWarnings("unchecked")
        ObservedSniHandler() {
            super((Mapping<String, SslContext>) hostname -> null);
        }

        @Override
        protected void replaceHandler(ChannelHandlerContext context, String hostname, SslContext sslContext) {
            if (hostname == null) {
                fallbackSelections++;
            } else {
                hostSelections++;
            }
        }
    }

    private static byte[] tlsRecord(byte[] payload) {
        byte[] record = new byte[5 + payload.length];
        record[0] = 22;
        record[1] = 3;
        record[2] = 3;
        record[3] = (byte) (payload.length >>> 8);
        record[4] = (byte) payload.length;
        System.arraycopy(payload, 0, record, 5, payload.length);
        return record;
    }

    private static byte[] fragmentedClientHello() throws Exception {
        byte[] hostname = "host.example".getBytes(StandardCharsets.US_ASCII);
        ByteArrayOutputStream body = new ByteArrayOutputStream();
        body.write(new byte[] {3, 3});
        body.write(new byte[32]);
        body.write(new byte[] {0, 0, 2, 0x13, 0x01, 1, 0});
        int serverNameListLength = 1 + 2 + hostname.length;
        int serverNameExtensionLength = 2 + serverNameListLength;
        int extensionsLength = 4 + serverNameExtensionLength;
        body.write(new byte[] {(byte) (extensionsLength >>> 8), (byte) extensionsLength});
        body.write(new byte[] {0, 0, (byte) (serverNameExtensionLength >>> 8),
                               (byte) serverNameExtensionLength,
                               (byte) (serverNameListLength >>> 8), (byte) serverNameListLength,
                               0, (byte) (hostname.length >>> 8), (byte) hostname.length});
        body.write(hostname);
        byte[] helloBody = body.toByteArray();
        ByteArrayOutputStream handshake = new ByteArrayOutputStream();
        handshake.write(new byte[] {1, (byte) (helloBody.length >>> 16),
                                    (byte) (helloBody.length >>> 8), (byte) helloBody.length});
        handshake.write(helloBody);
        return handshake.toByteArray();
    }

    public static void main(String[] args) throws Exception {
        byte[] hello = fragmentedClientHello();
        byte[] firstFragment = tlsRecord(new byte[] {hello[0], hello[1]});
        byte[] secondFragment = tlsRecord(java.util.Arrays.copyOfRange(hello, 2, hello.length));
        ObservedSniHandler handler = new ObservedSniHandler();
        EmbeddedChannel channel = new EmbeddedChannel(handler);
        try {
            channel.writeInbound(Unpooled.wrappedBuffer(firstFragment));
            int fallbackAfterFirstFragment = handler.fallbackSelections;
            if (fallbackAfterFirstFragment == 0) {
                channel.writeInbound(Unpooled.wrappedBuffer(secondFragment));
            }
            System.out.println("FIRST_FRAGMENT_FALLBACKS=" + fallbackAfterFirstFragment);
            System.out.println("FINAL_FALLBACKS=" + handler.fallbackSelections);
            System.out.println("HOST_SELECTIONS=" + handler.hostSelections);
        } finally {
            channel.finishAndReleaseAll();
        }
    }
}
