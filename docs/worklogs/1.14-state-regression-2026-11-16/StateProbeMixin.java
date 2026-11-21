package stateprobe;

import com.mojang.blaze3d.platform.GlStateManager;
import java.util.Arrays;
import org.lwjgl.opengl.GL11;
import org.lwjgl.opengl.GL13;
import org.lwjgl.opengl.GL14;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;

/** Test-only in-memory instrumentation; never included in the product JAR. */
@Mixin(targets = "tech.rolly.thirdpersonreadablemaps.ReadableMapSurface", remap = false)
public abstract class StateProbeMixin {
    private static int samples;
    private static int unit, binding, texture;
    private static boolean lighting, blend, alpha;
    private static int[] factors, expectedFactors;
    private static float[] color, expectedColor;

    private static int[] factors() {
        return new int[]{GL11.glGetInteger(GL14.GL_BLEND_SRC_RGB), GL11.glGetInteger(GL14.GL_BLEND_DST_RGB),
                         GL11.glGetInteger(GL14.GL_BLEND_SRC_ALPHA), GL11.glGetInteger(GL14.GL_BLEND_DST_ALPHA)};
    }
    private static float[] color() {
        float[] result = new float[4];
        GL11.glGetFloatv(GL11.GL_CURRENT_COLOR, result);
        return result;
    }
    @Inject(method = "draw", at = @At("HEAD"), remap = false)
    private static void before(CallbackInfo ci) {
        if (samples >= 8) return;
        unit = GL11.glGetInteger(GL13.GL_ACTIVE_TEXTURE);
        binding = GL11.glGetInteger(GL11.GL_TEXTURE_BINDING_2D);
        lighting = GL11.glIsEnabled(GL11.GL_LIGHTING);
        blend = GL11.glIsEnabled(GL11.GL_BLEND);
        alpha = GL11.glIsEnabled(GL11.GL_ALPHA_TEST);
        factors = factors(); color = color();
        texture = GL11.glGenTextures();
        GlStateManager.bindTexture(texture);
        GlStateManager.enableBlend();
        GlStateManager.disableAlphaTest();
        GlStateManager.blendFuncSeparate(GL11.GL_SRC_ALPHA, GL11.GL_ONE, GL11.GL_ONE, GL11.GL_ZERO);
        GlStateManager.color4f(0.25f, 0.5f, 0.75f, 1f);
        expectedFactors = factors(); expectedColor = color();
    }
    @Inject(method = "draw", at = @At("RETURN"), remap = false)
    private static void after(CallbackInfo ci) {
        if (samples >= 8) return;
        System.out.println("TPRM_STATE_PROBE sample=" + samples
                + " blend=" + GL11.glIsEnabled(GL11.GL_BLEND)
                + " alpha=" + GL11.glIsEnabled(GL11.GL_ALPHA_TEST)
                + " factors_match=" + Arrays.equals(expectedFactors, factors())
                + " color_match=" + Arrays.equals(expectedColor, color())
                + " texture_match=" + (texture == GL11.glGetInteger(GL11.GL_TEXTURE_BINDING_2D))
                + " unit_match=" + (unit == GL11.glGetInteger(GL13.GL_ACTIVE_TEXTURE))
                + " lighting_match=" + (lighting == GL11.glIsEnabled(GL11.GL_LIGHTING)));
        GlStateManager.blendFuncSeparate(factors[0], factors[1], factors[2], factors[3]);
        if (blend) GlStateManager.enableBlend(); else GlStateManager.disableBlend();
        if (alpha) GlStateManager.enableAlphaTest(); else GlStateManager.disableAlphaTest();
        GlStateManager.color4f(color[0], color[1], color[2], color[3]);
        GlStateManager.activeTexture(unit);
        GlStateManager.bindTexture(binding);
        GL11.glDeleteTextures(texture);
        if (lighting) GlStateManager.enableLighting(); else GlStateManager.disableLighting();
        samples++;
    }
}
