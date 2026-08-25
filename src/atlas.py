import os
import random

import pygame

# --- Block colour grading -------------------------------------------------
# Applied once at atlas build, so drawing costs nothing extra at runtime.
# Each row is (multiply, add): multiply pushes the hue, add puts back the
# brightness that multiplying costs. Both are RGB-only, so alpha and the
# pixel-art edges survive untouched.
#
# Ores saturate hard toward their own colour; the stone family gets only a
# warm lift and stays darker, so the ores read as treasure against it.
# These values are eyeballed -- tune the rows, not the code.
BLOCK_TINTS = {
    # Ores: loud on purpose.
    "coal_ore":          ((150, 150, 165), (35, 35, 45)),
    "iron_ore":          ((255, 225, 195), (30, 20, 10)),
    "copper_ore":        ((255, 165,  95), (40, 15,  0)),
    "gold_ore":          ((255, 205,  70), (45, 30,  0)),
    "diamond_ore":       (( 90, 245, 255), ( 0, 35, 40)),
    "emerald_ore":       (( 80, 255, 130), ( 0, 40, 10)),
    "redstone_ore":      ((255,  75,  75), (50,  0,  0)),
    "lapis_ore":         (( 90, 130, 255), ( 0, 10, 50)),
    # Stone family: muted backdrop, just a touch of warmth.
    "stone":             ((225, 215, 205), (12, 10,  8)),
    "cobblestone":       ((225, 215, 205), (12, 10,  8)),
    "mossy_cobblestone": ((205, 230, 195), ( 8, 16,  8)),
    "andesite":          ((215, 218, 228), (10, 10, 14)),
    "diorite":           ((235, 230, 230), (14, 12, 12)),
    "granite":           ((240, 195, 175), (18, 10,  6)),
    "obsidian":          ((175, 140, 230), (18, 10, 30)),
}


def apply_block_tints(atlas_surface, textures):
    """Colour-grade terrain blocks in place on the finished atlas."""
    for name, (mult, add) in BLOCK_TINTS.items():
        rect = textures["block"].get(name)
        if rect is None:
            continue  # Texture pack without this block: leave it alone.
        region = atlas_surface.subsurface(rect)  # Shares pixels with the atlas.
        region.fill(mult, special_flags=pygame.BLEND_RGB_MULT)
        region.fill(add, special_flags=pygame.BLEND_RGB_ADD)


def make_lava_tile(size=16):
    """A lava tile, drawn rather than shipped -- there is no lava.png.

    Horizontal bands of molten colour with per-pixel jitter: at block scale it
    reads as churning lava, and it costs no asset.
    """
    rng = random.Random(4242)  # Fixed seed: the same tile every run.
    tile = pygame.Surface((size, size), pygame.SRCALPHA)
    bands = [(255, 236, 120), (255, 176,  40), (238, 108,  20), (196,  56,  12)]
    for y in range(size):
        base = bands[int(y / size * len(bands)) % len(bands)]
        for x in range(size):
            j = rng.randint(-22, 22)
            tile.set_at((x, y), tuple(max(0, min(255, c + j)) for c in base) + (255,))
    return tile


def create_texture_atlas(asset_path):
    categories = ['block', 'item', 'destroy_stage', 'particle', "pickaxe"]
    textures = {category: {} for category in categories}
    images = []
    positions = {}
    atlas_width = 512

    # Load images and track dimensions
    x_offset, y_offset, row_height = 0, 0, 0
    for category in categories:
        folder_path = os.path.join(asset_path, category)
        if not os.path.exists(folder_path):
            print("Folder not found: ", folder_path)
            continue
        
        for filename in sorted(os.listdir(folder_path)):
            if filename.endswith(".png"):
                img_path = os.path.join(folder_path, filename)
                image = pygame.image.load(img_path).convert_alpha()
                img_width, img_height = image.get_size()
                
                # Wrap to new row if necessary
                if x_offset + img_width > atlas_width:  # Max texture width
                    x_offset = 0
                    y_offset += row_height
                    row_height = 0
                
                # Store texture coordinates
                texture_name = filename.rsplit(".", 1)[0]
                textures[category][texture_name] = (x_offset, y_offset, img_width, img_height)
                
                images.append((image, (x_offset, y_offset)))
                
                x_offset += img_width
                row_height = max(row_height, img_height)
    
    # Lava has no PNG, so it joins the packing flow here as a synthetic image.
    lava = make_lava_tile()
    lw, lh = lava.get_size()
    if x_offset + lw > atlas_width:
        x_offset = 0
        y_offset += row_height
        row_height = 0
    textures["block"]["lava"] = (x_offset, y_offset, lw, lh)
    images.append((lava, (x_offset, y_offset)))
    x_offset += lw
    row_height = max(row_height, lh)

    # Determine atlas size
    atlas_height = y_offset + row_height
    atlas_surface = pygame.Surface((atlas_width, atlas_height), pygame.SRCALPHA)
    
    # Blit images onto atlas
    for image, pos in images:
        atlas_surface.blit(image, pos)

    apply_block_tints(atlas_surface, textures)

    return atlas_surface, textures
