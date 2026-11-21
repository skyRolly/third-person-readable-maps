package tech.rolly.probe;

import com.mojang.serialization.Codec;
import com.mojang.serialization.DataResult;
import com.mojang.serialization.DynamicOps;
import java.util.Optional;

/** Probe each game's own MapId codec and NbtOps, without installing a mod. */
public class MapCodecProbe {
    @SuppressWarnings({"rawtypes", "unchecked"})
    public static void main(String[] args) throws Exception {
        Class<?> mapId = Class.forName(args[0]);
        Class<?> nbtOps = Class.forName(args[2]);
        Codec codec = (Codec) mapId.getField(args[1]).get(null);
        DynamicOps ops = (DynamicOps) nbtOps.getField(args[3]).get(null);
        Object[] tags = {ops.createInt(0), ops.createInt(7), ops.createDouble(0.5),
                         ops.createLong(4294967296L), ops.createDouble(Double.NaN),
                         ops.createString("not a number")};
        String[] labels = {"explicit_zero", "explicit_seven", "fractional_double",
                           "overflow_long", "nan_double", "string"};
        String[] expected = {"0", "7", "0", "0", "0", "error"};
        for (int i = 0; i < tags.length; i++) {
            DataResult decoded = codec.parse(ops, tags[i]);
            Optional value = decoded.result();
            String result = value.isPresent()
                    ? mapId.getMethod(args[4]).invoke(value.get()).toString() : "error";
            System.out.println(labels[i] + "=" + result);
            if (!expected[i].equals(result)) throw new AssertionError(labels[i] + ": " + result);
        }
    }
}
