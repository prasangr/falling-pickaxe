import pygame
import math
import pymunk
import pymunk.autogeometry
from chunk import chunks
from constants import BLOCK_SIZE, CHUNK_WIDTH, FRAMERATE
from config import config

# Read here, not passed in: overheat fires from inside the collision
# handler, which has no route back to main's config values.
OVERHEAT_MS = 1000 * config.get("OVERHEAT_DURATION_SECONDS", 20)
import random

def rotate_point(x, y, angle):
    """Rotate a point (x, y) by angle (in radians) around the origin (0, 0)."""
    cos_angle = math.cos(angle)
    sin_angle = math.sin(angle)
    new_x = cos_angle * x - sin_angle * y
    new_y = sin_angle * x + cos_angle * y
    return new_x, new_y

def rotate_vertices(vertices, angle):
        rotated_vertices = []

        for vertex in vertices:
            # Rotate each vertex based on the body's angle
            rotated_x, rotated_y = rotate_point(vertex[0] - BLOCK_SIZE / 2 , vertex[1] - BLOCK_SIZE / 2, angle)

            # Offset each rotated vertex by the body's position
            rotated_vertices.append((rotated_x, rotated_y))
        
        return rotated_vertices

class Pickaxe:
    def __init__(self, space, x, y, texture, sound_manager, damage=2, velocity=0, rotation=0, mass=100):
        self.texture = texture
        self.velocity = velocity
        self.rotation = rotation
        self.space = space
        self.damage = damage
        self.is_enlarged = False

        # Spin mode. The multiplier lives here rather than folded into
        # self.damage because pickaxe()/random_pickaxe() reassign damage from
        # the material table -- a skin change mid-spin would eat the boost.
        self.damage_multiplier = 1
        self.spin_end_time = 0
        self.spin_rate = 0
        self.spin_gravity = 1

        # Lava/water states. Both are timestamps, both scale the same two
        # numbers (dig damage, fall ceiling), so they compose with spin.
        self.overheated_until = 0
        # Set each frame by main from the water pool: buoyancy applies only
        # while the axe is actually inside the water, not for a flat duration.
        self.submerged = False

        vertices = rotate_vertices([
                    (0, 0), # A
                    (10, 0), # C
                    (110, 100), # D
                    (100, 110), # E
                    (0, 10), # F
                    (110, 110), # G
                ], -math.pi / 2)
        
        vertices2 = rotate_vertices([
                    (110, 30), # H
                    (120, 40), # I
                    (120, 90), # J
                    (100, 90), # K
                    (100, 40), # L
                    (110, 100), # D
                ], -math.pi / 2)
        
        vertices3 = rotate_vertices([
                    (30, 110), # M
                    (40, 120), # N
                    (90, 120), # O
                    (40, 100), # P
                    (90, 100), # Q
                    (100, 110), # E
                ], -math.pi / 2)

        inertia = pymunk.moment_for_poly(mass, vertices)
        self.body = pymunk.Body(mass, inertia)
        self.body.position = (x, y)
        self.body.angle = math.radians(rotation)

        self.sound_manager = sound_manager

        self.shapes = []
        for vertices in [vertices, vertices2, vertices3]:
            shape = pymunk.Poly(self.body, vertices)
            shape.elasticity = 0.7
            shape.friction = 0.7
            shape.collision_type = 1  # Identifier for collisions
            self.shapes.append(shape)

        self.space.add(self.body, *self.shapes)

        # Add collision handler for pickaxe & blocks
        handler = space.add_collision_handler(1, 2)  # (Pickaxe type, Block type)
        handler.post_solve = self.on_collision

    def on_collision(self, arbiter, space, data):
        """Handles collision with blocks: Reduce HP or destroy the block."""
        block_shape = arbiter.shapes[1]  # Get the block shape
        block = block_shape.block_ref  # Get the actual block instance

        block.first_hit_time = pygame.time.get_ticks()  
        block.last_heal_time = block.first_hit_time

        block.hp -= self.damage * self.damage_multiplier * self.heat_factor()

        if block.name == "lava":
            self.overheat()

        if (block.name == "grass_block" or block.name == "dirt"):
            self.sound_manager.play_sound("grass" + str(random.randint(1, 4)))
        else:
            self.sound_manager.play_sound("stone" + str(random.randint(1, 4)))

        # Add small random rotation on hit
        self.body.angle += random.choice([0.01, -0.01])

    def random_pickaxe(self, texture_atlas, atlas_items): 
        """Randomly change the pickaxe's properties."""

        pickaxe_name = random.choice(list(atlas_items["pickaxe"].keys()))
        self.texture = texture_atlas.subsurface(atlas_items["pickaxe"][pickaxe_name])
        print("Setting pickaxe to:", pickaxe_name)

        if self.is_enlarged:
            # Scale up texture
            new_size = (BLOCK_SIZE * 3, BLOCK_SIZE * 3)
            self.texture = pygame.transform.scale(self.texture, new_size)

        if(pickaxe_name =="wooden_pickaxe"):  
            self.damage = 2
        elif(pickaxe_name =="stone_pickaxe"):
            self.damage = 4
        elif(pickaxe_name =="iron_pickaxe"):
            self.damage = 6
        elif(pickaxe_name =="golden_pickaxe"):
            self.damage = 8
        elif(pickaxe_name =="diamond_pickaxe"):
            self.damage = 10
        elif(pickaxe_name =="netherite_pickaxe"):
            self.damage = 12

    def pickaxe(self, name, texture_atlas, atlas_items):
        """Set the pickaxe's properties based on its name."""

        self.texture = texture_atlas.subsurface(atlas_items["pickaxe"][name])
        print("Setting pickaxe to:", name)

        if self.is_enlarged:
            # Scale up texture
            new_size = (BLOCK_SIZE * 3, BLOCK_SIZE * 3)
            self.texture = pygame.transform.scale(self.texture, new_size)

        if(name =="wooden_pickaxe"):  
            self.damage = 2
        elif(name =="stone_pickaxe"):
            self.damage = 4
        elif(name =="iron_pickaxe"):
            self.damage = 6
        elif(name =="golden_pickaxe"):
            self.damage = 8
        elif(name =="diamond_pickaxe"):
            self.damage = 10
        elif(name =="netherite_pickaxe"):
            self.damage = 12

    def update(self):
        """Apply gravity, update movement, check collisions, and rotate."""
        # Manually limit the falling speed (terminal velocity). Spin mode
        # raises the ceiling too, otherwise the extra pull just saturates here
        # and the heavier fall is invisible.
        terminal = 1000 * (self.spin_gravity if self.spin_end_time else 1)
        if self.overheated_until:
            terminal *= 0.5      # Burned: the fall drags.
        if self.submerged:
            terminal *= 0.35     # In water: it sinks rather than falls.
        if self.body.velocity.y > terminal:
            self.body.velocity = (self.body.velocity.x, terminal)

        # --- Bounding box check for bedrock collision ---
        # Gather all vertices from all shapes, transformed to world coordinates
        all_vertices = []
        for shape in self.shapes:
            for v in shape.get_vertices():
                # Transform local vertex to world coordinates
                world_v = self.body.local_to_world(v)
                all_vertices.append(world_v)

        min_x = min(v.x for v in all_vertices)
        max_x = max(v.x for v in all_vertices)

        left_limit = BLOCK_SIZE
        right_limit = BLOCK_SIZE * (CHUNK_WIDTH - 1)

        # If any part is left of the left limit, shift the body right
        if min_x < left_limit:
            dx = left_limit - min_x
            self.body.position = (self.body.position.x + dx, self.body.position.y)

        # If any part is right of the right limit, shift the body left
        if max_x > right_limit:
            dx = max_x - right_limit
            self.body.position = (self.body.position.x - dx, self.body.position.y)

        # If pickaxe is enlarged, check if time is up
        if hasattr(self, "enlarge_end_time") and pygame.time.get_ticks() > self.enlarge_end_time:
            self.reset_size()
            self.is_enlarged = False

        now = pygame.time.get_ticks()
        if self.overheated_until and now > self.overheated_until:
            self.overheated_until = 0
        if self.submerged:
            # Buoyancy: cancel most of gravity, the mirror of spin's extra
            # pull, so the axe drifts down instead of dropping.
            lift = self.space.gravity.y * 0.75 / FRAMERATE
            self.body.velocity = (self.body.velocity.x,
                                  self.body.velocity.y - lift)

        # Spin mode: hold the angular velocity every frame, since collisions
        # and pymunk's damping both bleed it off otherwise.
        if self.spin_end_time:
            if pygame.time.get_ticks() > self.spin_end_time:
                self.spin_end_time = 0
                self.damage_multiplier = 1
                self.spin_gravity = 1
                self.body.angular_velocity = 0
            else:
                self.body.angular_velocity = self.spin_rate
                # Extra gravity for this body only -- raising space.gravity
                # would drag every TNT and block down with it.
                extra = self.space.gravity.y * (self.spin_gravity - 1) / FRAMERATE
                self.body.velocity = (self.body.velocity.x,
                                      self.body.velocity.y + extra)

    def draw(self, screen, camera):
        """Draw the pickaxe at its current position."""
        rotated_image = pygame.transform.rotate(self.texture, -math.degrees(self.body.angle))  # Convert to degrees
        rect = rotated_image.get_rect(center=(self.body.position.x, self.body.position.y))
        rect.y -= camera.offset_y
        rect.x -= camera.offset_x
        screen.blit(rotated_image, rect)

    def heat_factor(self):
        """0.5 while overheated, 1 otherwise. Kept separate from
        damage_multiplier so SPIN's 3x and a lava burn stack instead of
        overwriting each other."""
        return 0.5 if self.overheated_until else 1.0

    def overheat(self, duration=OVERHEAT_MS):
        """Lava burn: half damage and a slower fall. Self-heals, so a quiet
        chat can never leave the stream stuck."""
        if not self.overheated_until:
            print("Lava burned the pickaxe")
        # Touching lava again refreshes the burn rather than extending it.
        self.overheated_until = pygame.time.get_ticks() + duration

    def douse(self):
        """The !water command. Cures a burn, or floods the shaft if nothing
        is burning -- water has to do something either way."""
        if self.overheated_until:
            self.overheated_until = 0
            print("Water doused the pickaxe")
            return "cured"
        print("Water: pouring in")
        return "wet"

    def spin(self, duration=10000, multiplier=3, rate=12, gravity=3):
        """Whirl the pickaxe and multiply its dig damage for `duration` ms."""
        print("Spinning pickaxe")
        self.spin_rate = rate
        self.spin_gravity = gravity
        self.damage_multiplier = multiplier
        # Re-triggering extends rather than restarts, matching enlarge().
        now = pygame.time.get_ticks()
        self.spin_end_time = max(self.spin_end_time, now) + duration

    def enlarge(self, duration=5000):
        """Temporarily makes the pickaxe 3 times bigger with a larger hitbox."""
        print("Enlarging pickaxe")

        # If already enlarged, just extend the duration.
        if hasattr(self, "is_enlarged") and self.is_enlarged:
            self.enlarge_end_time += duration
            return

        # Not enlarged yet, so store original texture and shapes
        self.original_texture = self.texture.copy()
        self.original_shapes = self.shapes[:]  # Store original hitbox shapes
        self.is_enlarged = True

        # Scale up texture using the original texture.
        new_size = (BLOCK_SIZE * 3, BLOCK_SIZE * 3)
        self.texture = pygame.transform.scale(self.original_texture, new_size)

        # Scale up hitbox:
        self.space.remove(*self.shapes)  # Remove current shapes
        new_shapes = []
        for shape in self.original_shapes:
            # Get vertices from original shape and scale them by 3.
            scaled_vertices = [(x * 3, y * 3) for x, y in shape.get_vertices()]
            new_shape = pymunk.Poly(self.body, scaled_vertices)
            new_shape.elasticity = shape.elasticity
            new_shape.friction = shape.friction
            new_shape.collision_type = shape.collision_type
            new_shapes.append(new_shape)
        self.shapes = new_shapes
        self.space.add(*self.shapes)  # Add new enlarged shapes

        # Track when the enlargement effect should end
        self.enlarge_end_time = pygame.time.get_ticks() + duration

    def reset_size(self):
        """Restore the pickaxe to its original size."""
        if hasattr(self, "original_shapes"):
            # Restore texture using the stored original.
            self.texture = self.original_texture.copy()

            # Reset hitbox: remove enlarged shapes and add back the original shapes.
            self.space.remove(*self.shapes)
            self.shapes = self.original_shapes[:]
            self.space.add(*self.shapes)
            self.is_enlarged = False

            del self.enlarge_end_time  # Remove the enlargement timer


def spawn_clones(space, original, count=15, spread=None):
    """Temporary duplicate pickaxes for the MULTIPLY command.

    Clones share the original's texture and damage. They are ordinary bodies,
    so they scatter and dig their own tunnels; Pickaxe.update() clamps them to
    the shaft walls, so none can wander out of the world.
    """
    spread = spread if spread is not None else BLOCK_SIZE * 4
    clones = []
    for _ in range(count):
        dx = random.uniform(-spread, spread)
        dy = -random.uniform(BLOCK_SIZE, BLOCK_SIZE * 5)
        clone = Pickaxe(space,
                        original.body.position.x + dx,
                        original.body.position.y + dy,
                        original.texture, original.sound_manager,
                        damage=original.damage)
        clone.body.angle = random.uniform(0, 2 * math.pi)
        clones.append(clone)
    return clones


def despawn_clones(space, clones, original=None):
    """Remove clones. Call this outside space.step(), never from a collision
    callback -- removing bodies mid-step is how pymunk segfaults.

    Every Pickaxe.__init__ rebinds the (pickaxe, block) handler, so after
    spawning it points at the last clone. Rebinding to the original here stops
    the real pickaxe routing its hits through a body that no longer exists.
    """
    for clone in clones:
        space.remove(clone.body, *clone.shapes)
    clones.clear()
    if original is not None:
        space.add_collision_handler(1, 2).post_solve = original.on_collision
