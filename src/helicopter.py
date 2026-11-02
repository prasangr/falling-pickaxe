"""The helicopter bombing run: chat votes on a lane, then it bombs left, mid
and right, hitting the winning lane hardest.

Pure state, like events.py: this module performs no rendering and spawns no
TNT. `Hud` draws it, and `main.py` turns the bombs update() returns into TNT.
"""
import pygame

ARRIVING = "arriving"
VOTING = "voting"
BOMBING = "bombing"
GONE = "gone"

TNT = "tnt"
MEGA = "mega"

# Lane centres in world x, inside the bedrock walls at x=120 and x=960.
LANES = {"LEFT": 280, "MID": 540, "RIGHT": 800}

# Screen height the helicopter flies at. Below the top edge, so its name tag
# stays visible on a phone.
FLY_Y = 300

ARRIVE_MS = 1400
BOMBING_SPEED = 0.38  # Pixels per millisecond.

# Always flies left to right. It hovers for the whole vote, and from the right
# it would sit on top of the command menu just when viewers need to read it.
OFF_LEFT, OFF_RIGHT = -260, 1340
# The art is 300px wide, so this keeps all of it on screen and clear of the menu.
HOVER_X = 300


class Helicopter:
    def __init__(self, pilot, vote_ms=12000, clock=pygame.time.get_ticks):
        self.clock = clock
        self.pilot = pilot
        self.vote_ms = vote_ms

        self.phase = ARRIVING
        self.x = OFF_LEFT

        self._phase_started = self.clock()
        self._votes = {}
        self._plan = []

    # ---------- voting ----------

    def vote(self, user, lane):
        # Keyed by viewer: one vote each, and a later vote replaces the earlier
        # one. Otherwise whoever spams fastest decides every run.
        if self.phase == VOTING and lane in LANES:
            self._votes[user] = lane

    def tally(self):
        counts = {lane: 0 for lane in LANES}
        for lane in self._votes.values():
            counts[lane] += 1
        return counts

    def winner(self):
        """The lane with the most votes, or None on a tie or an empty chat."""
        counts = self.tally()
        best = max(counts.values())
        leaders = [lane for lane, count in counts.items() if count == best]
        return leaders[0] if best and len(leaders) == 1 else None

    def vote_secs_left(self):
        remaining = self._phase_started + self.vote_ms - self.clock()
        return (max(0, remaining) + 999) // 1000

    # ---------- flight ----------

    def _bomb_plan(self):
        winner = self.winner()
        bombs = []
        for lane, x in LANES.items():
            if winner is None:
                bombs += [(x - 50, TNT), (x + 50, TNT)]
            elif lane == winner:
                bombs += [(x - 90, TNT), (x, MEGA), (x + 90, TNT)]
            else:
                bombs.append((x, TNT))
        # In flight order, so they fall out from under the helicopter.
        return sorted(bombs, key=lambda b: b[0])

    def update(self):
        """Advance the flight. Returns the [(x, kind)] dropped this frame."""
        now = self.clock()
        elapsed = now - self._phase_started

        if self.phase == ARRIVING:
            progress = min(1.0, elapsed / ARRIVE_MS)
            self.x = OFF_LEFT + (HOVER_X - OFF_LEFT) * progress
            if progress >= 1.0:
                self.phase = VOTING
                self._phase_started = now
            return []

        if self.phase == VOTING:
            if elapsed >= self.vote_ms:
                self._plan = self._bomb_plan()
                self.phase = BOMBING
                self._phase_started = now
            return []

        if self.phase == BOMBING:
            self.x = HOVER_X + BOMBING_SPEED * elapsed
            dropped = []
            while self._plan and self.x >= self._plan[0][0]:
                dropped.append(self._plan.pop(0))
            if self.x >= OFF_RIGHT:
                self.phase = GONE
            return dropped

        return []


class Dispatcher:
    """Decides when a helicopter may fly: one at a time, a cooldown between
    summons, and one on its own when nobody has called for a while."""

    def __init__(self, cooldown_ms=30000, auto_ms=240000, vote_ms=12000, enabled=True,
                 clock=pygame.time.get_ticks):
        self.clock = clock
        self.enabled = enabled
        self.cooldown_ms = cooldown_ms
        self.auto_ms = auto_ms
        self.vote_ms = vote_ms

        self.active = None
        self._ready_at = 0
        self._auto_at = self.clock() + auto_ms

    def _launch(self, pilot):
        self.active = Helicopter(pilot, vote_ms=self.vote_ms, clock=self.clock)

    def request(self, user):
        """A viewer typed !heli. True if it launched; spam just gets False."""
        if not self.enabled or self.active is not None or self.clock() < self._ready_at:
            return False
        self._launch(user)
        return True

    def vote(self, user, lane):
        if self.active is not None:
            self.active.vote(user, lane)

    def update(self):
        """Advance any flight. Returns the [(x, kind)] dropped this frame."""
        if not self.enabled:
            return []

        now = self.clock()
        if self.active is None:
            if now >= self._auto_at:
                self._launch(None)
            return []

        dropped = self.active.update()
        if self.active.phase == GONE:
            self.active = None
            self._ready_at = now + self.cooldown_ms
            self._auto_at = now + self.auto_ms
        return dropped
