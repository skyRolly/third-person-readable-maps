import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
public final class JacksonFixedDepthProbe {
  public static void main(String[] args) throws Exception {
    int depth=Integer.parseInt(args[0]); StringBuilder json=new StringBuilder(depth*2+16);
    json.append("{\"nested\":"); for(int i=0;i<depth;i++) json.append('['); json.append('0'); for(int i=0;i<depth;i++) json.append(']'); json.append('}');
    try { JsonNode node=new ObjectMapper().readTree(json.toString()); System.out.println("parsed depth="+depth); }
    catch(Throwable e) { System.out.println(e.getClass().getName()+" depth="+depth+" message="+e.getMessage()); }
  }
}
