package tech.rolly.thirdpersonreadablemaps;

import net.minecraft.world.entity.HumanoidArm;
import net.minecraft.world.item.ItemStack;

/** Hand stacks captured at the same time as vanilla's armed-entity render state. */
public interface ReadableMapHands {
    ItemStack thirdpersonreadablemaps$getStack(HumanoidArm arm);
}
