package tech.rolly.thirdpersonreadablemaps;

import com.mojang.blaze3d.vertex.PoseStack;
import com.mojang.blaze3d.vertex.VertexConsumer;
import com.mojang.math.Axis;
import net.minecraft.client.Minecraft;
import net.minecraft.client.renderer.MultiBufferSource;
import net.minecraft.client.renderer.RenderType;
import net.minecraft.core.component.DataComponents;
import net.minecraft.core.component.TypedDataComponent;
import org.joml.Quaternionf;
import net.minecraft.resources.ResourceLocation;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.item.MapItem;
import net.minecraft.world.level.saveddata.maps.MapId;
import net.minecraft.world.level.saveddata.maps.MapItemSavedData;

/** Renders map faces and map data in the holding hand coordinate space. */
public final class ReadableMapSurface {
    private static final RenderType BLANK_MAP_FACE = RenderType.text(
            new ResourceLocation("textures/map/map_background.png"));
    private static final RenderType FILLED_MAP_FACE = RenderType.text(
            new ResourceLocation("textures/map/map_background_checkerboard.png"));

    private ReadableMapSurface() {}

    public static void submitReadableMap(PoseStack mapTransform, MultiBufferSource mapQueue, ItemStack mapItemStack,
                            int mapPackedLight, boolean useCompactMap, boolean useLeftMapLayout) {
        Minecraft mapClientInstance = Minecraft.getInstance();
        if (mapClientInstance.level == null) return;
        MapId readableMapId = null;
        // Iteration and typed-component access avoid version-specific getter linkage.
        for (TypedDataComponent<?> component : mapItemStack.getComponents()) {
            if (component.type() == DataComponents.MAP_ID && component.value() instanceof MapId id) {
                readableMapId = id;
                break;
            }
        }
        MapItemSavedData readableMapData = MapItem.getSavedData(mapItemStack, mapClientInstance.level);

        if (useCompactMap) {
            rotate(mapTransform, Axis.YP.rotationDegrees(160f));
            rotate(mapTransform, Axis.ZP.rotationDegrees(180f));
            mapTransform.scale(0.38f, 0.38f, 0.38f);
            mapTransform.translate(-0.1, -1.2, 0.0);
            mapTransform.scale(0.0098125f, 0.0098125f, 0.0098125f);
        } else {
            rotate(mapTransform, Axis.YP.rotationDegrees(useLeftMapLayout ? 154.5f : 155f));
            rotate(mapTransform, Axis.ZP.rotationDegrees(useLeftMapLayout ? 166.5f : 213.5f));
            mapTransform.scale(0.38f, 0.38f, 0.38f);
            if (useLeftMapLayout) mapTransform.translate(0.585, -1.225, 0.15);
            else mapTransform.translate(-0.955, -1.8, 0.0);
            mapTransform.scale(0.0138125f, 0.0138125f, 0.0138125f);
        }

        submitMapFace(mapQueue, mapTransform, readableMapData == null ? BLANK_MAP_FACE : FILLED_MAP_FACE, mapPackedLight, false);
        submitMapFace(mapQueue, mapTransform, BLANK_MAP_FACE, mapPackedLight, true);

        if (readableMapData != null && readableMapId != null) {
            mapClientInstance.gameRenderer.getMapRenderer().render(
                    mapTransform, mapQueue, readableMapId, readableMapData, false, mapPackedLight);
        }
    }

    /** Apply the same quaternion to the pose and normal matrices. */
    public static void rotate(PoseStack stack, Quaternionf rotation) {
        PoseStack.Pose pose = stack.last();
        pose.pose().rotate(rotation);
        pose.normal().rotate(rotation);
    }

    private static void submitMapFace(MultiBufferSource mapQueue, PoseStack mapTransform, RenderType mapFaceType,
                                 int mapPackedLight, boolean isReverseMapFace) {
        PoseStack.Pose mapFacePose = mapTransform.last();
        VertexConsumer mapFaceVertices = mapQueue.getBuffer(mapFaceType);
            if (isReverseMapFace) {
                mapFaceVertices.vertex(mapFacePose, -7f, -7f, 0f).color(-1).uv(0f, 0f).uv2(mapPackedLight).endVertex();
                mapFaceVertices.vertex(mapFacePose, 135f, -7f, 0f).color(-1).uv(1f, 0f).uv2(mapPackedLight).endVertex();
                mapFaceVertices.vertex(mapFacePose, 135f, 135f, 0f).color(-1).uv(1f, 1f).uv2(mapPackedLight).endVertex();
                mapFaceVertices.vertex(mapFacePose, -7f, 135f, 0f).color(-1).uv(0f, 1f).uv2(mapPackedLight).endVertex();
            } else {
                mapFaceVertices.vertex(mapFacePose, -7f, 135f, 0f).color(-1).uv(0f, 1f).uv2(mapPackedLight).endVertex();
                mapFaceVertices.vertex(mapFacePose, 135f, 135f, 0f).color(-1).uv(1f, 1f).uv2(mapPackedLight).endVertex();
                mapFaceVertices.vertex(mapFacePose, 135f, -7f, 0f).color(-1).uv(1f, 0f).uv2(mapPackedLight).endVertex();
                mapFaceVertices.vertex(mapFacePose, -7f, -7f, 0f).color(-1).uv(0f, 0f).uv2(mapPackedLight).endVertex();
            }
    }
}
