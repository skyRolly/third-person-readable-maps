import java.lang.reflect.Field;

/** Reads the exact JRE's internal LDAP codebase trust gate without network access. */
public class JndiRemoteCodebasePolicyProbe {
  public static void main(String[] args) throws Exception {
    String[] candidates = {
        "com.sun.jndi.ldap.VersionHelper",
        "com.sun.jndi.ldap.VersionHelper12",
        "com.sun.naming.internal.VersionHelper12",
        "com.sun.naming.internal.VersionHelper"
    };
    Class<?> helper = null;
    Field gate = null;
    for (String name : candidates) {
      try {
        Class<?> candidate = Class.forName(name);
        for (Field field : candidate.getDeclaredFields()) {
          if (field.getName().equals("trustURLCodebase") ||
              field.getName().equals("TRUST_URL_CODE_BASE")) {
            helper = candidate;
            gate = field;
            break;
          }
        }
        if (gate != null) {
          break;
        }
      } catch (ClassNotFoundException ignored) {
      }
    }
    if (gate == null) {
      throw new IllegalStateException("JNDI remote codebase trust gate not found in known helpers");
    }
    gate.setAccessible(true);
    Object value = gate.get(null);
    boolean trusted = value instanceof Boolean
        ? ((Boolean) value).booleanValue()
        : "true".equalsIgnoreCase(String.valueOf(value));
    System.out.println("JNDI_HELPER_CLASS=" + helper.getName());
    System.out.println("JNDI_CODEBASE_TRUST_GATE=" + trusted);
    System.out.println("JNDI_CODEBASE_TRUST_GATE_RAW=" + value);
    String serialGateValue = "no_runtime_gate_method";
    try {
      Class<?> ldapHelper = Class.forName("com.sun.jndi.ldap.VersionHelper");
      java.lang.reflect.Method method = ldapHelper.getDeclaredMethod("isSerialDataAllowed");
      method.setAccessible(true);
      serialGateValue = String.valueOf(method.invoke(null));
    } catch (NoSuchMethodException ignored) {
    } catch (ClassNotFoundException ignored) {
    }
    System.out.println("JNDI_SERIAL_DATA_TRUST_GATE=" + serialGateValue);
    System.out.println("LDAP_TRUST_URL_CODEBASE_PROPERTY=" +
        (System.getProperty("com.sun.jndi.ldap.object.trustURLCodebase") == null
            ? "<unset>"
            : System.getProperty("com.sun.jndi.ldap.object.trustURLCodebase")));
    System.out.println("JAVA_VERSION=" + System.getProperty("java.version"));
  }
}
