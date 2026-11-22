package issue45;

import com.google.common.collect.MapMaker;
import java.io.ByteArrayInputStream;
import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.io.ObjectInputStream;
import java.io.ObjectOutputStream;
import java.io.Serializable;
import java.lang.reflect.Method;
import java.util.concurrent.ConcurrentMap;

public final class GuavaDeserializationProbe {
  private static byte[] serialize(Serializable value) throws IOException {
    ByteArrayOutputStream bytes = new ByteArrayOutputStream();
    try (ObjectOutputStream output = new ObjectOutputStream(bytes)) {
      output.writeObject(value);
    }
    return bytes.toByteArray();
  }

  private static Object readWithHugeDeclaredSize(byte[] bytes) throws IOException, ClassNotFoundException {
    try (ObjectInputStream input = new ObjectInputStream(new ByteArrayInputStream(bytes)) {
      @Override public int readInt() throws IOException {
        super.readInt();
        return Integer.MAX_VALUE;
      }
    }) {
      return input.readObject();
    }
  }

  private static void probe(String name, Serializable value) throws Exception {
    byte[] bytes = serialize(value);
    try {
      Object result = readWithHugeDeclaredSize(bytes);
      System.out.println(name + ": unexpected object returned " + result.getClass().getName());
    } catch (OutOfMemoryError error) {
      System.out.println(name + ": unbounded allocation observed; " + error.getClass().getName());
    } catch (IOException error) {
      if (error instanceof java.io.EOFException) {
        System.out.println(name + ": bounded allocation; truncated controlled stream rejected with EOFException");
      } else {
        System.out.println(name + ": other I/O failure; " + error.getClass().getName() + ": " + error.getMessage());
      }
    }
  }

  private static void probeCompact(String className, String method, Object... values) throws Exception {
    try {
      Class<?> type = Class.forName(className);
      Method factory = type.getDeclaredMethod("create");
      factory.setAccessible(true);
      Object collection = factory.invoke(null);
      Method mutator = method.equals("put")
          ? type.getDeclaredMethod(method, Object.class, Object.class)
          : type.getDeclaredMethod(method, Object.class);
      mutator.setAccessible(true);
      if (method.equals("put")) mutator.invoke(collection, values[0], values[1]);
      else mutator.invoke(collection, values[0]);
      probe(type.getSimpleName(), (Serializable) collection);
    } catch (ClassNotFoundException missing) {
      System.out.println(className + ": absent from this Guava artifact");
    }
  }

  public static void main(String[] args) throws Exception {
    String target = args.length == 0 ? "all" : args[0];
    if (target.equals("all") || target.equals("map"))
      probeCompact("com.google.common.collect.CompactHashMap", "put", 1, "1");
    if (target.equals("all") || target.equals("set"))
      probeCompact("com.google.common.collect.CompactHashSet", "add", 1);
    if (target.equals("all") || target.equals("mapmaker")) {
      ConcurrentMap<Integer, String> concurrentMap = new MapMaker().weakKeys().makeMap();
      if (concurrentMap instanceof Serializable) probe("MapMakerInternalMap", (Serializable) concurrentMap);
      else System.out.println("MapMakerInternalMap: returned map proxy is not Serializable");
    }
  }
}
