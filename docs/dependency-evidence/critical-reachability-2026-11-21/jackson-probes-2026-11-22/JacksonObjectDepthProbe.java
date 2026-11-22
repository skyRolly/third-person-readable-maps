import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
public final class JacksonObjectDepthProbe {
  public static void main(String[] args) throws Exception {
    int depth=Integer.parseInt(args[0]);
    StringBuilder json=new StringBuilder(depth*8+2);
    for(int i=0;i<depth;i++) json.append("{\"n\":");
    json.append('0');
    for(int i=0;i<depth;i++) json.append('}');
    try { JsonNode node=new ObjectMapper().readTree(json.toString()); System.out.println("parsed depth="+depth); }
    catch(StackOverflowError e) { System.out.println("StackOverflowError depth="+depth+" input_bytes="+json.length()); }
  }
}
