package nullprobe;
import net.minecraft.class_1799;
import net.minecraft.class_1937;
import net.minecraft.class_22;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.Redirect;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;

@Mixin(targets = "tech.rolly.thirdpersonreadablemaps.ReadableMapSurface", remap = false)
public abstract class MissingDataProbeMixin {
    private static int forced;
    private static int completed;

    @Redirect(method = "submitReadableMap", at = @At(value = "INVOKE", target = "Lnet/minecraft/class_1806;method_7997(Lnet/minecraft/class_1799;Lnet/minecraft/class_1937;)Lnet/minecraft/class_22;"), remap = false)
    private static class_22 forceMissingData(class_1799 stack, class_1937 world) {
        if (forced < 8) System.out.println("TPRM_MISSING_DATA_PROBE forced_null=" + (++forced));
        return null;
    }

    @Inject(method = "submitReadableMap", at = @At("RETURN"), remap = false)
    private static void after(CallbackInfo ci) {
        if (completed < forced) System.out.println("TPRM_MISSING_DATA_PROBE render_completed=" + (++completed));
    }
}
