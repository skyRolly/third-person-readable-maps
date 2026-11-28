package unavailableprobe;
import net.minecraft.class_1799;
import net.minecraft.class_1806;
import net.minecraft.class_1937;
import net.minecraft.class_22;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.Redirect;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;

@Mixin(targets = "tech.rolly.thirdpersonreadablemaps.ReadableMapSurface", remap = false)
public abstract class ObserveMapStateMixin {
    private static int observed;
    private static int completed;
    @Redirect(method = "submitReadableMap", at = @At(value = "INVOKE", target = "Lnet/minecraft/class_1806;method_7997(Lnet/minecraft/class_1799;Lnet/minecraft/class_1937;)Lnet/minecraft/class_22;"), remap = false)
    private static class_22 observe(class_1799 stack, class_1937 world) {
        class_22 actual = class_1806.method_7997(stack, world);
        if (observed < 8) { observed++; System.out.println("TPRM_UNAVAILABLE_PROBE observed_null=" + (actual == null)); }
        return actual;
    }
    @Inject(method = "submitReadableMap", at = @At("RETURN"), remap = false)
    private static void after(CallbackInfo callback) {
        if (completed < observed) System.out.println("TPRM_UNAVAILABLE_PROBE render_completed=" + (++completed));
    }
}
