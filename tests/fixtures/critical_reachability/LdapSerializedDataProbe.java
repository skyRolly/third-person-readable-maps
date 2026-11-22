import java.io.ByteArrayOutputStream;
import java.io.ObjectOutputStream;
import java.lang.reflect.InvocationTargetException;
import java.lang.reflect.Method;
import javax.naming.directory.Attributes;
import javax.naming.directory.BasicAttribute;
import javax.naming.directory.BasicAttributes;

/** Tests the JDK LDAP attribute decoder with one harmless local String object. */
public class LdapSerializedDataProbe {
  private static final String MARKER = "ISSUE45_HARMLESS_SERIALIZED_STRING";

  public static void main(String[] args) throws Exception {
    ByteArrayOutputStream bytes = new ByteArrayOutputStream();
    ObjectOutputStream output = new ObjectOutputStream(bytes);
    output.writeObject(MARKER);
    output.close();

    Attributes attributes = new BasicAttributes(true);
    attributes.put(new BasicAttribute("javaSerializedData", bytes.toByteArray()));
    Class<?> decoder = Class.forName("com.sun.jndi.ldap.Obj");
    Method decode = decoder.getDeclaredMethod("decodeObject", Attributes.class);
    decode.setAccessible(true);
    try {
      Object value = decode.invoke(null, attributes);
      if (!(value instanceof String) || !MARKER.equals(value)) {
        throw new IllegalStateException("LDAP decoder returned an unexpected local object");
      }
      System.out.println("LDAP_SERIALIZED_DATA_RESULT=deserialized:java.lang.String");
      System.out.println("LDAP_SERIALIZED_DATA_MARKER_MATCH=true");
    } catch (InvocationTargetException e) {
      Throwable cause = e.getCause();
      System.out.println("LDAP_SERIALIZED_DATA_RESULT=blocked:" + cause.getClass().getName());
      System.out.println("LDAP_SERIALIZED_DATA_MESSAGE=" + String.valueOf(cause.getMessage()));
      System.out.println("LDAP_SERIALIZED_DATA_MARKER_MATCH=false");
    }
    System.out.println("LDAP_DECODER_CLASS=" + decoder.getName());
    System.out.println("NETWORK_REQUESTS=0");
  }
}
