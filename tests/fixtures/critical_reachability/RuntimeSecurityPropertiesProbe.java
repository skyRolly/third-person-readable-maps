public class RuntimeSecurityPropertiesProbe {
  public static void main(String[] args) {
    System.out.println("JAVA_VERSION=" + System.getProperty("java.version"));
    System.out.println("JAVA_SPECIFICATION_VERSION=" + System.getProperty("java.specification.version"));
    String trust = System.getProperty("com.sun.jndi.ldap.object.trustURLCodebase");
    System.out.println("LDAP_TRUST_URL_CODEBASE_PROPERTY=" + (trust == null ? "<unset>" : trust));
  }
}
