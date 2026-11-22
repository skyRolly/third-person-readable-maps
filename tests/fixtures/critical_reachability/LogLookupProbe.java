import org.apache.logging.log4j.LogManager;
import org.apache.logging.log4j.Logger;
public class LogLookupProbe {
  public static void main(String[] args) throws Exception {
    System.setProperty("issue45.safe.marker", "LOCAL_LOOKUP_EXPANDED");
    Class<?> lookup = Class.forName("org.apache.logging.log4j.core.lookup.JndiLookup");
    System.out.println("LOOKUP_CLASS_SOURCE=" + lookup.getProtectionDomain().getCodeSource().getLocation());
    Logger logger = LogManager.getLogger("issue45.lookup.probe");
    logger.info("BEFORE_${sys:issue45.safe.marker}_AFTER");
    System.out.println("PROBE_FINISHED");
  }
}
