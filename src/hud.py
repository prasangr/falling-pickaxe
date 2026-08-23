import math
import pygame
import random
from constants import BLOCK_SIZE, CHUNK_HEIGHT

# --- Command panel layout, in internal-surface pixels (1080 x 1920) ---
PANEL_X = 756
PANEL_W = 300
PANEL_Y = 180
ROW_H = 52
HEADER_H = 44
ICON_SIZE = 40

# --- Event ticker layout ---
TICKER_X, TICKER_Y = 32, 880
TICKER_W, TICKER_H = 420, 90

# (label, subtitle, atlas category, atlas name, icon scale, is_new)
# Labels deliberately carry no "!" prefix: that is Streamer.bot trigger
# syntax and only adds noise at Shorts resolution.
COMMAND_ROWS = [
    ("TNT",       "SPAWN 1 TNT",         "block",   "tnt",               1.0, False),
    ("NUKE",      "GIANT PICK + 30 TNT", "block",   "mega_tnt",          1.0, True),
    ("BIG",       "GIANT PICKAXE",       "pickaxe", "wooden_pickaxe",    1.4, False),
    ("FAST",      "SPEED UP 5S",         "chevron", "right",             1.0, False),
    ("SLOW",      "SLOW DOWN 5S",        "chevron", "left",              1.0, False),
    ("DIAMOND",   "DIAMOND SKIN 30S",    "pickaxe", "diamond_pickaxe",   1.0, False),
    ("GOLD",      "GOLD SKIN 30S",       "pickaxe", "golden_pickaxe",    1.0, False),
    ("IRON",      "IRON SKIN 30S",       "pickaxe", "iron_pickaxe",      1.0, False),
    ("STONE",     "STONE SKIN 30S",      "pickaxe", "stone_pickaxe",     1.0, False),
    ("NETHERITE", "BEST SKIN 30S",       "pickaxe", "netherite_pickaxe", 1.0, False),
]


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

        self.panel_font = pygame.font.Font(None, 40)
        self.small_font = pygame.font.Font(None, 24)

        # Icons are cut and downscaled once here, never per frame. The atlas
        # arrives already scaled by BLOCK_SCALE_FACTOR (~7.5x).
        self.icons = {}
        for label, _sub, cat, name, scale, _new in COMMAND_ROWS:
            px = int(ICON_SIZE * scale)
            if cat == "chevron":
                self.icons[label] = make_chevron(name, px, (235, 235, 235))
            else:
                src = texture_atlas.subsurface(pygame.Rect(atlas_items[cat][name]))
                self.icons[label] = pygame.transform.smoothscale(src, (px, px))

        # Cache all static text surfaces rendered once at init, never per frame.
        self.panel_texts = {
            'COMMANDS_title': render_text_with_outline('COMMANDS', self.panel_font, (255, 255, 255), (0, 0, 0), 2),
            'NEW_COMMAND_title': render_text_with_outline('NEW COMMAND', self.panel_font, (255, 215, 0), (0, 0, 0), 2),
        }

        self.label_texts = {}  # label -> (label_surface, subtitle_surface)
        for label, subtitle, _cat, _name, _scale, _new in COMMAND_ROWS:
            lab = render_text_with_outline(label, self.panel_font, (255, 255, 255), (0, 0, 0), 2)
            sub = render_text_with_outline(subtitle, self.small_font, (170, 170, 180), (0, 0, 0), 1)
            self.label_texts[label] = (lab, sub)

        # Cache filled background surfaces for panels (sized for their content).
        commands_height = HEADER_H + len(COMMAND_ROWS) * ROW_H
        new_rows = [r for r in COMMAND_ROWS if r[5]]
        new_height = HEADER_H + len(new_rows) * ROW_H

        self.panel_boxes = {}
        commands_bg = pygame.Surface((PANEL_W, commands_height), pygame.SRCALPHA)
        commands_bg.fill((12, 12, 16, 200))
        self.panel_boxes['COMMANDS'] = commands_bg

        new_bg = pygame.Surface((PANEL_W, new_height), pygame.SRCALPHA)
        new_bg.fill((12, 12, 16, 200))
        self.panel_boxes['NEW_COMMAND'] = new_bg

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
        # Blit cached background and title, draw border
        box = self.panel_boxes[title_key]
        screen.blit(box, (x, y))
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
        lab, sub = self.label_texts[label]
        screen.blit(lab, (tx, y + 2))
        screen.blit(sub, (tx, y + lab.get_height() - 2))

    def draw_command_panel(self, screen):
        height = HEADER_H + len(COMMAND_ROWS) * ROW_H
        self._panel_box(screen, PANEL_X, PANEL_Y, PANEL_W, height, 'COMMANDS')
        y = PANEL_Y + HEADER_H
        for label, _subtitle, _cat, _name, _scale, _new in COMMAND_ROWS:
            self._panel_row(screen, PANEL_X, y, label)
            y += ROW_H

        new_rows = [r for r in COMMAND_ROWS if r[5]]
        if not new_rows:
            return
        ny = PANEL_Y + height + 36
        nh = HEADER_H + len(new_rows) * ROW_H
        self._panel_box(screen, PANEL_X, ny, PANEL_W, nh, 'NEW_COMMAND', accent=(255, 215, 0))
        y = ny + HEADER_H
        for label, _subtitle, _cat, _name, _scale, _new in new_rows:
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

    def draw_event_ticker(self, screen, events):
        """Render the active or incoming event. Nothing is drawn while idle."""
        if events.phase == "idle":
            return

        box = pygame.Surface((TICKER_W, TICKER_H), pygame.SRCALPHA)
        box.fill((12, 12, 16, 200))
        screen.blit(box, (TICKER_X, TICKER_Y))
        pygame.draw.rect(screen, events.color,
                         (TICKER_X, TICKER_Y, TICKER_W, TICKER_H), 3)

        if events.phase == "warning":
            # Same sine-brightness pulse the TNT fuse uses.
            period = 600
            t = pygame.time.get_ticks() % period
            brightness = (math.sin(t / period * 2 * math.pi) + 1) / 2
            col = tuple(int(c * (0.4 + 0.6 * brightness)) for c in events.color)
            label = render_text_with_outline(f"{events.name} INCOMING",
                                             self.panel_font, col, (0, 0, 0), 2)
            screen.blit(label, (TICKER_X + 12, TICKER_Y + 28))
            return

        label = render_text_with_outline(events.name, self.panel_font,
                                         events.color, (0, 0, 0), 2)
        screen.blit(label, (TICKER_X + 12, TICKER_Y + 6))

        secs = (events.remaining_ms() + 999) // 1000
        secs_surf = render_text_with_outline(f"{secs}s", self.panel_font,
                                             (255, 255, 255), (0, 0, 0), 2)
        screen.blit(secs_surf,
                    (TICKER_X + TICKER_W - secs_surf.get_width() - 12, TICKER_Y + 6))

        bar_x, bar_y = TICKER_X + 12, TICKER_Y + 54
        bar_w, bar_h = TICKER_W - 24, 22
        pygame.draw.rect(screen, (50, 50, 58), (bar_x, bar_y, bar_w, bar_h))
        filled = int(bar_w * (1.0 - events.progress()))
        pygame.draw.rect(screen, events.color, (bar_x, bar_y, filled, bar_h))

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


