"""QUAKE and STORM: the two commands that act on the world rather than the axe.

Rain is drawn in screen space, so it needs no camera transform. Lightning
reuses tnt.blast, so explosions and strikes share one damage rule.
"""
import math
import random

import pygame
import pymunk

from constants import BLOCK_SIZE, INTERNAL_HEIGHT, INTERNAL_WIDTH
from chunk import block_at
from tnt import blast


def trigger_quake(space, camera, intensity=26, impulse=900, frames=90):
    """Shake the view and jolt every loose body in the world.

    Stateless: the camera's own decay handles the duration, so there is no
    timer to keep. Static bodies (the blocks) are skipped -- shoving those
    would tear the terrain apart.
    """
    camera.shake(frames, intensity)
    for body in space.bodies:
        if body.body_type != pymunk.Body.DYNAMIC:
            continue
        body.apply_impulse_at_local_point(
            (random.uniform(-impulse, impulse), random.uniform(-impulse, impulse) * 0.4))


class Storm:
    """Rain, lightning and thunder for a fixed span of time."""

    def __init__(self, duration_ms=12000, strike_interval_ms=900,
                 strike_radius_blocks=3, clock=pygame.time.get_ticks):
        self.clock = clock
        self.strike_interval_ms = strike_interval_ms
        self.strike_radius = strike_radius_blocks * BLOCK_SIZE
        self.ends_at = self.clock() + duration_ms
        self.next_strike_at = self.clock() + strike_interval_ms
        self.flash = 0  # Frames of white overlay left.
        self.strikes = 0
        self.bolt_x = None
        # Screen-space droplets: x, y, fall speed, streak length.
        self.drops = [[random.uniform(0, INTERNAL_WIDTH),
                       random.uniform(0, INTERNAL_HEIGHT),
                       random.uniform(28, 46),
                       random.uniform(26, 60)] for _ in range(220)]

    def expired(self):
        return self.clock() >= self.ends_at

    def extend(self, duration_ms):
        self.ends_at = self.clock() + duration_ms

    def update(self, pickaxe, camera, sound_manager):
        for drop in self.drops:
            drop[1] += drop[2]
            if drop[1] > INTERNAL_HEIGHT:
                drop[1] = -drop[3]
                drop[0] = random.uniform(0, INTERNAL_WIDTH)

        if self.flash > 0:
            self.flash -= 1

        now = self.clock()
        if now < self.next_strike_at:
            return
        self.next_strike_at = now + self.strike_interval_ms
        self.strikes += 1
        self.flash = 4

        # Strike near the pickaxe, so viewers always see the damage land.
        x = pickaxe.body.position.x + random.uniform(-6, 6) * BLOCK_SIZE
        y = pickaxe.body.position.y + random.uniform(-2, 6) * BLOCK_SIZE
        self.bolt_x = x
        blast((x, y), self.strike_radius, 120)
        camera.shake(12, 14)
        if sound_manager is not None:
            sound_manager.play_sound("tnt")  # Doubles as thunder.

    def draw(self, screen, camera):
        rain = (170, 195, 235)
        for x, y, _speed, length in self.drops:
            pygame.draw.line(screen, rain, (x, y), (x - 4, y + length), 2)

        if self.flash > 0:
            overlay = pygame.Surface((INTERNAL_WIDTH, INTERNAL_HEIGHT), pygame.SRCALPHA)
            overlay.fill((255, 255, 255, 26 * self.flash))
            screen.blit(overlay, (0, 0))


class Water:
    """A pour of water: droplets fall, splash, and fill a pool that drains.

    Deliberately a small volume in world space rather than a screen tint --
    the axe should look partly submerged, with its top still clear.
    """

    POUR_MS = 1100   # How long droplets keep falling in.
    DRAIN_MS = 1200  # How long the pool takes to empty at the end.

    def __init__(self, x, y, duration_ms=10000, width_blocks=3.2,
                 depth_blocks=1.2, clock=pygame.time.get_ticks):
        self.clock = clock
        self.w = width_blocks * BLOCK_SIZE
        self.h = depth_blocks * BLOCK_SIZE
        self.cx = x
        self.top = y - BLOCK_SIZE * 0.15  # Axe's top stays out of the water.
        self.started_at = self.clock()
        self.ends_at = self.started_at + duration_ms
        self.drops = []      # [x, y, speed, length]
        self.splashes = []   # [x, y, vx, vy, life]
        self.ripple_seed = random.random() * 100

    # ---------- state ----------

    def expired(self):
        return self.clock() >= self.ends_at

    def fill(self):
        """0..1 as the pour lands, back to 0 as it drains."""
        now = self.clock()
        poured = min(1.0, (now - self.started_at) / self.POUR_MS)
        remaining = self.ends_at - now
        draining = max(0.0, min(1.0, remaining / self.DRAIN_MS))
        return min(poured, draining)

    def depth(self):
        return self.h * self.fill()

    def covers(self, x, y):
        """Is this point submerged? Buoyancy needs real water, so a pool that
        has barely started filling does not float anything yet."""
        d = self.depth()
        if d < self.h * 0.35:
            return False
        return abs(x - self.cx) <= self.w / 2 and self.top <= y <= self.top + d

    def _open_rects(self, left, right, top, bottom):
        """Clip a world region to the cells that are actually mined out.

        Water takes the shape of the shaft, so the pool pours around the
        terrain instead of floating as a rectangle over it.
        """
        if bottom <= top or right <= left:
            return []
        rects = []
        for gx in range(int(left // BLOCK_SIZE), int(right // BLOCK_SIZE) + 1):
            for gy in range(int(top // BLOCK_SIZE), int(bottom // BLOCK_SIZE) + 1):
                if block_at(gx * BLOCK_SIZE + BLOCK_SIZE / 2,
                            gy * BLOCK_SIZE + BLOCK_SIZE / 2) is not None:
                    continue  # Solid rock: no water here.
                x0 = max(left, gx * BLOCK_SIZE)
                x1 = min(right, (gx + 1) * BLOCK_SIZE)
                y0 = max(top, gy * BLOCK_SIZE)
                y1 = min(bottom, (gy + 1) * BLOCK_SIZE)
                if x1 > x0 and y1 > y0:
                    rects.append((x0, y0, x1 - x0, y1 - y0))
        return rects

    def cells(self):
        """World rects the pool occupies -- only where the rock is mined out."""
        d = self.depth()
        if d <= 1:
            return []
        return self._open_rects(self.cx - self.w / 2, self.cx + self.w / 2,
                                self.top, self.top + d)

    # ---------- per-frame ----------

    def update(self, pickaxe):
        px, py = pickaxe.body.position.x, pickaxe.body.position.y
        self.cx += (px - self.cx) * 0.12
        self.top += ((py - BLOCK_SIZE * 0.15) - self.top) * 0.10

        # Droplets only while pouring.
        if self.clock() - self.started_at < self.POUR_MS:
            for _ in range(4):
                self.drops.append([
                    self.cx + random.uniform(-self.w * 0.45, self.w * 0.45),
                    self.top - BLOCK_SIZE * random.uniform(3.5, 7.0),
                    random.uniform(34, 52),
                    random.uniform(18, 40)])

        surface = self.top
        still_falling = []
        for drop in self.drops:
            drop[1] += drop[2]
            if drop[1] >= surface:
                # Landed: throw a little splash sideways off the surface.
                for _ in range(3):
                    self.splashes.append([drop[0], surface,
                                          random.uniform(-6, 6),
                                          random.uniform(-9, -3), 14])
            else:
                still_falling.append(drop)
        self.drops = still_falling

        alive = []
        for sp in self.splashes:
            sp[0] += sp[2]
            sp[1] += sp[3]
            sp[3] += 0.8  # Gravity on the spray.
            sp[4] -= 1
            if sp[4] > 0:
                alive.append(sp)
        self.splashes = alive

    # ---------- drawing ----------

    def draw(self, screen, camera):
        ox, oy = camera.offset_x, camera.offset_y
        drop_color = (150, 210, 255)

        # Falling droplets, drawn behind the pool surface.
        for x, y, _speed, length in self.drops:
            pygame.draw.line(screen, drop_color,
                             (x - ox, y - oy), (x - ox, y - oy + length), 3)

        t = self.clock() / 260 + self.ripple_seed
        for rx, ry, rw, rh in self.cells():
            surf = pygame.Surface((int(rw), int(rh)), pygame.SRCALPHA)
            surf.fill((60, 140, 235, 125))
            # Only cells at the pool's surface get the wavy highlight -- a
            # flat edge is what made this read as a blue box.
            if ry - self.top < 2:
                for i in range(0, int(rw), 6):
                    wave = math.sin(t + (rx + i) / 26) * 3
                    pygame.draw.line(surf, (170, 220, 255, 220),
                                     (i, 3 + wave), (i + 6, 3 + wave), 5)
            screen.blit(surf, (rx - ox, ry - oy))

        for sx, sy, _vx, _vy, life in self.splashes:
            pygame.draw.circle(screen, drop_color,
                               (int(sx - ox), int(sy - oy)), max(1, life // 4))
