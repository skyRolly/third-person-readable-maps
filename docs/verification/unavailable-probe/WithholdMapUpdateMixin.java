package unavailableprobe;
import net.minecraft.class_2683;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;

@Mixin(targets = "net.minecraft.class_634", remap = false)
public abstract class WithholdMapUpdateMixin {
    private static int blocked;
    @Inject(method = "method_11088(Lnet/minecraft/class_2683;)V", at = @At("HEAD"), cancellable = true, remap = false)
    private void withhold(class_2683 packet, CallbackInfo callback) {
        if (blocked < 8) System.out.println("TPRM_UNAVAILABLE_PROBE blocked_map_update=" + (++blocked));
        callback.cancel();
    }
}
