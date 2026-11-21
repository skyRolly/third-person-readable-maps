package tech.rolly.probe;

import com.mojang.serialization.Codec;
import com.mojang.serialization.DataResult;
import com.mojang.serialization.DynamicOps;
import java.util.Optional;

/** Inspect the game's own map-ID codec and NBT operations without a mod. */
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
        for (int i = 0; i < tags.length; i++) {
            DataResult decoded = codec.parse(ops, tags[i]);
            Optional value = decoded.result();
            String result = value.isPresent()
                    ? mapId.getMethod(args[4]).invoke(value.get()).toString() : "error";
            System.out.println(labels[i] + "=" + result);
            if (i == 0 && !result.equals("0")) throw new AssertionError("explicit zero: " + result);
            if (i == 1 && !result.equals("7")) throw new AssertionError("explicit seven: " + result);
        }
    }
}
