
import time
import pygame
import pymunk
import pymunk.pygame_util
from config import config
from atlas import create_texture_atlas
from pathlib import Path
from chunk import get_block, clean_chunks, chunks
from constants import BLOCK_SCALE_FACTOR, BLOCK_SIZE, CHUNK_HEIGHT, CHUNK_WIDTH, INTERNAL_HEIGHT, INTERNAL_WIDTH, FRAMERATE
from pickaxe import Pickaxe, spawn_clones, despawn_clones
from camera import Camera
from sound import SoundManager
from tnt import Tnt, MegaTnt
import threading
import random
import os  # Needed for file operations
from hud import Hud
from events import EventManager
import daylight
from weather import trigger_quake, Storm, Water

# Track key states
key_t_pressed = False
key_m_pressed = False

# Global Queues
tnt_queue = []
tnt_superchat_queue = []
fast_slow_queue = []
big_queue = []
spin_queue = []
multiply_queue = []
quake_queue = []
storm_queue = []
water_queue = []
pickaxe_queue = []
mega_tnt_queue = []

# Live stream stats shown on the HUD. Seeded from config, incremented by
# SUB lines, and overridden absolutely by SUBS lines.
stream_stats = {"subs": config.get("SUB_COUNT_BASE", 0)}

# ==========================================
# FILE WATCHER (The Listener)
# ==========================================
def check_command_file():
    """
    Reads 'commands.txt' for new instructions.
    Format in file: COMMAND:USER:VALUE
    """
    cmd_file = Path(__file__).parent.parent / "commands.txt"
    
    # Create file if it doesn't exist
    if not cmd_file.exists():
        with open(cmd_file, 'w') as f: f.write("")
        return

    try:
        with open(cmd_file, 'r') as f:
            lines = f.readlines()
        
        # If file is empty, do nothing
        if not lines:
            return

        # Process commands
        for line in lines:
            line = line.strip()
            if not line: continue
            
            print(f"[File] Read: {line}")
            parts = line.split(':')
            command = parts[0].upper()
            user = parts[1] if len(parts) > 1 else "StreamerBot"
            value = parts[2] if len(parts) > 2 else ""

            if command == "TNT":
                tnt_queue.append(user)
            elif command == "SUB":
                mega_tnt_queue.append(user)
                stream_stats["subs"] += 1
            elif command == "SUBS":
                # Optional absolute sync, e.g. "SUBS:system:165909".
                # A malformed count is ignored; the baseline stands.
                try:
                    stream_stats["subs"] = int(value)
                except ValueError:
                    print(f"Ignoring malformed SUBS value: {value!r}")
            elif command == "SUPER":
                tnt_superchat_queue.append((user, value))
            elif command == "SPEED":
                if "FAST" in value.upper():
                    fast_slow_queue.append((user, "Fast"))
                elif "SLOW" in value.upper():
                    fast_slow_queue.append((user, "Slow"))
            elif command == "BIG":
                big_queue.append(user)
            elif command == "SPIN":
                spin_queue.append(user)
            elif command == "MULTIPLY":
                multiply_queue.append(user)
            elif command == "QUAKE":
                quake_queue.append(user)
            elif command == "STORM":
                storm_queue.append(user)
            elif command == "WATER":
                water_queue.append(user)
            
            # --- NUKE COMMAND ---
            elif command == "NUKE":
                # 1. Make Pickaxe Big
                big_queue.append(user)
                # 2. Spawn 30 TNTs rapidly
                for _ in range(30):
                    tnt_queue.append(user)

            elif command == "PICKAXE":
                p_map = {
                    "WOOD": "wooden_pickaxe", "STONE": "stone_pickaxe",
                    "IRON": "iron_pickaxe", "GOLD": "golden_pickaxe",
                    "DIAMOND": "diamond_pickaxe", "NETHERITE": "netherite_pickaxe"
                }
                p_type = p_map.get(value.upper())
                if p_type:
                    pickaxe_queue.append((user, p_type))

        # Clear file after reading
        with open(cmd_file, 'w') as f:
            f.write("")
            
    except Exception as e:
        print(f"File Read Error: {e}")

# ==========================================
# GAME LOOP
# ==========================================
def game():
    window_width = int(INTERNAL_WIDTH / 2)
    window_height = int(INTERNAL_HEIGHT / 2)

    pygame.init()
    clock = pygame.time.Clock()
    space = pymunk.Space()
    space.gravity = (0, 1000)

    screen_size = (window_width, window_height)
    screen = pygame.display.set_mode(screen_size, pygame.RESIZABLE)
    pygame.display.set_caption("Falling Pickaxe (Ultimate Edition)")
    
    internal_surface = pygame.Surface((INTERNAL_WIDTH, INTERNAL_HEIGHT))

    # Load Assets
    assets_dir = Path(__file__).parent.parent / "src/assets"
    (texture_atlas, atlas_items) = create_texture_atlas(assets_dir)
    background_image = pygame.image.load(assets_dir / "background.png")
    
    # Scale Background
    background_scale_factor = 1.5
    bg_w = int(background_image.get_width() * background_scale_factor)
    bg_h = int(background_image.get_height() * background_scale_factor)
    background_image = pygame.transform.scale(background_image, (bg_w, bg_h))

    # Day/night tint. Rebuilt only when the wall-clock minute changes, so this
    # is one surface copy a minute rather than one a frame.
    day_night = config.get("DAY_NIGHT_ENABLED", True)
    background_tinted = background_image
    background_tint_minute = None

    # Scale Atlas
    texture_atlas = pygame.transform.scale(texture_atlas,
                                        (texture_atlas.get_width() * BLOCK_SCALE_FACTOR,
                                        texture_atlas.get_height() * BLOCK_SCALE_FACTOR))
    for cat in atlas_items:
        for item in atlas_items[cat]:
            x, y, w, h = atlas_items[cat][item]
            atlas_items[cat][item] = (x*BLOCK_SCALE_FACTOR, y*BLOCK_SCALE_FACTOR, w*BLOCK_SCALE_FACTOR, h*BLOCK_SCALE_FACTOR)

    # ---------------- SOUNDS ----------------
    sound_manager = SoundManager()
    try:
        sound_manager.load_sound("tnt", assets_dir / "sounds" / "tnt.mp3", 0.3)
        sound_manager.load_sound("stone1", assets_dir / "sounds" / "stone1.wav", 0.5)
        sound_manager.load_sound("stone2", assets_dir / "sounds" / "stone2.wav", 0.5)
        sound_manager.load_sound("stone3", assets_dir / "sounds" / "stone3.wav", 0.5)
        sound_manager.load_sound("stone4", assets_dir / "sounds" / "stone4.wav", 0.5)
        sound_manager.load_sound("grass1", assets_dir / "sounds" / "grass1.wav", 0.1)
        sound_manager.load_sound("grass2", assets_dir / "sounds" / "grass2.wav", 0.1)
        sound_manager.load_sound("grass3", assets_dir / "sounds" / "grass3.wav", 0.1)
        sound_manager.load_sound("grass4", assets_dir / "sounds" / "grass4.wav", 0.1)
    except Exception as e:
        print(f"Sound Load Error (Ignored): {e}")

    pickaxe = Pickaxe(space, INTERNAL_WIDTH//2, INTERNAL_HEIGHT//2, texture_atlas.subsurface(atlas_items["pickaxe"]["wooden_pickaxe"]), sound_manager)
    
    # ---------------- TIMERS & VARIABLES ----------------
    last_tnt_spawn = pygame.time.get_ticks()
    tnt_spawn_interval = 1000 * random.uniform(config["TNT_SPAWN_INTERVAL_SECONDS_MIN"], config["TNT_SPAWN_INTERVAL_SECONDS_MAX"])
    tnt_list = []
    
    last_random_pickaxe = pygame.time.get_ticks()
    random_pickaxe_interval = 1000 * 5
    
    last_enlarge = pygame.time.get_ticks()
    enlarge_interval = 1000 * 10
    enlarge_duration = 1000 * config["PICKAXE_ENLARGE_DURATION_SECONDS"]
    spin_duration = 1000 * config.get("SPIN_DURATION_SECONDS", 10)
    spin_multiplier = config.get("SPIN_DAMAGE_MULTIPLIER", 3)
    spin_rate = config.get("SPIN_RATE_RADIANS", 12)
    spin_gravity = config.get("SPIN_GRAVITY_MULTIPLIER", 3)
    multiply_count = config.get("MULTIPLY_COUNT", 15)
    multiply_duration = 1000 * config.get("MULTIPLY_DURATION_SECONDS", 8)
    clones = []
    clones_end_time = 0
    quake_intensity = config.get("QUAKE_INTENSITY", 26)
    quake_impulse = config.get("QUAKE_IMPULSE", 900)
    storm_duration = 1000 * config.get("STORM_DURATION_SECONDS", 12)
    storm_interval = config.get("STORM_STRIKE_INTERVAL_MS", 900)
    storm = None
    last_event_quake = 0
    wet_duration = 1000 * config.get("WET_DURATION_SECONDS", 10)
    water_width = config.get("WATER_WIDTH_BLOCKS", 3.2)
    water_depth = config.get("WATER_DEPTH_BLOCKS", 1.2)
    water = None
    
    fast_slow_active = False
    fast_slow = "Fast"
    fast_slow_interval = 1000 * 15
    last_fast_slow = pygame.time.get_ticks()
    
    camera = Camera()
    hud = Hud(texture_atlas, atlas_items)
    events = EventManager(
        interval_min_s=config.get("EVENT_INTERVAL_SECONDS_MIN", 60),
        interval_max_s=config.get("EVENT_INTERVAL_SECONDS_MAX", 90),
        enabled=config.get("EVENTS_ENABLED", True),
    )
    last_storm_spawn = pygame.time.get_ticks()
    explosions = []
    
    # File Check Timer
    last_file_check = pygame.time.get_ticks()
    file_check_interval = 500 # Check file every 0.5 seconds

    # Pickaxe Auto-Revert Logic
    pickaxe_reset_time = 0
    pickaxe_duration = 1000 * config.get("PICKAXE_REVERT_DURATION_SECONDS", 30)

    running = True
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT: running = False
            elif event.type == pygame.VIDEORESIZE:
                w, h = event.w, event.h
                if w/9 > h/16: w = int(h*(9/16))
                else: h = int(w*(16/9))
                window_width, window_height = w, h
                screen = pygame.display.set_mode((w, h), pygame.RESIZABLE)

        # Physics Step
        # An active event outranks a chat-triggered speed change.
        speed_mode = events.speed_override or (fast_slow if fast_slow_active else None)
        step = 1/FRAMERATE
        if speed_mode == "Fast": step = 1/(FRAMERATE/2)
        elif speed_mode == "Slow": step = 1/(FRAMERATE*2)
        space.step(step)

        # Logic
        pickaxe.update()
        for clone in clones:
            clone.update()
        camera.update(pickaxe.body.position.y)
        
        start_chunk_y = int(pickaxe.body.position.y // (CHUNK_HEIGHT * BLOCK_SIZE) - 1) - 1
        end_chunk_y = int(pickaxe.body.position.y + INTERNAL_HEIGHT) // (CHUNK_HEIGHT * BLOCK_SIZE) + 1
        clean_chunks(start_chunk_y)

        # Drawing
        screen.fill((0,0,0))
        if day_night:
            lt = time.localtime()
            if lt.tm_min != background_tint_minute:
                background_tint_minute = lt.tm_min
                background_tinted = background_image.copy()
                background_tinted.fill(daylight.tint_for(lt.tm_hour + lt.tm_min / 60),
                                       special_flags=pygame.BLEND_RGB_MULT)
        internal_surface.blit(background_tinted, ((INTERNAL_WIDTH - bg_w)//2, (INTERNAL_HEIGHT - bg_h)//2))

        # ------------------ SPAWN LOGIC ------------------
        curr = pygame.time.get_ticks()

        events.update(hud)

        if events.tnt_storm and curr - last_storm_spawn >= 300:
            tnt_list.append(Tnt(space, pickaxe.body.position.x,
                                pickaxe.body.position.y - 100,
                                texture_atlas, atlas_items, sound_manager,
                                owner_name="TNT STORM"))
            last_storm_spawn = curr

        # Auto Spawn (Only if Chat Control FALSE)
        if not config["CHAT_CONTROL"] and curr - last_tnt_spawn >= tnt_spawn_interval:
            tnt_list.append(Tnt(space, pickaxe.body.position.x, pickaxe.body.position.y - 100, texture_atlas, atlas_items, sound_manager))
            last_tnt_spawn = curr
            tnt_spawn_interval = 1000 * random.uniform(2, 5)

        # Auto Pickaxe (Only if Chat Control FALSE)
        if not config["CHAT_CONTROL"] and curr - last_random_pickaxe >= random_pickaxe_interval:
            pickaxe.random_pickaxe(texture_atlas, atlas_items)
            last_random_pickaxe = curr
            random_pickaxe_interval = 1000 * random.uniform(10, 20)

        # ------------------ PROCESS QUEUES (FROM FILE) ------------------
        if config["CHAT_CONTROL"] and curr - last_file_check >= file_check_interval:
            check_command_file()
            last_file_check = curr
            
            # 1. Regular TNT
            if tnt_queue:
                u = tnt_queue.pop(0)
                #print(f"Spawning TNT for {u}")
                tnt_list.append(Tnt(space, pickaxe.body.position.x, pickaxe.body.position.y - 100, texture_atlas, atlas_items, sound_manager, owner_name=u))
            
            # 2. Mega TNT (Subscriber)
            if mega_tnt_queue:
                u = mega_tnt_queue.pop(0)
                tnt_list.append(MegaTnt(space, pickaxe.body.position.x, pickaxe.body.position.y - 100, texture_atlas, atlas_items, sound_manager, owner_name=u))
            
            # 3. Superchat (Multiple TNTs)
            if tnt_superchat_queue:
                u, msg = tnt_superchat_queue.pop(0)
                print(f"Superchat from {u}: {msg}")
                # Spawn multiple TNTs based on config
                for _ in range(config.get("TNT_AMOUNT_ON_SUPERCHAT", 10)):
                    tnt_list.append(Tnt(space, pickaxe.body.position.x, pickaxe.body.position.y - 100, texture_atlas, atlas_items, sound_manager, owner_name=u))

            # 4. Big Pickaxe
            if big_queue:
                big_queue.pop(0)
                pickaxe.enlarge(enlarge_duration)

            # 5. Change Pickaxe Type (With Auto-Revert)
            if pickaxe_queue:
                u, p_type = pickaxe_queue.pop(0)
                print(f"Changing pickaxe to {p_type}")
                pickaxe.pickaxe(p_type, texture_atlas, atlas_items)
                # Set the Revert Timer
                pickaxe_reset_time = curr + pickaxe_duration

            # 6. Fast/Slow Mode
            if fast_slow_queue:
                u, mode = fast_slow_queue.pop(0)
                fast_slow = mode
                fast_slow_active = True
                last_fast_slow = curr

            # 7. Spin Mode
            if spin_queue:
                spin_queue.pop(0)
                pickaxe.spin(spin_duration, spin_multiplier, spin_rate, spin_gravity)

            # 8. Multiply
            if multiply_queue:
                multiply_queue.pop(0)
                if not clones:
                    clones.extend(spawn_clones(space, pickaxe, multiply_count))
                # Re-triggering extends rather than stacking another 15 bodies.
                clones_end_time = curr + multiply_duration

            # 9. Quake
            if quake_queue:
                quake_queue.pop(0)
                trigger_quake(space, camera, quake_intensity, quake_impulse)

            # 10. Storm
            if storm_queue:
                storm_queue.pop(0)
                if storm is None:
                    storm = Storm(storm_duration, storm_interval)
                else:
                    storm.extend(storm_duration)

            # 11. Water: cures a lava burn, or pours a pool if nothing burns.
            if water_queue:
                water_queue.pop(0)
                if pickaxe.douse() == "wet":
                    water = Water(pickaxe.body.position.x, pickaxe.body.position.y,
                                  wet_duration, water_width, water_depth)

        # ------------------ TIMEOUTS & REVERTS ------------------
        
        # Fast/Slow Timeout
        if fast_slow_active and curr - last_fast_slow >= (1000 * config["FAST_SLOW_DURATION_SECONDS"]):
            fast_slow_active = False

        # EARTHQUAKE event: repeated jolts, so it reads as sustained shaking
        # rather than one bump at the start.
        if events.quake and curr - last_event_quake >= 700:
            trigger_quake(space, camera, quake_intensity, quake_impulse)
            last_event_quake = curr

        # THUNDERSTORM event: keep a storm alive while the flag is set. The
        # short extend means it rains out a couple of seconds after the event
        # ends instead of stopping dead.
        if events.storm:
            if storm is None:
                storm = Storm(storm_duration, storm_interval)
            else:
                storm.extend(2000)

        # Water pool: buoyancy applies only while the axe is inside it.
        if water is not None:
            if water.expired():
                water = None
                pickaxe.submerged = False
            else:
                water.update(pickaxe)
                pickaxe.submerged = water.covers(pickaxe.body.position.x,
                                                 pickaxe.body.position.y)

        # Storm: rain and lightning tick here, after the physics step.
        if storm is not None:
            if storm.expired():
                storm = None
            else:
                storm.update(pickaxe, camera, sound_manager)

        # Multiply Timeout
        if clones and curr > clones_end_time:
            despawn_clones(space, clones, pickaxe)

        # Pickaxe Auto-Revert Logic
        if pickaxe_reset_time > 0 and curr > pickaxe_reset_time:
            print("Time's up! Reverting to Wooden Pickaxe")
            pickaxe.pickaxe("wooden_pickaxe", texture_atlas, atlas_items)
            pickaxe_reset_time = 0

        # Draw Blocks
        for cy in range(start_chunk_y, end_chunk_y):
            for cx in range(-1, 2):
                for y in range(CHUNK_HEIGHT):
                    for x in range(CHUNK_WIDTH):
                        b = get_block(cx, cy, x, y, texture_atlas, atlas_items, space)
                        if b:
                            b.update(space, hud)
                            b.draw(internal_surface, camera)

        pickaxe.draw(internal_surface, camera)
        for clone in clones:
            clone.draw(internal_surface, camera)
        for tnt in tnt_list:
            tnt.update(tnt_list, explosions, camera)
            tnt.draw(internal_surface, camera)
        
        for exp in explosions:
            exp.update()
            exp.draw(internal_surface, camera)
        explosions = [e for e in explosions if e.particles]

        # Zero keeps the counter hidden (see Hud.draw_sub_count). Flip
        # SHOW_SUB_COUNT to true in config.json to put it back on screen.
        hud.sub_count = stream_stats["subs"] if config.get("SHOW_SUB_COUNT", False) else 0
        if water is not None:
            water.draw(internal_surface, camera)

        if storm is not None:
            storm.draw(internal_surface, camera)

        hud.draw_state_overlay(internal_surface, pickaxe)

        hud.draw(internal_surface, pickaxe.body.position.y,
                 speed_mode is not None, speed_mode or "Normal")
        hud.draw_event_ticker(internal_surface, events)

        scaled_surface = pygame.transform.smoothscale(internal_surface, (window_width, window_height))
        screen.blit(scaled_surface, (0,0))
        pygame.display.flip()
        clock.tick(FRAMERATE)

    pygame.quit()
    import sys; sys.exit()

if __name__ == "__main__":
    game()