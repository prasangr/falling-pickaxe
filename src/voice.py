"""The pickaxe's personality: what it says and how it feels right now.

Pure state, like events.py: this module performs no rendering. `Hud` draws the
face and speech bubble from the public attributes.

Edit LINES freely. {USER} becomes the viewer's name, and a line has to stay
short enough to read on a phone (test_every_line_fits_in_a_speech_bubble).
"""
import random

import pygame

NEUTRAL = "neutral"
SCARED = "scared"
HAPPY = "happy"
DIZZY = "dizzy"

BUBBLE_MS = 2800
NAME_MAX = 14
LINE_MAX = 30

LINES = {
    "TNT": (SCARED, ["{USER} BHAI KYU?!", "NOT THE TNT!", "{USER}, I TRUSTED YOU",
                     "ARRE YAAR, TNT AGAIN?"]),
    "NUKE": (SCARED, ["{USER}, SERIOUSLY?!", "BIG BOOM INCOMING", "BHAI RUKO RUKO RUKO"]),
    "BIG": (HAPPY, ["I FEEL POWERFUL", "WHO'S THE BOSS NOW?"]),
    "SPIN": (DIZZY, ["I'M GONNA BE SICK", "{USER} STOP THE RIDE"]),
    "MULTIPLY": (HAPPY, ["WHO ARE THESE GUYS?", "THERE'S MORE OF ME?!"]),
    "QUAKE": (SCARED, ["THE GROUND IS ANGRY", "{USER} STOP SHAKING ME"]),
    "STORM": (SCARED, ["I'M LITERALLY METAL!", "WHO ORDERED LIGHTNING?"]),
    "WATER": (HAPPY, ["AAH, THANKS {USER}", "COOL. VERY COOL."]),
    "FAST": (SCARED, ["TOO FAST TOO FAST"]),
    "SLOW": (HAPPY, ["FINALLY, A BREAK"]),
    "SKIN": (HAPPY, ["OOH, FANCY", "DO I LOOK RICH NOW?"]),
    "SUB": (HAPPY, ["THANK YOU {USER}!", "{USER} JOINED US!"]),
    "SUPER": (HAPPY, ["{USER} YOU LEGEND!"]),
    "ARMED": (SCARED, ["OH NO OH NO OH NO", "WHO FILLED THE METER?!"]),
    "DETONATE": (SCARED, ["AAAAAAAAAAAH!!!"]),
    "RECORD": (HAPPY, ["NEW RECORD! I'M THE BEST"]),
    "HELI": (SCARED, ["{USER} CALLED BACKUP", "{USER} SENT A CHOPPER!"]),
    "HELI_AUTO": (SCARED, ["IS THAT A HELICOPTER?!", "WHO CALLED THAT THING?!"]),
    "BOMBING": (SCARED, ["INCOMING! TAKE COVER!"]),
    "LAVA": (SCARED, ["HOT HOT HOT HOT!", "SOMEBODY TYPE WATER!"]),
    "IDLE": (NEUTRAL, ["HOW DEEP ARE WE?", "IS ANYONE WATCHING?", "TYPE TNT, I DARE YOU",
                       "HELLO? ANYONE THERE?", "SOMEBODY CALL THE HELI",
                       "WHY DO I KEEP FALLING?", "BHAI, KOI HAI?"]),
}

# Every pickaxe material shares one set of lines.
SKIN_LABELS = {"WOOD", "STONE", "IRON", "GOLD", "DIAMOND", "NETHERITE"}


def voice_key(label):
    """The LINES entry for a command label from hud.feed_label()."""
    return "SKIN" if label in SKIN_LABELS else label


def display_name(user):
    """A viewer's name in a form that is safe to draw on stream.

    The stream font only has Latin glyphs, so anything else would render as a
    row of empty boxes. It also caps the length: a long handle otherwise runs
    off both edges of a phone screen.
    """
    name = str(user or "").lstrip("@")
    name = "".join(c for c in name if c.isascii() and c.isprintable()).strip()
    return name[:NAME_MAX].upper() or "SOMEONE"


class PickaxeVoice:
    def __init__(self, enabled=True, idle_min_ms=25000, idle_max_ms=45000,
                 clock=pygame.time.get_ticks, rng=None):
        # clock and rng are injected so this is testable without a display.
        self.clock = clock
        self.rng = rng if rng is not None else random.Random()
        self.enabled = enabled
        self.idle_min_ms = idle_min_ms
        self.idle_max_ms = idle_max_ms

        self.line = None
        self.mood = NEUTRAL

        self._line_ends_at = 0
        self._last_template = None
        self._next_idle_at = self.clock() + self._idle_gap()

    def _idle_gap(self):
        return self.rng.randint(self.idle_min_ms, self.idle_max_ms)

    def react(self, key, user=None, force=False):
        """Say something about `key`. Chat cannot talk over a line in progress,
        or a busy stream becomes flicker; big moments pass force=True."""
        if not self.enabled or key not in LINES:
            return
        if self.line is not None and not force:
            return

        mood, templates = LINES[key]
        options = [t for t in templates if t != self._last_template] or templates
        template = self.rng.choice(options)

        # str.replace, not str.format: a viewer's name is untrusted, and
        # one called "{0}" must not be able to crash a live stream.
        self.line = template.replace("{USER}", display_name(user))
        self.mood = mood
        self._last_template = template
        self._line_ends_at = self.clock() + BUBBLE_MS
        self._next_idle_at = self._line_ends_at + self._idle_gap()

    def update(self):
        now = self.clock()
        if self.line is not None and now >= self._line_ends_at:
            self.line = None
            self.mood = NEUTRAL
        if self.line is None and now >= self._next_idle_at:
            self.react("IDLE")
