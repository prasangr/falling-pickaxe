from collections import deque
import functools
import math
import pygame
import random
from constants import BLOCK_SIZE, CHUNK_HEIGHT
import helicopter
import voice as voice_mod
from voice import display_name

# --- Command menu layout, in internal-surface pixels (1080 x 1920) ---
# Sized for Shorts: viewers watch on a phone, so the menu is tuned to stay
# legible after the 1080x1920 surface is scaled down to a handset viewport.
MENU_X, MENU_Y, MENU_W = 742, 34, 318
ROW_H, ROW_GAP = 44, 4
TITLE_H, GROUP_H = 58, 38
ICON_SIZE = 46
MENU_ICON = 38

HAZARD_YELLOW = (255, 205, 40)
PLATE_COLOR = (14, 16, 22, 240)
CHIP_COLOR = (36, 40, 52)

# --- "JUST NOW" live feed, directly under the menu ---
FEED_SIZE = 3
FEED_ROW_H = 38
FEED_GAP = 12
FEED_H = 44 + FEED_SIZE * FEED_ROW_H

# --- Event ticker layout ---
TICKER_X, TICKER_Y = 32, 880

# Centred alert banner (lava burn), high enough to clear the ticker.
ALERT_Y = 1180
TICKER_W, TICKER_H = 420, 90

# --- Nuke Meter layout ---
# Above the bottom fifth of the screen, which YouTube covers with the title
# and buttons on a phone.
METER_X, METER_Y = 40, 1330
METER_W, METER_H = 1000, 110
METER_COLOR = (90, 235, 90)
METER_ARMED_COLOR = (255, 60, 40)

# Below the fast/slow indicator, clear of the ticker.
RECORD_X, RECORD_Y = 47, 805
RECORD_COLOR = (255, 215, 0)
RECORD_BANNER_Y = 1470

# Where the face sits on the sprite, relative to its centre, at 120px: on the
# pick head rather than the handle. Pixels at normal size.
FACE_X, FACE_Y = 22, -22
SPRITE_SIZE = 120

# --- Helicopter ---
HELI_PILOT_Y = helicopter.FLY_Y - 112
VOTE_TITLE_Y = 1100
VOTE_Y, VOTE_W, VOTE_H = 1150, 230, 96


def nuke_caption(user):
    """The line shown over the blast. Crediting the viewer is the reason they
    keep typing, and the shot they would want to clip."""
    if not user:
        return "NUKE!"
    return f"NUKED BY {display_name(user)}"


def face_offset(angle, scale):
    """Where the face goes relative to the sprite's centre, once rotated. Only
    the position turns with the axe: the features stay upright, so the face is
    still readable mid-spin."""
    x, y = FACE_X * scale, FACE_Y * scale
    return (x * math.cos(angle) - y * math.sin(angle),
            x * math.sin(angle) + y * math.cos(angle))


# commands.txt verbs that are a viewer doing something, and so appear in the
# feed. SUBS is absent on purpose: it is a counter sync, not a person.
FEED_COMMANDS = {"TNT", "NUKE", "BIG", "SPIN", "MULTIPLY", "QUAKE", "STORM", "WATER",
                 "SUB", "SUPER", "HELI", "LEFT", "MID", "RIGHT"}


def feed_label(command, value):
    """What to show for a command line, or None if no viewer is behind it."""
    if command in ("SPEED", "PICKAXE"):
        return value.upper() or None
    return command if command in FEED_COMMANDS else None


# (label, atlas category, atlas name, icon scale, is_new)
# Labels deliberately carry no "!" prefix: that is Streamer.bot trigger
# syntax and only adds noise at Shorts resolution. No description line
# either -- the icon and the name carry it, and viewers work the rest out
# from chat.
COMMAND_ROWS = [
    ("HELI",      "heli",    "heli",              1.0, True),
    ("TNT",       "block",   "tnt",               1.0, False),
    ("NUKE",      "block",   "mega_tnt",          1.0, False),
    ("BIG",       "pickaxe", "wooden_pickaxe",    1.0, False),
    ("SPIN",      "spin",    "spin",              1.0, False),
    ("MULTIPLY",  "multi",   "wooden_pickaxe",    1.0, False),
    ("QUAKE",     "quake",   "quake",             1.0, False),
    ("STORM",     "bolt",    "bolt",              1.0, False),
    ("WATER",     "drop",    "drop",              1.0, False),
    ("FAST",      "chevron", "right",             1.0, False),
    ("SLOW",      "chevron", "left",              1.0, False),
    ("DIAMOND",   "pickaxe", "diamond_pickaxe",   1.0, False),
    ("GOLD",      "pickaxe", "golden_pickaxe",    1.0, False),
    ("NETHERITE", "pickaxe", "netherite_pickaxe", 1.0, False),
]

# (group title, colour, labels). Grouped so a new viewer can find "the bomb
# ones" at a glance instead of reading fourteen rows.
MENU_GROUPS = [
    ("BOOM",    (255,  95,  70), ["HELI", "TNT", "NUKE", "QUAKE", "STORM"]),
    ("POWER",   (120, 215, 255), ["BIG", "SPIN", "MULTIPLY", "FAST", "SLOW", "WATER"]),
    ("PICKAXE", (255, 205,  60), ["DIAMOND", "GOLD", "NETHERITE"]),
]


def menu_height():
    rows = sum(len(labels) for _name, _color, labels in MENU_GROUPS)
    return 14 + TITLE_H + len(MENU_GROUPS) * GROUP_H + rows * (ROW_H + ROW_GAP) + 10


# The five pickaxe icons are near-identical silhouettes at panel size, so the
# LABEL carries the distinction instead — colour reads instantly where a 46px
# sprite does not. Tuned to each material.
LABEL_COLORS = {
    "HELI":      (255, 225,  90),
    "LEFT":      (255, 225,  90),
    "MID":       (255, 225,  90),
    "RIGHT":     (255, 225,  90),
    "SUB":       (255,  90,  90),
    "SUPER":     (255, 215,   0),
    "WOOD":      (210, 165, 110),
    "STONE":     (190, 190, 190),
    "IRON":      (225, 225, 225),
    "TNT":       (255, 255, 255),
    "NUKE":      (255, 120,  90),
    "BIG":       (255, 255, 255),
    "SPIN":      (255, 170,  70),
    "MULTIPLY":  (150, 220, 255),
    "QUAKE":     (215, 165, 105),
    "STORM":     (135, 195, 255),
    "WATER":     ( 95, 175, 255),
    "FAST":      (130, 235, 130),
    "SLOW":      (110, 200, 240),
    "DIAMOND":   ( 85, 225, 225),
    "GOLD":      (255, 205,  60),
    "NETHERITE": (190, 145, 230),
}


# Skin icons are graded toward their material so five identical silhouettes
# stop looking like one row repeated five times.
PICKAXE_ICON_TINTS = {
    "DIAMOND":   ( 90, 240, 240),
    "GOLD":      (255, 205,  60),
    "NETHERITE": (175, 130, 220),
}


def make_chevron(direction, size, color):
    """A double chevron, drawn rather than loaded — two triangles need no PNG."""
    surf = pygame.Surface((size, size), pygame.SRCALPHA)
    for i in (0, 1):
        off = i * size * 0.42
        if direction == "right":
            pts = [(off, size * 0.15),
                   (off + size * 0.42, size * 0.5),
                   (off, size * 0.85)]
        else:
            pts = [(size - off, size * 0.15),
                   (size - off - size * 0.42, size * 0.5),
                   (size - off, size * 0.85)]
        pygame.draw.polygon(surf, color, pts)
    return surf

def tint_icon(surf, color):
    """Grade an icon toward a colour. The five pickaxe skins are the same
    silhouette at panel size -- colour is the only thing that tells them
    apart at a glance."""
    out = surf.copy()
    out.fill(color, special_flags=pygame.BLEND_RGB_MULT)
    lift = tuple(int(c * 0.22) for c in color)
    out.fill(lift, special_flags=pygame.BLEND_RGB_ADD)
    return out


def outline_icon(surf, width=3, color=(0, 0, 0)):
    """Dark halo around an icon so it reads against bright terrain.

    The reference layouts get this for free by sitting icons on dark pills;
    the panel here is transparent, so the icon carries its own contrast.
    """
    w, h = surf.get_size()
    out = pygame.Surface((w + width * 2, h + width * 2), pygame.SRCALPHA)
    silhouette = pygame.mask.from_surface(surf).to_surface(
        setcolor=color, unsetcolor=(0, 0, 0, 0))
    for dx in range(-width, width + 1):
        for dy in range(-width, width + 1):
            if dx * dx + dy * dy > width * width:
                continue  # Round halo, not a square one.
            out.blit(silhouette, (width + dx, width + dy))
    out.blit(surf, (width, width))
    return out


def make_quake(size, color):
    """A cracked ground line -- a zigzag fissure reads as a quake instantly."""
    surf = pygame.Surface((size, size), pygame.SRCALPHA)
    w = max(2, int(size * 0.11))
    pts = [(size * 0.06, size * 0.30), (size * 0.32, size * 0.52),
           (size * 0.18, size * 0.66), (size * 0.52, size * 0.92)]
    pygame.draw.lines(surf, color, False, pts, w)
    # Two side branches, so it reads as cracked rather than as a stray line.
    pygame.draw.lines(surf, color, False,
                      [(size * 0.32, size * 0.52), (size * 0.62, size * 0.42)], w)
    pygame.draw.lines(surf, color, False,
                      [(size * 0.18, size * 0.66), (size * 0.86, size * 0.60)], w)
    return surf


def make_drop(size, color):
    """A water droplet: round belly, pointed top."""
    surf = pygame.Surface((size, size), pygame.SRCALPHA)
    r = size * 0.30
    cx, cy = size * 0.5, size * 0.62
    pygame.draw.circle(surf, color, (int(cx), int(cy)), int(r))
    pygame.draw.polygon(surf, color, [(cx, size * 0.06),
                                      (cx - r * 0.92, cy + r * 0.22),
                                      (cx + r * 0.92, cy + r * 0.22)])
    # Highlight, so it reads as liquid rather than a blue blob.
    pygame.draw.circle(surf, (255, 255, 255),
                       (int(cx - r * 0.34), int(cy - r * 0.30)), max(2, int(r * 0.22)))
    return surf


def make_bolt(size, color):
    """A lightning bolt."""
    surf = pygame.Surface((size, size), pygame.SRCALPHA)
    pygame.draw.polygon(surf, color, [
        (size * 0.58, size * 0.02), (size * 0.20, size * 0.55),
        (size * 0.44, size * 0.55), (size * 0.32, size * 0.98),
        (size * 0.82, size * 0.40), (size * 0.54, size * 0.40),
        (size * 0.74, size * 0.02),
    ])
    return surf


def make_multi(src, size):
    """Three overlapping pickaxes -- one sprite cannot say "many"."""
    surf = pygame.Surface((size, size), pygame.SRCALPHA)
    small = pygame.transform.smoothscale(src, (int(size * 0.62), int(size * 0.62)))
    for ox, oy in ((0.0, 0.34), (0.19, 0.17), (0.38, 0.0)):
        surf.blit(small, (int(ox * size), int(oy * size)))
    return surf


def make_spin(size, color):
    """A circular arrow. No pickaxe sprite can show rotation -- an arrow can,
    and drawing it beats shipping another PNG."""
    surf = pygame.Surface((size, size), pygame.SRCALPHA)
    pad = size * 0.14
    rect = pygame.Rect(pad, pad, size - 2 * pad, size - 2 * pad)
    width = max(2, int(size * 0.14))
    # Open arc: the gap is where the arrowhead goes.
    pygame.draw.arc(surf, color, rect, math.radians(-40), math.radians(250), width)

    # Arrowhead at the open end, pointing clockwise (the direction the axe
    # actually spins on screen).
    r = (size - 2 * pad) / 2
    cx = cy = size / 2
    a = math.radians(-40)
    tip_a = a - math.radians(26)
    tip = (cx + r * math.cos(tip_a), cy - r * math.sin(tip_a))
    head = size * 0.30
    # Perpendicular to the radius, so the barbs straddle the stroke.
    nx, ny = math.cos(a), -math.sin(a)
    px, py = -ny, nx
    base = (cx + r * math.cos(a), cy - r * math.sin(a))
    pygame.draw.polygon(surf, color, [
        tip,
        (base[0] + px * head * 0.5, base[1] + py * head * 0.5),
        (base[0] - px * head * 0.5, base[1] - py * head * 0.5),
    ])
    return surf


def make_heli_icon(size, color):
    """A small side-on helicopter for the menu row."""
    surf = pygame.Surface((size, size), pygame.SRCALPHA)
    pygame.draw.rect(surf, color, (size * 0.34, size * 0.40, size * 0.52, size * 0.32),
                     border_radius=max(2, int(size * 0.10)))
    pygame.draw.rect(surf, color, (size * 0.04, size * 0.46, size * 0.34, size * 0.10))
    pygame.draw.rect(surf, color, (size * 0.02, size * 0.32, size * 0.08, size * 0.26))
    pygame.draw.rect(surf, color, (size * 0.56, size * 0.24, size * 0.08, size * 0.18))
    pygame.draw.rect(surf, color, (size * 0.22, size * 0.18, size * 0.76, size * 0.08))
    pygame.draw.rect(surf, color, (size * 0.34, size * 0.82, size * 0.54, size * 0.07))
    return surf


@functools.cache
def helicopter_frames():
    """Two blocky rotor frames, drawn rather than loaded so the art is ours.
    Cached: rebuilding them at 60fps would be pure waste."""
    frames = []
    for wide_rotor in (True, False):
        surf = pygame.Surface((300, 140), pygame.SRCALPHA)
        steel, dark = (64, 72, 86), (34, 38, 48)
        # Tail boom, with the hazard stripes that tie it to the menu.
        pygame.draw.rect(surf, HAZARD_YELLOW, (14, 58, 90, 18))
        for x in range(14, 100, 24):
            pygame.draw.rect(surf, (18, 18, 20), (x, 58, 12, 18))
        pygame.draw.rect(surf, (225, 55, 40), (0, 26, 26, 44))
        pygame.draw.circle(surf, dark, (13, 42), 18, 5)
        # Body, cockpit and nose.
        pygame.draw.rect(surf, steel, (96, 40, 140, 66))
        pygame.draw.rect(surf, dark, (96, 92, 140, 14))
        pygame.draw.rect(surf, (135, 215, 245), (178, 50, 62, 34))
        pygame.draw.rect(surf, (215, 240, 250), (186, 54, 18, 12))
        pygame.draw.rect(surf, steel, (236, 58, 24, 40))
        # Mast and rotor.
        pygame.draw.rect(surf, dark, (156, 24, 14, 18))
        rotor = (32, 14, 262, 9) if wide_rotor else (118, 14, 90, 9)
        pygame.draw.rect(surf, dark, rotor)
        # Skids and the TNT rack.
        pygame.draw.rect(surf, dark, (124, 106, 8, 20))
        pygame.draw.rect(surf, dark, (204, 106, 8, 20))
        pygame.draw.rect(surf, dark, (96, 124, 142, 8))
        pygame.draw.rect(surf, (215, 45, 40), (150, 106, 36, 16))
        pygame.draw.rect(surf, (245, 245, 245), (150, 110, 36, 8))
        frames.append(surf)
    return frames


def hazard_band(surf, x, y, w, h):
    """Yellow-and-black warning stripes: the NukeCraft look."""
    band = pygame.Surface((w, h), pygame.SRCALPHA)
    band.fill(HAZARD_YELLOW)
    for sx in range(-h, w + h, h * 2):
        pygame.draw.polygon(band, (18, 18, 20),
                            [(sx, h), (sx + h, 0), (sx + h * 2, 0), (sx + h, h)])
    surf.blit(band, (x, y))


def render_text_with_outline(text, font, text_color, outline_color, outline_width=2):
    # Render the text in the main color.
    text_surface = font.render(text, True, text_color)
    # Create a new surface larger than the text surface to hold the outline.
    w, h = text_surface.get_size()
    outline_surface = pygame.Surface((w + 2*outline_width, h + 2*outline_width), pygame.SRCALPHA)
    
    # Blit the text multiple times in the outline color, offset by outline_width in every direction.
    for dx in range(-outline_width, outline_width+1):
        for dy in range(-outline_width, outline_width+1):
            # Only draw outline if offset is non-zero (avoids overdraw, though it's not a big deal)
            if dx != 0 or dy != 0:
                pos = (dx + outline_width, dy + outline_width)
                outline_surface.blit(font.render(text, True, outline_color), pos)
    
    # Blit the main text in the center.
    outline_surface.blit(text_surface, (outline_width, outline_width))
    return outline_surface


# An outlined line is dozens of font renders. The meter redraws the same few
# strings every frame at 60fps, so it reuses them instead.
cached_text = functools.lru_cache(maxsize=256)(render_text_with_outline)


class Hud:
    def __init__(self, texture_atlas, atlas_items, position=(32, 32)):
        """
        :param texture_atlas: The atlas surface containing the item icons.
        :param atlas_items: A dict with keys under "item" for each ore.
        :param position: Top-left position where the HUD will be drawn.
        """
        self.texture_atlas = texture_atlas
        self.atlas_items = atlas_items

        # Initialize ore amounts to 0.
        self.amounts = {
            "coal": 0,
            "iron_ingot": 0,
            "copper_ingot": 0,
            "gold_ingot": 0,
            "redstone": 0,
            "lapis_lazuli": 0,
            "diamond": 0,
            "emerald": 0,
        }

        # Multiplied by the GOLD FEVER event; 1 means normal drops.
        self.ore_multiplier = 1

        # Set from main.py. Zero means "not configured" and renders nothing.
        self.sub_count = 0

        self.position = position
        self.icon_size = (64, 64)  # Size to draw each icon
        self.spacing = 15  # Space between items

        # Initialize a font (using the default font and size 24)
        self.font = pygame.font.Font(None, 64)

        self.panel_font = pygame.font.Font(None, 38)
        self.small_ticker_font = pygame.font.Font(None, 30)
        self.big_font = pygame.font.Font(None, 72)
        self.bubble_font = pygame.font.Font(None, 52)

        # Who just did what, newest first, for the "JUST NOW" panel.
        self.feed = deque(maxlen=FEED_SIZE)

        # Icons are cut and downscaled once here, never per frame. The atlas
        # arrives already scaled by BLOCK_SCALE_FACTOR (~7.5x).
        self.icons = {}
        for label, cat, name, scale, _new in COMMAND_ROWS:
            px = int(ICON_SIZE * scale)
            if cat == "chevron":
                self.icons[label] = make_chevron(name, px, (235, 235, 235))
            elif cat == "heli":
                self.icons[label] = make_heli_icon(px, LABEL_COLORS["HELI"])
            elif cat == "spin":
                self.icons[label] = make_spin(px, LABEL_COLORS["SPIN"])
            elif cat == "quake":
                self.icons[label] = make_quake(px, LABEL_COLORS["QUAKE"])
            elif cat == "bolt":
                self.icons[label] = make_bolt(px, LABEL_COLORS["STORM"])
            elif cat == "drop":
                self.icons[label] = make_drop(px, LABEL_COLORS["WATER"])
            elif cat == "multi":
                base = texture_atlas.subsurface(pygame.Rect(atlas_items["pickaxe"][name]))
                self.icons[label] = make_multi(base, px)
            else:
                src = texture_atlas.subsurface(pygame.Rect(atlas_items[cat][name]))
                icon = pygame.transform.smoothscale(src, (px, px))
                # Pickaxe skins share one silhouette; tint each to its label
                # colour so the row is identifiable without reading the text.
                if cat == "pickaxe" and label in PICKAXE_ICON_TINTS:
                    icon = tint_icon(icon, PICKAXE_ICON_TINTS[label])
                self.icons[label] = icon

        # Every icon gets the halo, whatever built it.
        for label, icon in self.icons.items():
            self.icons[label] = outline_icon(icon)

        # The menu never changes, so it is built once and blitted every frame.
        self.menu_surface = self._build_menu()


    def update_amounts(self, new_amounts):
        """
        Update the ore amounts.
        :param new_amounts: Dict with ore names as keys and integer amounts as values.
        """
        self.amounts.update(new_amounts)

    def add_ore(self, key, lo, hi):
        """Credit an ore drop, applying the active event multiplier."""
        self.amounts[key] += random.randint(lo, hi) * self.ore_multiplier

    def add_feed(self, user, label):
        """Note a viewer's action for the feed. `label` is from feed_label()."""
        if label:
            self.feed.appendleft((display_name(user), label))

    def _build_menu(self):
        height = menu_height()
        surf = pygame.Surface((MENU_W, height), pygame.SRCALPHA)
        pygame.draw.rect(surf, PLATE_COLOR, (0, 0, MENU_W, height), border_radius=18)
        hazard_band(surf, 14, 8, MENU_W - 28, 12)
        pygame.draw.rect(surf, HAZARD_YELLOW, (0, 0, MENU_W, height), 3, border_radius=18)

        title = cached_text("TYPE IN CHAT", self.panel_font, (255, 255, 255), (0, 0, 0), 2)
        surf.blit(title, ((MENU_W - title.get_width()) // 2, 28))

        new_labels = {row[0] for row in COMMAND_ROWS if row[4]}
        y = 14 + TITLE_H
        for name, color, labels in MENU_GROUPS:
            head = cached_text(name, self.small_ticker_font, color, (0, 0, 0), 2)
            surf.blit(head, (16, y + 6))
            line_x = 22 + head.get_width()
            pygame.draw.line(surf, color, (line_x, y + 16), (MENU_W - 16, y + 16), 2)
            y += GROUP_H
            for label in labels:
                self._menu_row(surf, y, label, label in new_labels)
                y += ROW_H + ROW_GAP
        return surf

    def _menu_row(self, surf, y, label, is_new):
        accent = LABEL_COLORS.get(label, (255, 255, 255))
        pygame.draw.rect(surf, CHIP_COLOR, (12, y, MENU_W - 24, ROW_H), border_radius=10)
        pygame.draw.rect(surf, accent, (12, y, 7, ROW_H),
                         border_top_left_radius=10, border_bottom_left_radius=10)

        icon = pygame.transform.smoothscale(self.icons[label], (MENU_ICON, MENU_ICON))
        surf.blit(icon, (26, y + (ROW_H - MENU_ICON) // 2))

        lab = cached_text(label, self.panel_font, accent, (0, 0, 0), 2)
        surf.blit(lab, (72, y + (ROW_H - lab.get_height()) // 2))

        if is_new:
            pill = pygame.Rect(MENU_W - 86, y + 9, 62, 26)
            pygame.draw.rect(surf, (255, 60, 40), pill, border_radius=13)
            tag = self.small_ticker_font.render("NEW", True, (255, 255, 255))
            surf.blit(tag, tag.get_rect(center=pill.center))

    def draw_command_panel(self, screen):
        screen.blit(self.menu_surface, (MENU_X, MENU_Y))
        self._draw_feed(screen, MENU_Y + menu_height() + FEED_GAP)

    def _draw_feed(self, screen, y):
        # Nothing rather than an empty box until someone has actually typed.
        if not self.feed:
            return
        plate = pygame.Surface((MENU_W, FEED_H), pygame.SRCALPHA)
        pygame.draw.rect(plate, PLATE_COLOR, (0, 0, MENU_W, FEED_H), border_radius=14)
        screen.blit(plate, (MENU_X, y))

        pygame.draw.circle(screen, (255, 50, 50), (MENU_X + 24, y + 22), 8)
        title = cached_text("JUST NOW", self.small_ticker_font, (255, 255, 255), (0, 0, 0), 2)
        screen.blit(title, (MENU_X + 40, y + 10))

        row_y = y + 42
        for user, label in self.feed:
            name = cached_text(user, self.small_ticker_font, (225, 225, 235), (0, 0, 0), 2)
            action = cached_text(label, self.small_ticker_font,
                                 LABEL_COLORS.get(label, (255, 255, 255)), (0, 0, 0), 2)
            screen.blit(name, (MENU_X + 16, row_y))
            screen.blit(action, (MENU_X + MENU_W - action.get_width() - 16, row_y))
            row_y += FEED_ROW_H

    # ---------- talking pickaxe ----------

    def draw_pickaxe_face(self, screen, axe, camera, voice):
        """Eyes and a mouth on the pick head. Drawn over the sprite, so every
        material and the !big size get the same character."""
        scale = axe.texture.get_width() / SPRITE_SIZE
        dx, dy = face_offset(axe.body.angle, scale)
        cx = axe.body.position.x + dx - camera.offset_x
        cy = axe.body.position.y + dy - camera.offset_y

        eye_r = 14 * scale
        gap = 15 * scale
        ink = (18, 18, 22)
        now = pygame.time.get_ticks()

        white = (255, 255, 255)
        edge = max(2, int(2 * scale))
        stroke = max(3, int(4 * scale))

        for side in (-1, 1):
            ex, ey = cx + side * gap, cy - 5 * scale
            # Dark rim on every eye: white on a bright sky has no edge otherwise.
            radius = eye_r * 1.25 if voice.mood == voice_mod.SCARED else eye_r
            pygame.draw.circle(screen, ink, (ex, ey), radius + edge)
            pygame.draw.circle(screen, white, (ex, ey), radius)

            if voice.mood == voice_mod.DIZZY:
                # X eyes: they read as dizzy even at phone size.
                r = eye_r * 0.6
                pygame.draw.line(screen, ink, (ex - r, ey - r), (ex + r, ey + r), stroke)
                pygame.draw.line(screen, ink, (ex - r, ey + r), (ex + r, ey - r), stroke)
            elif voice.mood == voice_mod.HAPPY:
                # Squeezed-shut ^ eyes.
                r = eye_r * 0.62
                pygame.draw.lines(screen, ink, False, [(ex - r, ey + r * 0.5), (ex, ey - r * 0.6),
                                                       (ex + r, ey + r * 0.5)], stroke)
            elif voice.mood == voice_mod.SCARED:
                # Huge whites, small pupils.
                pygame.draw.circle(screen, ink, (ex, ey), eye_r * 0.32)
            else:
                # Pupils drift, so it looks alive even with nothing happening.
                look = math.sin(now / 900) * eye_r * 0.35
                pygame.draw.circle(screen, ink, (ex + look, ey), eye_r * 0.5)

        # Every mouth is ink on a white halo: bare ink vanishes on dark wood.
        mouth_y = cy + 17 * scale
        if voice.mood == voice_mod.SCARED:
            mouth = pygame.Rect(cx - 10 * scale, mouth_y - 3 * scale, 20 * scale, 24 * scale)
            pygame.draw.ellipse(screen, white, mouth.inflate(edge * 2, edge * 2))
            pygame.draw.ellipse(screen, ink, mouth)
        elif voice.mood == voice_mod.HAPPY:
            # An open grin: a half-disc, flat edge up.
            pts = [(cx + 15 * scale * math.cos(a / 10 * math.pi),
                    mouth_y - 2 * scale + 15 * scale * math.sin(a / 10 * math.pi))
                   for a in range(11)]
            pygame.draw.polygon(screen, white, pts, stroke + edge * 2)
            pygame.draw.polygon(screen, ink, pts)
        else:
            half = 9 * scale
            pygame.draw.line(screen, white, (cx - half - edge, mouth_y),
                             (cx + half + edge, mouth_y), stroke + edge * 2)
            pygame.draw.line(screen, ink, (cx - half, mouth_y), (cx + half, mouth_y), stroke)

    def draw_speech_bubble(self, screen, axe, camera, voice):
        if not voice.line:
            return
        text = cached_text(voice.line, self.bubble_font, (18, 18, 22), (255, 255, 255), 1)
        w, h = text.get_width() + 44, text.get_height() + 28

        tip_x = axe.body.position.x - camera.offset_x
        tip_y = axe.body.position.y - camera.offset_y - axe.texture.get_height() * 0.55
        # Kept on screen: a bubble cut off by the edge is a wasted joke.
        x = max(20, min(screen.get_width() - w - 20, tip_x - w / 2))
        y = max(20, tip_y - h - 34)

        border = {voice_mod.SCARED: (225, 50, 40), voice_mod.HAPPY: (60, 180, 80),
                  voice_mod.DIZZY: (225, 150, 40)}.get(voice.mood, (18, 18, 22))
        tail = [(tip_x - 20, y + h - 3), (tip_x + 20, y + h - 3), (tip_x, y + h + 30)]
        pygame.draw.polygon(screen, (255, 255, 255), tail)
        pygame.draw.lines(screen, border, False, tail, 5)
        pygame.draw.rect(screen, (255, 255, 255), (x, y, w, h), border_radius=18)
        pygame.draw.rect(screen, border, (x, y, w, h), 5, border_radius=18)
        screen.blit(text, (x + 22, y + 14))

    # ---------- helicopter ----------

    def draw_helicopter(self, screen, heli):
        now = pygame.time.get_ticks()
        frame = helicopter_frames()[(now // 50) % 2]
        bob = math.sin(now / 260) * 8
        rect = frame.get_rect(center=(heli.x, helicopter.FLY_Y + bob))
        screen.blit(frame, rect)

        title = f"PILOT {display_name(heli.pilot)}" if heli.pilot else "NUKECRAFT AIR"
        tag = cached_text(title, self.panel_font, LABEL_COLORS["HELI"], (0, 0, 0), 2)
        # Clamped: the tag is wider than the helicopter as it enters and leaves.
        tag_x = max(16, min(screen.get_width() - tag.get_width() - 16,
                            heli.x - tag.get_width() / 2))
        screen.blit(tag, (tag_x, HELI_PILOT_Y + bob))

        if heli.phase == helicopter.VOTING:
            self._draw_vote_panel(screen, heli)

    def _draw_vote_panel(self, screen, heli):
        title = cached_text(f"TYPE LEFT, MID OR RIGHT   {heli.vote_secs_left()}",
                            self.font, HAZARD_YELLOW, (0, 0, 0), 3)
        screen.blit(title, ((screen.get_width() - title.get_width()) // 2, VOTE_TITLE_Y))

        tally = heli.tally()
        winner = heli.winner()
        for lane, x in helicopter.LANES.items():
            plate = pygame.Surface((VOTE_W, VOTE_H), pygame.SRCALPHA)
            pygame.draw.rect(plate, PLATE_COLOR, (0, 0, VOTE_W, VOTE_H), border_radius=14)
            left = x - VOTE_W // 2
            screen.blit(plate, (left, VOTE_Y))
            border = HAZARD_YELLOW if lane == winner else (110, 115, 130)
            pygame.draw.rect(screen, border, (left, VOTE_Y, VOTE_W, VOTE_H), 4, border_radius=14)

            name = cached_text(lane, self.panel_font, LABEL_COLORS[lane], (0, 0, 0), 2)
            screen.blit(name, (x - name.get_width() // 2, VOTE_Y + 8))
            count = cached_text(str(tally[lane]), self.font, (255, 255, 255), (0, 0, 0), 2)
            screen.blit(count, (x - count.get_width() // 2, VOTE_Y + 42))

    def draw_sub_count(self, screen):
        # Zero means hidden: a streamer who never set SUB_COUNT_BASE gets a
        # clean screen rather than an embarrassing "0".
        if not self.sub_count:
            return
        x, y = 32, 1000
        # Drawn triangle rather than a glyph -- the default pygame font has
        # no reliable play-symbol codepoint.
        pygame.draw.polygon(screen, (255, 0, 0),
                            [(x, y + 4), (x, y + 34), (x + 26, y + 19)])
        surf = render_text_with_outline(f"{self.sub_count:,} subs", self.font,
                                        (255, 255, 255), (0, 0, 0), 2)
        screen.blit(surf, (x + 36, y - 4))

    def _ticker_panel(self, screen, color, glow):
        """Rounded plate with an outer glow. `glow` is 0..1 pulse strength."""
        pad = 14
        surf = pygame.Surface((TICKER_W + pad * 2, TICKER_H + pad * 2), pygame.SRCALPHA)

        # Glow: concentric rounded rects fading outward. Cheap, and it lifts
        # the plate off the terrain instead of sitting flat on it.
        for i in range(pad, 0, -3):
            a = int(46 * glow * (1 - i / pad))
            if a <= 0:
                continue
            pygame.draw.rect(surf, (*color, a),
                             (pad - i, pad - i, TICKER_W + i * 2, TICKER_H + i * 2),
                             border_radius=18 + i)

        # Two-tone body: lighter at the top, so it reads as a lit surface.
        pygame.draw.rect(surf, (26, 26, 34, 232), (pad, pad, TICKER_W, TICKER_H),
                         border_radius=16)
        pygame.draw.rect(surf, (44, 44, 56, 232), (pad, pad, TICKER_W, TICKER_H // 2),
                         border_top_left_radius=16, border_top_right_radius=16)
        pygame.draw.rect(surf, (*color, 255), (pad, pad, TICKER_W, TICKER_H),
                         3, border_radius=16)
        screen.blit(surf, (TICKER_X - pad, TICKER_Y - pad))

    def _ticker_bar(self, screen, x, y, w, h, fraction, color):
        """Rounded progress bar with a highlight along its top edge."""
        pygame.draw.rect(screen, (46, 46, 56), (x, y, w, h), border_radius=h // 2)
        filled = max(h, int(w * fraction)) if fraction > 0 else 0
        if filled:
            pygame.draw.rect(screen, color, (x, y, filled, h), border_radius=h // 2)
            light = tuple(min(255, c + 55) for c in color)
            pygame.draw.rect(screen, light, (x + 3, y + 2, max(1, filled - 6), h // 3),
                             border_radius=h // 3)

    def draw_event_ticker(self, screen, events):
        """Render the active or incoming event. Nothing is drawn while idle."""
        countdown = None
        if events.phase == "idle":
            countdown = events.countdown_secs()
            if countdown is None:
                return

        # Sine pulse shared by every phase, so the plate always breathes.
        period = 1100 if countdown is not None else 600
        t = pygame.time.get_ticks() % period
        pulse = (math.sin(t / period * 2 * math.pi) + 1) / 2

        if countdown is not None:
            # Neutral, warming toward gold as it closes in: tension without
            # leaking which event is coming.
            heat = 1 - min(1.0, countdown / 15)
            color = (int(200 + 55 * heat), int(200 - 25 * heat), int(210 - 140 * heat))
            self._ticker_panel(screen, color, 0.35 + 0.65 * pulse * heat)

            label = render_text_with_outline("NEXT EVENT", self.small_ticker_font,
                                             (205, 205, 215), (0, 0, 0), 2)
            screen.blit(label, (TICKER_X + 16, TICKER_Y + 10))

            big = render_text_with_outline(f"{countdown}", self.big_font, color, (0, 0, 0), 3)
            screen.blit(big, (TICKER_X + TICKER_W - big.get_width() - 18, TICKER_Y + 4))

            self._ticker_bar(screen, TICKER_X + 16, TICKER_Y + TICKER_H - 26,
                             TICKER_W - 32, 14, countdown / 15, color)
            return

        color = events.color
        if events.phase == "warning":
            flash = tuple(int(c * (0.45 + 0.55 * pulse)) for c in color)
            self._ticker_panel(screen, color, 0.4 + 0.6 * pulse)
            label = render_text_with_outline(f"{events.name} INCOMING",
                                             self.panel_font, flash, (0, 0, 0), 2)
            screen.blit(label, (TICKER_X + 16,
                                TICKER_Y + (TICKER_H - label.get_height()) // 2))
            return

        # Active: steady plate, name left, seconds right, drain bar beneath.
        self._ticker_panel(screen, color, 0.25 + 0.25 * pulse)
        label = render_text_with_outline(events.name, self.panel_font, color, (0, 0, 0), 2)
        screen.blit(label, (TICKER_X + 16, TICKER_Y + 8))

        secs = (events.remaining_ms() + 999) // 1000
        secs_surf = render_text_with_outline(f"{secs}s", self.panel_font,
                                             (255, 255, 255), (0, 0, 0), 2)
        screen.blit(secs_surf,
                    (TICKER_X + TICKER_W - secs_surf.get_width() - 18, TICKER_Y + 8))

        self._ticker_bar(screen, TICKER_X + 16, TICKER_Y + TICKER_H - 30,
                         TICKER_W - 32, 18, 1.0 - events.progress(), color)

    def draw_nuke_meter(self, screen, meter):
        """The shared bar. Hidden entirely when the meter is switched off."""
        if not meter.enabled:
            return

        armed = meter.phase == "armed"
        color = METER_ARMED_COLOR if armed else METER_COLOR
        pulse = (math.sin(pygame.time.get_ticks() / 120) + 1) / 2

        plate = pygame.Surface((METER_W, METER_H), pygame.SRCALPHA)
        pygame.draw.rect(plate, (26, 26, 34, 225), (0, 0, METER_W, METER_H),
                         border_radius=16)
        screen.blit(plate, (METER_X, METER_Y))
        border = tuple(int(c * (0.4 + 0.6 * pulse)) for c in color) if armed else color
        pygame.draw.rect(screen, border, (METER_X, METER_Y, METER_W, METER_H), 4,
                         border_radius=16)

        title = f"NUKE IN {meter.countdown_secs()}" if armed else "NUKE METER"
        label = cached_text(title, self.panel_font, color, (0, 0, 0), 2)
        screen.blit(label, (METER_X + 20, METER_Y + 12))

        if not armed:
            percent = cached_text(f"{int(meter.fraction() * 100)}%",
                                  self.panel_font, (255, 255, 255), (0, 0, 0), 2)
            screen.blit(percent, (METER_X + METER_W - percent.get_width() - 20,
                                  METER_Y + 12))

        self._ticker_bar(screen, METER_X + 20, METER_Y + METER_H - 46,
                         METER_W - 40, 30, meter.fraction(), color)

    def draw_nuke_flash(self, screen, meter):
        """White-out and credit on detonation. Nothing is drawn the rest of the time."""
        flash = meter.flash()
        if flash <= 0:
            return

        # Surface-wide alpha, not per-pixel: this covers the whole 1080x1920
        # frame, and per-pixel blending stuttered right on the moment people clip.
        overlay = pygame.Surface(screen.get_size())
        overlay.fill((255, 255, 255))
        overlay.set_alpha(int(255 * flash))
        screen.blit(overlay, (0, 0))

        caption = cached_text(nuke_caption(meter.detonated_by), self.big_font,
                              METER_ARMED_COLOR, (0, 0, 0), 4)
        screen.blit(caption, ((screen.get_width() - caption.get_width()) // 2,
                              (screen.get_height() - caption.get_height()) // 2))

    def draw_depth_record(self, screen, best, celebrating):
        """The number every stream is chasing. Hidden until there is one."""
        if not best:
            return
        surf = cached_text(f"RECORD {best:,}", self.font, RECORD_COLOR, (0, 0, 0), 2)
        screen.blit(surf, (RECORD_X, RECORD_Y))

        if celebrating:
            banner = cached_text("NEW DEPTH RECORD!", self.big_font,
                                 RECORD_COLOR, (0, 0, 0), 4)
            screen.blit(banner, ((screen.get_width() - banner.get_width()) // 2,
                                 RECORD_BANNER_Y))

    def draw_state_overlay(self, screen, pickaxe):
        """Screen tint and alert for the lava/water states."""
        # Water is a real pool in the world now, so only the burn tints here.
        if not pickaxe.overheated_until:
            return
        tint, color = (255, 90, 20, 46), (255, 150, 60)
        lines = ("LAVA DAMAGED THE AXE", "POUR WATER ON IT")

        overlay = pygame.Surface(screen.get_size(), pygame.SRCALPHA)
        overlay.fill(tint)
        screen.blit(overlay, (0, 0))

        # Same rounded plate as the ticker, so alerts look like one system.
        surfaces = [render_text_with_outline(t, self.panel_font, c, (0, 0, 0), 3)
                    for t, c in zip(lines, (color, (255, 255, 255)))]
        w = max(s.get_width() for s in surfaces) + 48
        h = sum(s.get_height() for s in surfaces) + 34
        x = (screen.get_width() - w) // 2
        y = ALERT_Y

        pulse = (math.sin(pygame.time.get_ticks() / 400) + 1) / 2
        plate = pygame.Surface((w, h), pygame.SRCALPHA)
        plate.fill((26, 14, 10, 226))
        screen.blit(plate, (x, y))
        pygame.draw.rect(screen, tuple(int(c * (0.5 + 0.5 * pulse)) for c in color),
                         (x, y, w, h), 4, border_radius=14)

        ty = y + 14
        for surf in surfaces:
            screen.blit(surf, (x + (w - surf.get_width()) // 2, ty))
            ty += surf.get_height()

    def draw(self, screen, pickaxe_y, fast_slow_active, fast_slow):
        """
        Draws the HUD: each ore icon with its amount and other indicators.
        """
        x, y = self.position

        for ore, amount in self.amounts.items():
            # Retrieve the icon rect from atlas_items["item"][ore]
            if ore in self.atlas_items["item"]:
                icon_rect = pygame.Rect(self.atlas_items["item"][ore])
                icon = self.texture_atlas.subsurface(icon_rect)
                # Scale the icon to desired icon size
                icon = pygame.transform.scale(icon, self.icon_size)
                # Blit the icon
                screen.blit(icon, (x, y))
            else:
                # In case the ore key is missing, skip drawing the icon
                continue

            # Render the amount text with a black outline.
            text = str(amount)
            # You can tweak outline_width, text color, and outline color as needed.
            text_surface = render_text_with_outline(text, self.font, (255, 255, 255), (0, 0, 0), outline_width=2)
            
            # Position text to the right of the icon
            text_x = x + self.icon_size[0] + self.spacing
            text_y = y + (self.icon_size[1] - text_surface.get_height()) // 2 + 3
            screen.blit(text_surface, (text_x, text_y))

            # Move to the next line
            y += self.icon_size[1] + self.spacing

        # Draw the pickaxe position indicator with outlined text
        pickaxe_indicator_text = f"Y: {-int(pickaxe_y // BLOCK_SIZE)}"
        pickaxe_indicator_surface = render_text_with_outline(pickaxe_indicator_text, self.font, (255, 255, 255), (0, 0, 0), outline_width=2)
        pickaxe_indicator_x = x + self.spacing
        pickaxe_indicator_y = y + self.spacing
        screen.blit(pickaxe_indicator_surface, (pickaxe_indicator_x, pickaxe_indicator_y))

        # Draw the fast/slow indicator with outlined text
        if fast_slow_active:
            fast_slow_text = f"{fast_slow}"
        else:
            fast_slow_text = "Normal"
        fast_slow_surface = render_text_with_outline(fast_slow_text, self.font, (255, 255, 255), (0, 0, 0), outline_width=2)
        fast_slow_x = x + self.spacing
        fast_slow_y = y + 2 * self.spacing + fast_slow_surface.get_height()
        screen.blit(fast_slow_surface, (fast_slow_x, fast_slow_y))

        self.draw_command_panel(screen)
        self.draw_sub_count(screen)


