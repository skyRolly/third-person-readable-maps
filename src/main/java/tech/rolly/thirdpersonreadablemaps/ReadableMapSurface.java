package tech.rolly.thirdpersonreadablemaps;

import com.mojang.blaze3d.vertex.PoseStack;
import com.mojang.math.Axis;
import net.minecraft.client.Minecraft;
import net.minecraft.client.renderer.SubmitNodeCollector;
import net.minecraft.client.renderer.rendertype.RenderType;
import net.minecraft.client.renderer.rendertype.RenderTypes;
import net.minecraft.client.renderer.state.MapRenderState;
import net.minecraft.core.component.DataComponents;
import net.minecraft.resources.Identifier;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.item.MapItem;
import net.minecraft.world.level.saveddata.maps.MapId;
import net.minecraft.world.level.saveddata.maps.MapItemSavedData;

/** Submits map faces and map data in the holding hand coordinate space. */
public final class ReadableMapSurface {
    private static final RenderType BLANK_MAP_FACE = RenderTypes.text(
            Identifier.withDefaultNamespace("textures/map/map_background.png"));
    private static final RenderType FILLED_MAP_FACE = RenderTypes.text(
            Identifier.withDefaultNamespace("textures/map/map_background_checkerboard.png"));

    private ReadableMapSurface() {}

    public static void submitReadableMap(PoseStack mapTransform, SubmitNodeCollector mapQueue, ItemStack mapItemStack,
                            int mapPackedLight, boolean useCompactMap, boolean useLeftMapLayout) {
        Minecraft mapClientInstance = Minecraft.getInstance();
        if (mapClientInstance.level == null) return;
        MapId readableMapId = mapItemStack.get(DataComponents.MAP_ID);
        MapItemSavedData readableMapData = MapItem.getSavedData(mapItemStack, mapClientInstance.level);

        if (useCompactMap) {
            mapTransform.mulPose(Axis.YP.rotationDegrees(160f));
            mapTransform.mulPose(Axis.ZP.rotationDegrees(180f));
            mapTransform.scale(0.38f, 0.38f, 0.38f);
            mapTransform.translate(-0.1, -1.2, 0.0);
            mapTransform.scale(0.0098125f, 0.0098125f, 0.0098125f);
        } else {
            mapTransform.mulPose(Axis.YP.rotationDegrees(useLeftMapLayout ? 154.5f : 155f));
            mapTransform.mulPose(Axis.ZP.rotationDegrees(useLeftMapLayout ? 166.5f : 213.5f));
            mapTransform.scale(0.38f, 0.38f, 0.38f);
            if (useLeftMapLayout) mapTransform.translate(0.585, -1.225, 0.15);
            else mapTransform.translate(-0.955, -1.8, 0.0);
            mapTransform.scale(0.0138125f, 0.0138125f, 0.0138125f);
        }

        submitMapFace(mapQueue, mapTransform, readableMapData == null ? BLANK_MAP_FACE : FILLED_MAP_FACE, mapPackedLight, false);
        submitMapFace(mapQueue, mapTransform, BLANK_MAP_FACE, mapPackedLight, true);

        if (readableMapData != null && readableMapId != null) {
            MapRenderState readableMapRenderState = new MapRenderState();
            mapClientInstance.getMapRenderer().extractRenderState(readableMapId, readableMapData, readableMapRenderState);
            mapClientInstance.getMapRenderer().render(readableMapRenderState, mapTransform, mapQueue, false, mapPackedLight);
        }
    }

    private static void submitMapFace(SubmitNodeCollector mapQueue, PoseStack mapTransform, RenderType mapFaceType,
                                 int mapPackedLight, boolean isReverseMapFace) {
        mapQueue.submitCustomGeometry(mapTransform, mapFaceType, (mapFacePose, mapFaceVertices) -> {
            if (isReverseMapFace) {
                mapFaceVertices.addVertex(mapFacePose, -7f, -7f, 0f).setColor(-1).setUv(0f, 0f).setLight(mapPackedLight);
                mapFaceVertices.addVertex(mapFacePose, 135f, -7f, 0f).setColor(-1).setUv(1f, 0f).setLight(mapPackedLight);
                mapFaceVertices.addVertex(mapFacePose, 135f, 135f, 0f).setColor(-1).setUv(1f, 1f).setLight(mapPackedLight);
                mapFaceVertices.addVertex(mapFacePose, -7f, 135f, 0f).setColor(-1).setUv(0f, 1f).setLight(mapPackedLight);
            } else {
                mapFaceVertices.addVertex(mapFacePose, -7f, 135f, 0f).setColor(-1).setUv(0f, 1f).setLight(mapPackedLight);
                mapFaceVertices.addVertex(mapFacePose, 135f, 135f, 0f).setColor(-1).setUv(1f, 1f).setLight(mapPackedLight);
                mapFaceVertices.addVertex(mapFacePose, 135f, -7f, 0f).setColor(-1).setUv(1f, 0f).setLight(mapPackedLight);
                mapFaceVertices.addVertex(mapFacePose, -7f, -7f, 0f).setColor(-1).setUv(0f, 0f).setLight(mapPackedLight);
            }
        });
    }
}
