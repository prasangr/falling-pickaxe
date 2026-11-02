"""The Nuke Meter: chat fills one shared bar, and a full bar drops the bomb.

Pure state, like events.py: this module performs no rendering. `Hud` reads the
public attributes and draws the bar. `main.py` does the damage on the frame
update() returns True.
"""
import pygame

CHARGING = "charging"
ARMED = "armed"

# What each commands.txt verb adds to the meter. Anything absent charges
# nothing, which is what keeps "SUBS:system:123" (a counter sync, not a viewer)
# and malformed lines off the bar.
CHARGE_POINTS = {
    "TNT": 1, "SPEED": 1, "BIG": 1, "SPIN": 1, "MULTIPLY": 1,
    "QUAKE": 1, "STORM": 1, "WATER": 1, "PICKAXE": 1,
    "NUKE": 5,
    "SUB": 20,
    "SUPER": 30,
}


class NukeMeter:
    FLASH_MS = 1800

    def __init__(self, capacity=100, passive_per_minute=10, countdown_ms=5000,
                 enabled=True, clock=pygame.time.get_ticks):
        # clock is injected so the state machine is testable without a display
        # or a real wall clock.
        self.clock = clock
        self.enabled = enabled
        self.capacity = capacity
        self.passive_per_minute = passive_per_minute
        self.countdown_ms = countdown_ms

        self.phase = CHARGING
        self.charge_level = 0.0
        self.detonated_by = None

        self._armed_at = 0
        self._detonated_at = None
        self._last_update = self.clock()

    # ---------- input ----------

    def charge(self, command, user):
        # Commands during the countdown are ignored rather than banked: the
        # next meter starts empty, so every nuke has to be earned again.
        if not self.enabled or self.phase != CHARGING:
            return
        self._add(CHARGE_POINTS.get(command, 0), user)

    def _add(self, points, user):
        self.charge_level += points
        if self.charge_level >= self.capacity:
            self.charge_level = self.capacity
            self.phase = ARMED
            self.detonated_by = user
            self._armed_at = self.clock()

    # ---------- read-only view for the HUD ----------

    def fraction(self):
        return self.charge_level / self.capacity

    def countdown_secs(self):
        remaining = self._armed_at + self.countdown_ms - self.clock()
        return (max(0, remaining) + 999) // 1000

    def flash(self):
        """1.0 on the frame of the blast, fading to 0.0 over FLASH_MS."""
        if self._detonated_at is None:
            return 0.0
        return max(0.0, 1.0 - (self.clock() - self._detonated_at) / self.FLASH_MS)

    # ---------- per-frame tick ----------

    def update(self):
        """Advance the meter. True only on the single frame the bomb goes off."""
        now = self.clock()
        elapsed = now - self._last_update
        self._last_update = now

        if not self.enabled:
            return False

        if self.phase == CHARGING:
            # A quiet chat must still reach a nuke. On a small channel it is
            # the only thing that will, for now.
            self._add(self.passive_per_minute * elapsed / 60000, None)

        if self.phase == ARMED and now >= self._armed_at + self.countdown_ms:
            self.phase = CHARGING
            self.charge_level = 0.0
            self._detonated_at = now
            return True
        return False
