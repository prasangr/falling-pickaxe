import pygame
import pymunk
from constants import BLOCK_SIZE
import random

# Block name -> (HUD counter key, min drop, max drop).
# Quantities preserve the original per-ore behaviour exactly.
ORE_DROPS = {
    "coal_ore":     ("coal", 1, 1),
    "iron_ore":     ("iron_ingot", 1, 1),
    "copper_ore":   ("copper_ingot", 1, 1),
    "gold_ore":     ("gold_ingot", 1, 1),
    "diamond_ore":  ("diamond", 1, 1),
    "emerald_ore":  ("emerald", 1, 1),
    "redstone_ore": ("redstone", 4, 5),
    "lapis_ore":    ("lapis_lazuli", 4, 8),
}

def remove_from_world(space, body, *shapes):
    """Take an object out of the physics world so that it is safe to free.

    Call this outside space.step(). Once removed, a shape no longer tells its
    body it exists, so if Python frees the body first the shape is left pointing
    at freed memory and crashes the game when it is freed in turn.
    """
    space.remove(body, *shapes)
    for shape in shapes:
        shape.body = None


class Block:
    def __init__(self, space, x, y, name, texture_atlas, atlas_items):
        if name == "bedrock":
            self.max_hp = 1000000000
            self.hp = 1000000000
        elif name == "lava":
            # Breaks easily; the cost is touching it, not mining it.
            self.max_hp = 4
            self.hp = 4
        elif name == "stone":
            self.max_hp = 10
            self.hp = 10
        elif name == "andesite":
            self.hp = 10
            self.max_hp = 10
        elif name == "diorite":
            self.hp = 10
            self.max_hp = 10
        elif name == "granite":
            self.hp = 10
            self.max_hp = 10
        elif name == "coal_ore":
            self.hp = 15
            self.max_hp = 15
        elif name == "iron_ore":
            self.hp = 15
            self.max_hp = 15
        elif name == "copper_ore":
            self.hp = 15
            self.max_hp = 15
        elif name == "gold_ore":
            self.hp = 20
            self.max_hp = 20
        elif name == "diamond_ore":
            self.hp = 20
            self.max_hp = 20
        elif name == "emerald_ore":
            self.hp = 20
            self.max_hp = 20
        elif name == "obsidian":
            self.hp = 100
            self.max_hp = 100
        elif name == "redstone_ore":
            self.hp = 15
            self.max_hp = 15
        elif name == "lapis_ore":
            self.hp = 15
            self.max_hp = 15
        elif name == "mossy_cobblestone":
            self.hp = 12
            self.max_hp = 12
        elif name == "cobblestone":
            self.hp = 22
            self.max_hp = 22
        else:
            self.hp = 1
            self.max_hp = 1

        self.texture_atlas = texture_atlas
        self.atlas_items = atlas_items

        rect = atlas_items["block"][name]  
        self.texture = texture_atlas.subsurface(rect)

        width, height = self.texture.get_size()

        # Create a static physics body (doesn't move)
        self.body = pymunk.Body(body_type=pymunk.Body.STATIC)
        self.body.position = (x + BLOCK_SIZE//2, y + BLOCK_SIZE//2)

        # Create a hitbox
        self.shape = pymunk.Poly.create_box(self.body, (width, height))
        self.shape.elasticity = 1  # No bounce
        self.shape.collision_type = 2 # Identifier for collisions
        self.shape.friction = 1
        self.shape.block_ref = self  # Reference to the block object

        self.destroyed = False

        self.name = name

        self.last_heal_time = None  # Track time of last healing (None initially)
        self.heal_interval = 5000  # Heal every 5 seconds (5000 ms)
        self.first_hit_time = None  # Track the time when the block was first hit

        space.add(self.body, self.shape)

    def update(self, space, hud):
        """Update block state"""

        # Check if the block was hit for the first time
        if self.first_hit_time is None and self.hp < self.max_hp:
            self.first_hit_time = pygame.time.get_ticks()
            self.last_heal_time = self.first_hit_time

        # Check if the block has been hit before and start healing 5 seconds after it was first hit
        if self.first_hit_time is not None:
            current_time = pygame.time.get_ticks()

            # Start healing 5 seconds after the block was first hit
            if current_time - self.first_hit_time >= 5000:
                # Heal 20% of the max HP every 5 seconds (but not exceeding max_hp)
                if current_time - self.last_heal_time >= self.heal_interval:
                    healing_amount = self.max_hp * 0.2
                    self.hp = min(self.hp + healing_amount, self.max_hp)

                    # Reset the healing timer after each heal
                    self.last_heal_time = current_time
        
        if self.hp <= 0 and not self.destroyed:
            self.destroyed = True
            remove_from_world(space, self.body, self.shape)

            drop = ORE_DROPS.get(self.name)
            if drop:
                hud.add_ore(*drop)

    def draw(self, screen, camera):
        """Draw block at its position"""

        if(self.destroyed):
            return

        block_x = self.body.position.x - camera.offset_x - BLOCK_SIZE // 2
        block_y = self.body.position.y - camera.offset_y - BLOCK_SIZE // 2

        screen.blit(self.texture, (block_x, block_y))

        # Determine the destroy stage (0-9) based on hp percentage
        if self.hp < self.max_hp:
            damage_stage = int((1 - (self.hp / self.max_hp)) * 9)  # Scale hp to 0-9 range
            damage_stage = min(damage_stage, 9)  # Ensure it doesn't exceed stage_9
            
            # Draw the destroy stage overlay
            destroy_texture = self.texture_atlas.subsurface(
                self.atlas_items["destroy_stage"][f"destroy_stage_{damage_stage}"]
            )
            screen.blit(destroy_texture, (block_x, block_y))