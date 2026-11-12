package tech.rolly.thirdpersonreadablemaps;

import com.mojang.blaze3d.platform.GlStateManager;
import net.minecraft.client.MinecraftClient;
import net.minecraft.client.render.BufferBuilder;
import net.minecraft.client.render.Tessellator;
import net.minecraft.client.render.VertexFormats;
import net.minecraft.item.FilledMapItem;
import net.minecraft.item.ItemStack;
import net.minecraft.item.map.MapState;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.util.Identifier;
import org.lwjgl.opengl.GL11;
import org.lwjgl.opengl.GL13;

/** Draws both faces and available map data in the current hand transform. */
public final class ReadableMapSurface {
    private static final Identifier MAP_FACE = new Identifier("textures/map/map_background.png");

    private ReadableMapSurface() {}

    public static void draw(ItemStack stack, boolean compact, boolean leftLayout) {
        MinecraftClient client = MinecraftClient.getInstance();
        if (client.world == null) return;
        // The historical getter falls back to map zero when the numeric tag is
        // absent. An explicit zero is valid, but a missing identity is not.
        CompoundTag tag = stack.getTag();
        MapState data = tag != null && tag.contains("map", 99)
                ? FilledMapItem.getMapState(stack, client.world) : null;
        if (compact) {
            GlStateManager.rotatef(160f, 0f, 1f, 0f);
            GlStateManager.rotatef(180f, 0f, 0f, 1f);
            GlStateManager.scalef(0.38f, 0.38f, 0.38f);
            GlStateManager.translatef(-0.1f, -1.2f, 0f);
            GlStateManager.scalef(0.0098125f, 0.0098125f, 0.0098125f);
        } else {
            GlStateManager.rotatef(leftLayout ? 154.5f : 155f, 0f, 1f, 0f);
            GlStateManager.rotatef(leftLayout ? 166.5f : 213.5f, 0f, 0f, 1f);
            GlStateManager.scalef(0.38f, 0.38f, 0.38f);
            if (leftLayout) GlStateManager.translatef(0.585f, -1.225f, 0.15f);
            else GlStateManager.translatef(-0.955f, -1.8f, 0f);
            GlStateManager.scalef(0.0138125f, 0.0138125f, 0.0138125f);
        }
        // Follow the 1.14 first-person map renderer's lighting and texture path.
        boolean lightingWasEnabled = GL11.glIsEnabled(GL11.GL_LIGHTING);
        int activeTexture = GL11.glGetInteger(GL13.GL_ACTIVE_TEXTURE);
        int boundTexture = GL11.glGetInteger(GL11.GL_TEXTURE_BINDING_2D);
        GlStateManager.disableLighting();
        try {
            client.getTextureManager().bindTexture(MAP_FACE);
            Tessellator tessellator = Tessellator.getInstance();
            BufferBuilder buffer = tessellator.getBuffer();
            buffer.begin(7, VertexFormats.POSITION_TEXTURE);
            vertex(buffer, -7, 135, 0, 1);
            vertex(buffer, 135, 135, 1, 1);
            vertex(buffer, 135, -7, 1, 0);
            vertex(buffer, -7, -7, 0, 0);
            vertex(buffer, -7, -7, 0, 0);
            vertex(buffer, 135, -7, 1, 0);
            vertex(buffer, 135, 135, 1, 1);
            vertex(buffer, -7, 135, 0, 1);
            tessellator.draw();
            if (data != null) client.gameRenderer.getMapRenderer().draw(data, false);
        } finally {
            try {
                // Use the state manager so its texture cache follows OpenGL.
                GlStateManager.activeTexture(activeTexture);
                GlStateManager.bindTexture(boundTexture);
            } finally {
                if (lightingWasEnabled) GlStateManager.enableLighting();
                else GlStateManager.disableLighting();
            }
        }
    }

    private static void vertex(BufferBuilder buffer, double x, double y, double u, double v) {
        buffer.vertex(x, y, 0).texture(u, v).next();
    }
}
