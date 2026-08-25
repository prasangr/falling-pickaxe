"""Timed random events that give the stream a heartbeat.

Pure state: this module performs no rendering. `Hud` reads the public
attributes and draws the ticker. `main.py` reads the flags each frame.
"""
import random

import pygame

import chunk as chunk_module
from chunk import generate_noise_ranges

IDLE = "idle"
WARNING = "warning"
ACTIVE = "active"

WARNING_MS = 3000

# How long before an event fires the idle countdown appears. The event is
# already chosen by then, so the countdown deliberately withholds its name --
# the WARNING phase does the reveal.
COUNTDOWN_MS = 15000

EVENTS = [
    {"name": "ORE RUSH",    "duration_ms": 15000, "color": (255, 200,  40)},
    {"name": "TNT STORM",   "duration_ms": 12000, "color": (235,  60,  50)},
    {"name": "SLOW MOTION", "duration_ms": 10000, "color": ( 80, 210, 235)},
    {"name": "GOLD FEVER",  "duration_ms": 20000, "color": (250, 230,  90)},
    {"name": "EARTHQUAKE",  "duration_ms": 12000, "color": (215, 165, 105)},
    {"name": "THUNDERSTORM", "duration_ms": 15000, "color": (135, 195, 255)},
]

# Ore-heavy world generation for the ORE RUSH event. Blocks absent from
# this table simply do not generate while the event runs; obsidian is
# excluded deliberately because its 100 HP would blunt the payoff.
ORE_RUSH_WEIGHTS = {
    "stone": 5, "andesite": 3, "cobblestone": 3,
    "coal_ore": 15, "iron_ore": 15, "copper_ore": 12,
    "gold_ore": 12, "redstone_ore": 12, "lapis_ore": 10,
    "diamond_ore": 8, "emerald_ore": 5,
}


class EventManager:
    def __init__(self, interval_min_s=60, interval_max_s=90, enabled=True,
                 clock=pygame.time.get_ticks, rng=None):
        # clock and rng are injected so the state machine is testable
        # without a display or a real wall clock.
        self.clock = clock
        self.rng = rng if rng is not None else random.Random()
        self.enabled = enabled
        self.interval_min_ms = int(interval_min_s * 1000)
        self.interval_max_ms = int(interval_max_s * 1000)

        self.phase = IDLE
        self.event = None
        self.phase_ends_at = 0

        # Flags read by the game loop each frame.
        self.speed_override = None
        self.tnt_storm = False
        # Like tnt_storm: set here, acted on by the game loop, because quake
        # and rain need the space and camera this module deliberately lacks.
        self.quake = False
        self.storm = False

        self._saved_noise_ranges = None
        self._schedule_next()

    # ---------- scheduling ----------

    def _schedule_next(self):
        self.event = self.rng.choice(EVENTS)
        gap = self.rng.randint(self.interval_min_ms, self.interval_max_ms)
        self.phase = IDLE
        self.phase_ends_at = self.clock() + gap

    # ---------- read-only view for the HUD ----------

    @property
    def name(self):
        return self.event["name"] if self.event else ""

    @property
    def color(self):
        return self.event["color"] if self.event else (255, 255, 255)

    def remaining_ms(self):
        return max(0, self.phase_ends_at - self.clock())

    def countdown_secs(self):
        """Whole seconds until the next event, or None when it is too far off.

        Only meaningful while idle: once WARNING starts, the ticker names the
        event instead.
        """
        if self.phase != IDLE:
            return None
        remaining = self.remaining_ms()
        if remaining > COUNTDOWN_MS:
            return None
        return (remaining + 999) // 1000

    def progress(self):
        """0.0 at the start of ACTIVE, 1.0 at its end. 0.0 in other phases."""
        if self.phase != ACTIVE or not self.event:
            return 0.0
        total = self.event["duration_ms"]
        return 1.0 - (self.remaining_ms() / total)

    # ---------- per-frame tick ----------

    def update(self, hud):
        if not self.enabled:
            # If disabled while effects are applied, restore them immediately
            # and return to IDLE. Subsequent disabled calls are then a cheap no-op.
            if self.phase == ACTIVE:
                self._restore(hud)
                self._schedule_next()
            return

        now = self.clock()
        if now < self.phase_ends_at:
            return

        if self.phase == IDLE:
            self.phase = WARNING
            self.phase_ends_at = now + WARNING_MS
        elif self.phase == WARNING:
            self.phase = ACTIVE
            self.phase_ends_at = now + self.event["duration_ms"]
            self._apply(hud)
        elif self.phase == ACTIVE:
            self._restore(hud)
            self._schedule_next()

    # ---------- effects (filled in by Task 3) ----------

    def _apply(self, hud):
        name = self.event["name"]
        if name == "ORE RUSH":
            self._saved_noise_ranges = chunk_module.noise_ranges
            chunk_module.noise_ranges = generate_noise_ranges(ORE_RUSH_WEIGHTS)
        elif name == "TNT STORM":
            self.tnt_storm = True
        elif name == "SLOW MOTION":
            self.speed_override = "Slow"
        elif name == "GOLD FEVER":
            hud.ore_multiplier = 3
        elif name == "EARTHQUAKE":
            self.quake = True
        elif name == "THUNDERSTORM":
            self.storm = True

    def _restore(self, hud):
        # Everything is cleared unconditionally, not just the flag the
        # active event set. A leaked flag strands a live stream.
        if self._saved_noise_ranges is not None:
            chunk_module.noise_ranges = self._saved_noise_ranges
            self._saved_noise_ranges = None
        self.tnt_storm = False
        self.quake = False
        self.storm = False
        self.speed_override = None
        hud.ore_multiplier = 1
