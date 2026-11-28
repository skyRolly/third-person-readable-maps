package stateprobe;

import com.mojang.blaze3d.platform.GlStateManager;
import org.lwjgl.opengl.GL11;
import org.lwjgl.opengl.GL13;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;

/** Test-only probe: seed a distinct binding and alternate lighting for real draws. */
@Mixin(targets = "tech.rolly.thirdpersonreadablemaps.ReadableMapSurface", remap = false)
public abstract class StateProbeMixin {
    private static int samples;
    private static int previousUnit, selectedUnit, previousBinding, expectedTexture;
    private static boolean previousLighting, expectedLighting;

    @Inject(method = "draw", at = @At("HEAD"), remap = false)
    private static void before(CallbackInfo ci) {
        if (samples >= 8) return;
        previousUnit = GL11.glGetInteger(GL13.GL_ACTIVE_TEXTURE);
        selectedUnit = GL13.GL_TEXTURE0 + ((samples / 2) & 1);
        GlStateManager.activeTexture(selectedUnit);
        previousBinding = GL11.glGetInteger(GL11.GL_TEXTURE_BINDING_2D);
        previousLighting = GL11.glIsEnabled(GL11.GL_LIGHTING);
        expectedLighting = (samples & 1) == 0;
        if (expectedLighting) GlStateManager.enableLighting();
        else GlStateManager.disableLighting();
        expectedTexture = GL11.glGenTextures();
        GlStateManager.bindTexture(expectedTexture);
    }

    @Inject(method = "draw", at = @At("RETURN"), remap = false)
    private static void after(CallbackInfo ci) {
        if (samples >= 8) return;
        int unit = GL11.glGetInteger(GL13.GL_ACTIVE_TEXTURE);
        int binding = GL11.glGetInteger(GL11.GL_TEXTURE_BINDING_2D);
        boolean lighting = GL11.glIsEnabled(GL11.GL_LIGHTING);
        System.out.println("TPRM_STATE_PROBE sample=" + samples + " expected_unit=" + selectedUnit
                + " actual_unit=" + unit + " expected_binding=" + expectedTexture
                + " actual_binding=" + binding + " expected_lighting=" + expectedLighting
                + " actual_lighting=" + lighting);
        GlStateManager.activeTexture(selectedUnit);
        GlStateManager.bindTexture(previousBinding);
        GL11.glDeleteTextures(expectedTexture);
        GlStateManager.activeTexture(previousUnit);
        if (previousLighting) GlStateManager.enableLighting();
        else GlStateManager.disableLighting();
        samples++;
    }
}
