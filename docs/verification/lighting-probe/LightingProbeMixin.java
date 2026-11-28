package stateprobe;

import com.mojang.blaze3d.platform.GlStateManager;
import org.lwjgl.opengl.GL11;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;

@Mixin(targets = "tech.rolly.thirdpersonreadablemaps.ReadableMapSurface", remap = false)
public abstract class LightingProbeMixin {
    private static int samples;
    private static boolean expected;

    @Inject(method = "draw", at = @At("HEAD"), remap = false)
    private static void before(CallbackInfo ci) {
        if (samples >= 8) return;
        expected = (samples & 1) == 0;
        if (expected) GlStateManager.enableLighting();
        else GlStateManager.disableLighting();
        expected = GL11.glIsEnabled(GL11.GL_LIGHTING);
    }

    @Inject(method = "draw", at = @At("RETURN"), remap = false)
    private static void after(CallbackInfo ci) {
        if (samples >= 8) return;
        boolean actual = GL11.glIsEnabled(GL11.GL_LIGHTING);
        System.out.println("TPRM_LIGHTING_PROBE expected=" + expected + " actual=" + actual);
        samples++;
    }
}
