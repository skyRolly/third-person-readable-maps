import org.apache.logging.log4j.LogManager;
import org.apache.logging.log4j.Logger;

/** Mirrors Minecraft's parameterized [CHAT] logger call with a harmless local JNDI name. */
public class ChatJndiProbe {
  public static void main(String[] args) throws Exception {
    System.setProperty("java.naming.factory.initial", "NoNetworkContextFactory");
    Class<?> lookup = Class.forName("org.apache.logging.log4j.core.lookup.JndiLookup");
    System.out.println("LOOKUP_CLASS_SOURCE=" + lookup.getProtectionDomain().getCodeSource().getLocation());
    Logger logger = LogManager.getLogger("issue45.chat.probe");
    int before = NoNetworkContextFactory.calls;
    String componentText = "BEFORE_${jndi:local}_AFTER";
    logger.info("[CHAT] {}", componentText.replaceAll("\r", "\\r").replaceAll("\n", "\\n"));
    System.out.println("NO_NETWORK_CONTEXT_CALLS=" + (NoNetworkContextFactory.calls - before));
  }
}
