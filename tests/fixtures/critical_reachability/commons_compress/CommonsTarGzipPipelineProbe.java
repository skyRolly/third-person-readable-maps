import java.io.FileInputStream;
import org.apache.commons.compress.archivers.tar.TarArchiveInputStream;
import org.apache.commons.compress.archivers.tar.TarArchiveEntry;
import org.apache.commons.compress.compressors.gzip.GzipCompressorInputStream;

public final class CommonsTarGzipPipelineProbe {
    public static void main(String[] args) {
        try (GzipCompressorInputStream gzip = new GzipCompressorInputStream(new FileInputStream(args[0]));
             TarArchiveInputStream tar = new TarArchiveInputStream(gzip)) {
            TarArchiveEntry entry = tar.getNextTarEntry();
            System.out.println("FIRST_ENTRY=" + (entry == null ? "null" : entry.getName()));
        } catch (OutOfMemoryError error) {
            System.out.println("RESULT=OUT_OF_MEMORY");
        } catch (Throwable error) {
            System.out.println("RESULT=" + error.getClass().getName() + ":" + error.getMessage());
        }
    }
}
