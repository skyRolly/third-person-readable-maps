package tech.rolly.thirdpersonreadablemaps.mixin;

import tech.rolly.thirdpersonreadablemaps.ReadableMapSurface;
import com.mojang.blaze3d.vertex.PoseStack;
import com.mojang.math.Axis;
import net.minecraft.client.Minecraft;
import net.minecraft.client.model.ArmedModel;
import net.minecraft.client.model.EntityModel;
import net.minecraft.client.model.HumanoidModel;
import net.minecraft.client.renderer.MultiBufferSource;
import net.minecraft.client.renderer.entity.RenderLayerParent;
import net.minecraft.client.renderer.entity.layers.ItemInHandLayer;
import net.minecraft.client.renderer.entity.layers.RenderLayer;
import net.minecraft.world.entity.LivingEntity;
import net.minecraft.client.renderer.block.model.ItemTransforms;
import net.minecraft.world.entity.HumanoidArm;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.item.MapItem;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;

/** Renders filled maps using the third-person hand transform. */
@Mixin(ItemInHandLayer.class)
public abstract class ReadableMapLayerMixin<
        MapEntityState extends LivingEntity,
        MapEntityModel extends EntityModel<MapEntityState> & ArmedModel> extends RenderLayer<MapEntityState, MapEntityModel> {

    protected ReadableMapLayerMixin(RenderLayerParent<MapEntityState, MapEntityModel> mapLayerParent) {
        super(mapLayerParent);
    }

    @Inject(method = "renderArmWithItem", at = @At("HEAD"), cancellable = true)
    private void thirdpersonreadablemaps$submitReadableMap(
            MapEntityState mapEntityState,
            ItemStack readableMapStack,
            ItemTransforms.TransformType unusedContext,
            HumanoidArm mapHoldingArm,
            PoseStack readableMapTransform,
            MultiBufferSource readableMapQueue,
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

        boolean isMapInMainHand = mapHoldingArm == mapEntityState.getMainArm();
        ItemStack otherHandMapStack = isMapInMainHand ? mapEntityState.getOffhandItem() : mapEntityState.getMainHandItem();
        boolean useCompactMap = !isMapInMainHand || !otherHandMapStack.isEmpty();

        readableMapTransform.pushPose();
        try {
            readableMapModel.translateToHand(mapHoldingArm, readableMapTransform);
            ReadableMapSurface.rotate(readableMapTransform, Axis.XP.rotationDegrees(-90.0f));
            ReadableMapSurface.rotate(readableMapTransform, Axis.YP.rotationDegrees(isMapInMainHand ? 205.0f : 200.0f));
            if (isMapInMainHand) {
                ReadableMapSurface.rotate(readableMapTransform, Axis.ZP.rotationDegrees(10.0f));
            }
            float mapHandSign = isMapInRightHand ? 1f : -1f;
            readableMapTransform.translate(mapHandSign / 16f, isMapInMainHand ? (useCompactMap ? 0.09 : 0.24) : 0.125, -0.625);

            ReadableMapSurface.submitReadableMap(
                    readableMapTransform, readableMapQueue, readableMapStack, readableMapPackedLight,
                    useCompactMap, isMapInMainHand && mapEntityState.getMainArm() == HumanoidArm.LEFT);
        } finally {
            readableMapTransform.popPose();
        }

        // The map submission replaces the ordinary carried-item submission.
        readableMapCallback.cancel();
    }
}
