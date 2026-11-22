import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;

public final class JacksonDepthProbe {
    public static void main(String[] args) throws Exception {
        int depth = Integer.parseInt(args[0]);
        StringBuilder json = new StringBuilder(depth * 2 + 16);
        json.append("{\"nested\":");
        for (int i = 0; i < depth; i++) json.append('[');
        json.append('0');
        for (int i = 0; i < depth; i++) json.append(']');
        json.append('}');
        ObjectMapper mapper = new ObjectMapper();
        try {
            JsonNode result = mapper.readTree(json.toString());
            System.out.println("parsed depth=" + depth + " node=" + result.get("nested").getNodeType());
        } catch (StackOverflowError overflow) {
            System.out.println("StackOverflowError depth=" + depth + " input_bytes=" + json.length());
        }
    }
}
