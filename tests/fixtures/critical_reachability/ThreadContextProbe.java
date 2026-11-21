import org.apache.logging.log4j.LogManager;
import org.apache.logging.log4j.Logger;
import org.apache.logging.log4j.ThreadContext;
public class ThreadContextProbe {
  public static void main(String[] args) {
    System.setProperty("java.naming.factory.initial", "NoNetworkContextFactory");
    ThreadContext.put("loginId", "${jndi:local}");
    Logger log = LogManager.getLogger("issue45.context.probe");
    int before = NoNetworkContextFactory.calls;
    log.info("safe message");
    System.out.println("NO_NETWORK_CONTEXT_CALLS=" + (NoNetworkContextFactory.calls - before));
  }
}
