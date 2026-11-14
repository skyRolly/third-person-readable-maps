package tech.rolly.thirdpersonreadablemaps.mixin;

import com.mojang.blaze3d.platform.GlStateManager;
import net.minecraft.client.MinecraftClient;
import net.minecraft.client.render.entity.feature.FeatureRenderer;
import net.minecraft.client.render.entity.feature.FeatureRendererContext;
import net.minecraft.client.render.entity.feature.HeldItemFeatureRenderer;
import net.minecraft.client.render.entity.model.BipedEntityModel;
import net.minecraft.client.render.entity.model.EntityModel;
import net.minecraft.client.render.entity.model.ModelWithArms;
import net.minecraft.client.render.model.json.ModelTransformation;
import net.minecraft.entity.LivingEntity;
import net.minecraft.item.FilledMapItem;
import net.minecraft.item.ItemStack;
import net.minecraft.util.Arm;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;
import tech.rolly.thirdpersonreadablemaps.ReadableMapSurface;

/** Renders maps inside the 1.14 held-item arm transform. */
@Mixin(HeldItemFeatureRenderer.class)
public abstract class ReadableMapLayerMixin<T extends LivingEntity, M extends EntityModel<T> & ModelWithArms>
        extends FeatureRenderer<T, M> {
    protected ReadableMapLayerMixin(FeatureRendererContext<T, M> context) { super(context); }

    @Inject(method = "method_4192", at = @At("HEAD"), cancellable = true)
    private void thirdpersonreadablemaps$drawMap(T entity, ItemStack stack,
            ModelTransformation.Type unusedContext, Arm holdingArm, CallbackInfo callback) {
        if (!(stack.getItem() instanceof FilledMapItem) || MinecraftClient.getInstance().world == null) return;
        M model = getContextModel();
        if (!(model instanceof BipedEntityModel<?>)) return;
        BipedEntityModel<?> biped = (BipedEntityModel<?>) model;
        boolean rightHand = holdingArm == Arm.RIGHT;
        if ((rightHand && !biped.rightArm.visible) || (!rightHand && !biped.leftArm.visible)) return;
        boolean mainHand = holdingArm == entity.getMainArm();
        ItemStack other = mainHand ? entity.getOffHandStack() : entity.getMainHandStack();
        boolean compact = !mainHand || !other.isEmpty();
        GlStateManager.pushMatrix();
        try {
            model.setArmAngle(0.0625f, holdingArm);
            if (entity.isInSneakingPose()) GlStateManager.translatef(0f, 0.2f, 0f);
            GlStateManager.rotatef(-90f, 1f, 0f, 0f);
            GlStateManager.rotatef(mainHand ? 205f : 200f, 0f, 1f, 0f);
            if (mainHand) GlStateManager.rotatef(10f, 0f, 0f, 1f);
            GlStateManager.translatef((rightHand ? 1f : -1f) / 16f,
                    mainHand ? (compact ? 0.09f : 0.24f) : 0.125f, -0.625f);
            ReadableMapSurface.draw(stack, compact, mainHand && entity.getMainArm() == Arm.LEFT);
        } finally {
            GlStateManager.popMatrix();
        }
        callback.cancel();
    }
}
