"""Time-of-day tint for the background image.

Pure colour maths: no pygame, no clock of its own. `main.py` asks for a tint
and multiplies the background by it, so this module stays testable.
"""

# (hour, RGB multiplier). Midday is white on purpose -- the artwork is already
# lit for daytime, so noon leaves it untouched and every other hour departs
# from it. Tuned by eye; move the rows, not the code.
KEYFRAMES = [
    ( 0, ( 55,  65, 120)),  # deep night
    ( 5, ( 80,  85, 135)),  # pre-dawn
    ( 7, (255, 170, 130)),  # sunrise
    (10, (255, 250, 245)),  # morning
    (14, (255, 255, 255)),  # midday: untouched
    (18, (255, 190, 140)),  # golden hour
    (20, (170, 130, 150)),  # dusk
    (22, ( 70,  75, 130)),  # night
    (24, ( 55,  65, 120)),  # same as hour 0, so the wrap is seamless
]


def tint_for(hour):
    """RGB multiplier for a fractional hour. Wraps, so 25.5 means 01:30."""
    hour %= 24
    for (h0, c0), (h1, c1) in zip(KEYFRAMES, KEYFRAMES[1:]):
        if h0 <= hour <= h1:
            span = h1 - h0
            t = 0.0 if span == 0 else (hour - h0) / span
            return tuple(int(a + (b - a) * t) for a, b in zip(c0, c1))
    return KEYFRAMES[-1][1]  # Unreachable while the table ends at 24.
