import org.apache.logging.log4j.LogManager;
import org.apache.logging.log4j.Logger;
public class JndiLookupProbe {
  public static void main(String[] args) throws Exception {
    System.setProperty("java.naming.factory.initial", "NoNetworkContextFactory");
    Class<?> lookup = Class.forName("org.apache.logging.log4j.core.lookup.JndiLookup");
    System.out.println("LOOKUP_CLASS_SOURCE=" + lookup.getProtectionDomain().getCodeSource().getLocation());
    Logger logger = LogManager.getLogger("issue45.jndi.probe");
    int before = NoNetworkContextFactory.calls;
    logger.info("BEFORE_${jndi:local}_AFTER");
    System.out.println("NO_NETWORK_CONTEXT_CALLS=" + (NoNetworkContextFactory.calls - before));
  }
}
