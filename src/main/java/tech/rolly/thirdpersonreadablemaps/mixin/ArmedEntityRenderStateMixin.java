package tech.rolly.thirdpersonreadablemaps.mixin;

import net.minecraft.client.renderer.entity.state.ArmedEntityRenderState;
import net.minecraft.client.renderer.item.ItemModelResolver;
import net.minecraft.world.entity.HumanoidArm;
import net.minecraft.world.entity.LivingEntity;
import net.minecraft.world.item.ItemStack;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.Unique;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;
import tech.rolly.thirdpersonreadablemaps.ReadableMapHands;

/** Carries the live entity's hand stacks into the detached render state. */
@Mixin(ArmedEntityRenderState.class)
public abstract class ArmedEntityRenderStateMixin implements ReadableMapHands {
    @Unique private ItemStack thirdpersonreadablemaps$right = ItemStack.EMPTY;
    @Unique private ItemStack thirdpersonreadablemaps$left = ItemStack.EMPTY;

    @Inject(method = "extractArmedEntityRenderState", at = @At("TAIL"))
    private static void thirdpersonreadablemaps$captureHands(
            LivingEntity entity, ArmedEntityRenderState state, ItemModelResolver resolver, CallbackInfo callback) {
        ArmedEntityRenderStateMixin hands = (ArmedEntityRenderStateMixin) (Object) state;
        // The same render-state object can be reused for another entity or frame.
        hands.thirdpersonreadablemaps$right = entity.getItemHeldByArm(HumanoidArm.RIGHT).copy();
        hands.thirdpersonreadablemaps$left = entity.getItemHeldByArm(HumanoidArm.LEFT).copy();
    }

    @Override
    public ItemStack thirdpersonreadablemaps$getStack(HumanoidArm arm) {
        return arm == HumanoidArm.RIGHT ? thirdpersonreadablemaps$right : thirdpersonreadablemaps$left;
    }
}
