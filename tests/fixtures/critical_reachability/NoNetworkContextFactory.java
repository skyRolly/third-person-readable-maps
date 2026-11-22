import java.util.Hashtable;
import javax.naming.Context;
import javax.naming.NamingException;
import javax.naming.spi.InitialContextFactory;
public class NoNetworkContextFactory implements InitialContextFactory {
  public static int calls;
  @Override public Context getInitialContext(Hashtable<?, ?> env) throws NamingException {
    calls++;
    throw new NamingException("Synthetic context refuses all lookups; no network provider used");
  }
}
