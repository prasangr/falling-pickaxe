import functools
import math
import pygame
import random
from constants import BLOCK_SIZE, CHUNK_HEIGHT

# --- Command panel layout, in internal-surface pixels (1080 x 1920) ---
# Sized for Shorts: viewers watch on a phone, so the panel is tuned to stay
# legible after the 1080x1920 surface is scaled down to a handset viewport.
PANEL_X = 730
PANEL_W = 340
PANEL_Y = 50
ROW_H = 52
HEADER_H = 48
ICON_SIZE = 46

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

NUKE_NAME_MAX = 18


def nuke_caption(user):
    """The line shown over the blast. Crediting the viewer is the reason they
    keep typing, and the shot they would want to clip."""
    if not user:
        return "NUKE!"
    return f"NUKED BY {user[:NUKE_NAME_MAX].upper()}"


# (label, atlas category, atlas name, icon scale, is_new)
# Labels deliberately carry no "!" prefix: that is Streamer.bot trigger
# syntax and only adds noise at Shorts resolution. No description line
# either -- the icon and the name carry it, and viewers work the rest out
# from chat.
COMMAND_ROWS = [
    ("TNT",       "block",   "tnt",               1.0, False),
    ("NUKE",      "block",   "mega_tnt",          1.0, True),
    ("BIG",       "pickaxe", "wooden_pickaxe",    1.4, False),
    ("SPIN",      "spin",    "spin",              1.0, True),
    ("MULTIPLY",  "multi",   "wooden_pickaxe",    1.0, True),
    ("QUAKE",     "quake",   "quake",             1.0, True),
    ("STORM",     "bolt",    "bolt",              1.0, True),
    ("WATER",     "drop",    "drop",              1.0, True),
    ("FAST",      "chevron", "right",             1.0, False),
    ("SLOW",      "chevron", "left",              1.0, False),
    ("DIAMOND",   "pickaxe", "diamond_pickaxe",   1.0, False),
    ("GOLD",      "pickaxe", "golden_pickaxe",    1.0, False),
    ("NETHERITE", "pickaxe", "netherite_pickaxe", 1.0, False),
]

# The five pickaxe icons are near-identical silhouettes at panel size, so the
# LABEL carries the distinction instead — colour reads instantly where a 46px
# sprite does not. Tuned to each material.
LABEL_COLORS = {
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

        # Icons are cut and downscaled once here, never per frame. The atlas
        # arrives already scaled by BLOCK_SCALE_FACTOR (~7.5x).
        self.icons = {}
        for label, cat, name, scale, _new in COMMAND_ROWS:
            px = int(ICON_SIZE * scale)
            if cat == "chevron":
                self.icons[label] = make_chevron(name, px, (235, 235, 235))
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

        # Cache all static text surfaces rendered once at init, never per frame.
        self.panel_texts = {
            'COMMANDS_title': render_text_with_outline('COMMANDS', self.panel_font, (255, 255, 255), (0, 0, 0), 2),
            'NEW_COMMAND_title': render_text_with_outline('NEW COMMAND', self.panel_font, (255, 215, 0), (0, 0, 0), 2),
        }

        self.label_texts = {}  # label -> label_surface
        for label, _cat, _name, _scale, _new in COMMAND_ROWS:
            color = LABEL_COLORS.get(label, (255, 255, 255))
            lab = render_text_with_outline(label, self.panel_font, color, (0, 0, 0), 2)
            self.label_texts[label] = lab


    def update_amounts(self, new_amounts):
        """
        Update the ore amounts.
        :param new_amounts: Dict with ore names as keys and integer amounts as values.
        """
        self.amounts.update(new_amounts)

    def add_ore(self, key, lo, hi):
        """Credit an ore drop, applying the active event multiplier."""
        self.amounts[key] += random.randint(lo, hi) * self.ore_multiplier

    def _panel_box(self, screen, x, y, w, h, title_key, accent=(255, 255, 255)):
        # Transparent panel: border + outlined text only, no fill.
        pygame.draw.rect(screen, accent, (x, y, w, h), 3)
        t = self.panel_texts[title_key + '_title']
        screen.blit(t, (x + (w - t.get_width()) // 2, y + 4))

    def _panel_row(self, screen, x, y, label):
        icon = self.icons[label]
        # BIG renders at 1.4x and overflows its box on purpose.
        ix = x + 12 + (ICON_SIZE - icon.get_width()) // 2
        iy = y + (ROW_H - icon.get_height()) // 2
        screen.blit(icon, (ix, iy))

        tx = x + 12 + ICON_SIZE + 8
        lab = self.label_texts[label]
        screen.blit(lab, (tx, y + (ROW_H - lab.get_height()) // 2))

    def draw_command_panel(self, screen):
        height = HEADER_H + len(COMMAND_ROWS) * ROW_H
        self._panel_box(screen, PANEL_X, PANEL_Y, PANEL_W, height, 'COMMANDS')
        y = PANEL_Y + HEADER_H
        for label, _cat, _name, _scale, _new in COMMAND_ROWS:
            self._panel_row(screen, PANEL_X, y, label)
            y += ROW_H

        new_rows = [r for r in COMMAND_ROWS if r[4]]
        if not new_rows:
            return
        ny = PANEL_Y + height + 36
        nh = HEADER_H + len(new_rows) * ROW_H
        self._panel_box(screen, PANEL_X, ny, PANEL_W, nh, 'NEW_COMMAND', accent=(255, 215, 0))
        y = ny + HEADER_H
        for label, _cat, _name, _scale, _new in new_rows:
            self._panel_row(screen, PANEL_X, y, label)
            y += ROW_H

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


