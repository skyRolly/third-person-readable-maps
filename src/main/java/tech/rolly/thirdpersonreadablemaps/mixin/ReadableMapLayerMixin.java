package tech.rolly.thirdpersonreadablemaps.mixin;

import tech.rolly.thirdpersonreadablemaps.ReadableMapSurface;
import com.mojang.blaze3d.vertex.PoseStack;
import com.mojang.math.Axis;
import net.minecraft.client.Minecraft;
import net.minecraft.client.model.ArmedModel;
import net.minecraft.client.model.EntityModel;
import net.minecraft.client.model.HumanoidModel;
import net.minecraft.client.renderer.SubmitNodeCollector;
import net.minecraft.client.renderer.entity.RenderLayerParent;
import net.minecraft.client.renderer.entity.layers.ItemInHandLayer;
import net.minecraft.client.renderer.entity.layers.RenderLayer;
import net.minecraft.client.renderer.entity.state.ArmedEntityRenderState;
import net.minecraft.client.renderer.item.ItemStackRenderState;
import net.minecraft.world.entity.HumanoidArm;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.item.MapItem;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;

/** Submits filled maps using the third-person hand transform. */
@Mixin(ItemInHandLayer.class)
public abstract class ReadableMapLayerMixin<
        MapEntityState extends ArmedEntityRenderState,
        MapEntityModel extends EntityModel<MapEntityState> & ArmedModel<MapEntityState>> extends RenderLayer<MapEntityState, MapEntityModel> {

    protected ReadableMapLayerMixin(RenderLayerParent<MapEntityState, MapEntityModel> mapLayerParent) {
        super(mapLayerParent);
    }

    @Inject(method = "submitArmWithItem", at = @At("HEAD"), cancellable = true)
    private void thirdpersonreadablemaps$submitReadableMap(
            MapEntityState mapEntityState,
            ItemStackRenderState unusedMapItemState,
            ItemStack readableMapStack,
            HumanoidArm mapHoldingArm,
            PoseStack readableMapTransform,
            SubmitNodeCollector readableMapQueue,
            int readableMapPackedLight,
            CallbackInfo readableMapCallback) {

        if (!(readableMapStack.getItem() instanceof MapItem) || Minecraft.getInstance().level == null) {
            return;
        }

        MapEntityModel readableMapModel = this.getParentModel();
        if (!(readableMapModel instanceof HumanoidModel<?> readableMapHumanoid)) {
            return;
        }
        boolean isMapInRightHand = mapHoldingArm == HumanoidArm.RIGHT;
        if ((isMapInRightHand && !readableMapHumanoid.rightArm.visible) || (!isMapInRightHand && !readableMapHumanoid.leftArm.visible)) {
            return;
        }

        boolean isMapInMainHand = mapHoldingArm == mapEntityState.mainArm;
        ItemStack otherHandMapStack = isMapInRightHand ? mapEntityState.leftHandItemStack : mapEntityState.rightHandItemStack;
        boolean useCompactMap = !isMapInMainHand || !otherHandMapStack.isEmpty();

        readableMapTransform.pushPose();
        try {
            readableMapModel.translateToHand(mapEntityState, mapHoldingArm, readableMapTransform);
            readableMapTransform.rotateDegrees(Axis.XP, -90.0f);
            readableMapTransform.rotateDegrees(Axis.YP, isMapInMainHand ? 205.0f : 200.0f);
            if (isMapInMainHand) {
                readableMapTransform.rotateDegrees(Axis.ZP, 10.0f);
            }
            float mapHandSign = isMapInRightHand ? 1f : -1f;
            readableMapTransform.translate(mapHandSign / 16f, isMapInMainHand ? (useCompactMap ? 0.09 : 0.24) : 0.125, -0.625);

            ReadableMapSurface.submitReadableMap(
                    readableMapTransform, readableMapQueue, readableMapStack, readableMapPackedLight,
                    useCompactMap, isMapInMainHand && mapEntityState.mainArm == HumanoidArm.LEFT);
        } finally {
            readableMapTransform.popPose();
        }

        // The map submission replaces the ordinary carried-item submission.
        readableMapCallback.cancel();
    }
}
