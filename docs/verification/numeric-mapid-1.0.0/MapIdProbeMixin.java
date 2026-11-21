package mapidprobe;

import net.minecraft.class_22;
import net.minecraft.class_1799;
import net.minecraft.class_1806;
import net.minecraft.class_1937;
import net.minecraft.class_2487;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.ModifyVariable;
import org.spongepowered.asm.mixin.injection.Redirect;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;

/** Test-only copied stacks; the real held item is never changed. */
@Mixin(targets = "tech.rolly.thirdpersonreadablemaps.ReadableMapSurface", remap = false)
public abstract class MapIdProbeMixin {
    private static int sample;
    private static String kind;
    private static boolean lookup, found;

    @ModifyVariable(method = "submitReadableMap", at = @At("HEAD"), argsOnly = true, ordinal = 0, remap = false)
    private static class_1799 copiedStack(class_1799 input) {
        if (sample >= 30) return input;
        class_1799 copy = input.method_7972();
        class_2487 tag = new class_2487();
        switch (sample % 10) {
            case 0: kind = "absent"; copy.method_7980(null); break;
            case 1: kind = "empty"; copy.method_7980(tag); break;
            case 2: kind = "text"; tag.method_10582("map", "not-a-number"); copy.method_7980(tag); break;
            case 3: kind = "fraction"; tag.method_10548("map", 0.5f); copy.method_7980(tag); break;
            case 4: kind = "overflow"; tag.method_10544("map", 4294967296L); copy.method_7980(tag); break;
            case 5: kind = "nan"; tag.method_10548("map", Float.NaN); copy.method_7980(tag); break;
            case 6: kind = "zero"; tag.method_10569("map", 0); copy.method_7980(tag); break;
            case 7: kind = "shortzero"; tag.method_10575("map", (short) 0); copy.method_7980(tag); break;
            case 8: kind = "nonzero"; tag.method_10569("map", 2); copy.method_7980(tag); break;
            default: kind = "unavailable"; tag.method_10569("map", 9999); copy.method_7980(tag); break;
        }
        lookup = false; found = false;
        return copy;
    }

    @Redirect(method = "submitReadableMap", at = @At(value = "INVOKE", target = "Lnet/minecraft/class_1806;method_8001(Lnet/minecraft/class_1799;Lnet/minecraft/class_1937;)Lnet/minecraft/class_22;"), remap = false)
    private static class_22 observeLookup(class_1799 stack, class_1937 world) {
        class_22 data = class_1806.method_8001(stack, world);
        if (sample < 30) { lookup = true; found = data != null; }
        return data;
    }

    @Inject(method = "submitReadableMap", at = @At("RETURN"), remap = false)
    private static void after(CallbackInfo ci) {
        if (sample >= 30) return;
        System.out.println("TPRM_MAPID_PROBE case=" + kind + " lookup=" + lookup + " data=" + found);
        sample++;
    }
}
