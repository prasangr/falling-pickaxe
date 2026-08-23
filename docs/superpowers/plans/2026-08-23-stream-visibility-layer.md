# Stream Visibility Layer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the game's seven existing chat commands visible on stream with an icon panel, add a live subscriber counter, and give the stream a heartbeat with a four-event random event system.

**Architecture:** One new pure-logic module (`src/events.py`) holding a four-phase state machine that exposes plain attribute flags. The existing `Hud` class gains all rendering — command panel, subscriber counter, event ticker. `main.py` reads the event flags each frame; no callbacks are threaded through the game loop. Icons come from the texture atlas that already loads them.

**Tech Stack:** Python 3.12, pygame 2.6.1, pymunk 6.11.1. No new dependencies. No new art assets. No test framework — plain `assert` run via `python test_events.py`.

**Spec:** `docs/superpowers/specs/2026-08-23-stream-visibility-layer-design.md`

## Global Constraints

- **No `!` prefix on screen.** The panel renders `TNT`, never `!tnt`. Spec §5.1.
- **No new PNG assets.** Eight icons come from the existing atlas; FAST/SLOW are drawn with `pygame.draw.polygon`; BIG reuses `wooden_pickaxe` at 1.4×. Spec §5.1.
- **No new pip dependencies.** `requirements.txt` is not modified.
- **No YouTube API key.** `src/youtube.py` stays unwired. Spec §5.2.
- **Internal render surface is fixed at 1080 × 1920.** All geometry is absolute against that surface, never against window size. Spec §5.
- **The game is launched from the project root** (`.venv/Scripts/python ./src/main.py`), which puts `src/` on `sys.path` and makes `config.py`'s relative `open("config.json")` resolve. Every command in this plan assumes CWD = project root.
- **Zero means hidden:** the subscriber counter must not render `0`. Spec §5.2.
- **Event flags must always be restored on event end** — a leaked flag strands a live stream in permanent slow motion. Spec §8.

### Deviation from the spec, recorded

Spec §6.3 lists `EventManager.draw(surface)`. This plan moves ticker rendering into `Hud.draw_event_ticker(surface, events)` instead. Rationale: it keeps `events.py` free of any pygame rendering call, which is what lets the whole state machine be tested with an injected fake clock and no display. All other §6.3 attributes are implemented as written.

## File Structure

| File | Responsibility |
|---|---|
| `src/events.py` | **New.** Event state machine + the four event definitions. Pure logic, no rendering. |
| `src/hud.py` | **Modified.** All rendering: existing ore column, plus command panel, subscriber counter, event ticker. Owns `ore_multiplier` and `add_ore()`. |
| `src/block.py` | **Modified.** `ORE_DROPS` table replaces the eight-branch drop chain. |
| `src/main.py` | **Modified.** Wires `EventManager`, parses `SUBS`, reads event flags. |
| `config.json` | **Modified.** Four new keys. |
| `test_events.py` | **New.** Project-root self-check for the event cycle and the ore multiplier. |
| `README.md` | **Modified.** Streamer.bot setup for the new commands. |

---

### Task 1: Ore drop table and multiplier

Replaces the eight-branch drop chain with a lookup table, and puts the GOLD FEVER multiplier in exactly one place. Everything later that touches ore counts depends on this.

**Files:**
- Modify: `src/block.py:115-130` (the drop chain), plus a new module constant
- Modify: `src/hud.py:34-50` (`Hud.__init__`), plus a new method
- Test: `test_events.py` (created here)

**Interfaces:**
- Consumes: nothing
- Produces:
  - `block.ORE_DROPS: dict[str, tuple[str, int, int]]` — block name → (hud key, min qty, max qty)
  - `Hud.ore_multiplier: int` — defaults to `1`
  - `Hud.add_ore(key: str, lo: int, hi: int) -> None`

- [ ] **Step 1: Write the failing test**

Create `test_events.py` at the **project root** (not in `src/`):

```python
"""Self-checks for the stream visibility layer.

Run from the project root:  python test_events.py
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))


def test_add_ore_applies_multiplier():
    from hud import Hud

    # Bypass __init__ so the test needs no pygame font/display setup.
    h = Hud.__new__(Hud)
    h.amounts = {"diamond": 0}
    h.ore_multiplier = 1
    h.add_ore("diamond", 2, 2)
    assert h.amounts["diamond"] == 2, h.amounts

    h.ore_multiplier = 3
    h.add_ore("diamond", 2, 2)
    assert h.amounts["diamond"] == 8, h.amounts  # 2 + (2 * 3)


def test_ore_drops_table_covers_every_ore():
    import block

    expected = {
        "coal_ore", "iron_ore", "copper_ore", "gold_ore",
        "diamond_ore", "emerald_ore", "redstone_ore", "lapis_ore",
    }
    assert set(block.ORE_DROPS) == expected, set(block.ORE_DROPS)
    # Quantities must match the pre-refactor behaviour exactly.
    assert block.ORE_DROPS["redstone_ore"] == ("redstone", 4, 5)
    assert block.ORE_DROPS["lapis_ore"] == ("lapis_lazuli", 4, 8)
    assert block.ORE_DROPS["diamond_ore"] == ("diamond", 1, 1)


if __name__ == "__main__":
    failures = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"PASS  {name}")
            except AssertionError as exc:
                failures += 1
                print(f"FAIL  {name}: {exc}")
    print(f"\n{failures} failure(s)")
    sys.exit(1 if failures else 0)
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
.venv/Scripts/python test_events.py
```

Expected: `FAIL` / `AttributeError` — `Hud` has no attribute `add_ore`, and `block` has no attribute `ORE_DROPS`.

- [ ] **Step 3: Add `ORE_DROPS` to `src/block.py`**

Insert directly after the imports at the top of `src/block.py` (after line 4):

```python
# Block name -> (HUD counter key, min drop, max drop).
# Quantities preserve the original per-ore behaviour exactly.
ORE_DROPS = {
    "coal_ore":     ("coal", 1, 1),
    "iron_ore":     ("iron_ingot", 1, 1),
    "copper_ore":   ("copper_ingot", 1, 1),
    "gold_ore":     ("gold_ingot", 1, 1),
    "diamond_ore":  ("diamond", 1, 1),
    "emerald_ore":  ("emerald", 1, 1),
    "redstone_ore": ("redstone", 4, 5),
    "lapis_ore":    ("lapis_lazuli", 4, 8),
}
```

- [ ] **Step 4: Replace the drop chain in `src/block.py`**

In `Block.update()`, replace the whole `if self.name == "coal_ore": ... elif self.name == "lapis_ore": ...` chain (lines 115-130) with:

```python
            drop = ORE_DROPS.get(self.name)
            if drop:
                hud.add_ore(*drop)
```

Leave the two lines above it (`self.destroyed = True` and `space.remove(...)`) untouched.

- [ ] **Step 5: Add the multiplier and `add_ore()` to `src/hud.py`**

In `Hud.__init__`, immediately after the `self.amounts = {...}` block (after line 43), add:

```python
        # Multiplied by the GOLD FEVER event; 1 means normal drops.
        self.ore_multiplier = 1
```

Then add this method to the `Hud` class, directly after `update_amounts()`:

```python
    def add_ore(self, key, lo, hi):
        """Credit an ore drop, applying the active event multiplier."""
        self.amounts[key] += random.randint(lo, hi) * self.ore_multiplier
```

Add `import random` to the top of `src/hud.py` (it currently imports only `pygame` and from `constants`).

- [ ] **Step 6: Run the test to verify it passes**

```bash
.venv/Scripts/python test_events.py
```

Expected: `PASS test_add_ore_applies_multiplier`, `PASS test_ore_drops_table_covers_every_ore`, `0 failure(s)`.

- [ ] **Step 7: Commit**

```bash
git add src/block.py src/hud.py test_events.py
git commit -m "refactor: replace ore drop chain with ORE_DROPS table and add_ore()"
```

---

### Task 2: Event state machine core

The four-phase timing loop, with no effects wired yet. Effects land in Task 3.

**Files:**
- Create: `src/events.py`
- Test: `test_events.py` (append)

**Interfaces:**
- Consumes: nothing from Task 1
- Produces:
  - `events.IDLE`, `events.WARNING`, `events.ACTIVE` — the phase string constants `"idle"`, `"warning"`, `"active"`
  - `events.WARNING_MS = 3000`
  - `events.EVENTS: list[dict]` — each `{"name": str, "duration_ms": int, "color": tuple[int,int,int]}`
  - `EventManager(interval_min_s=60, interval_max_s=90, enabled=True, clock=pygame.time.get_ticks, rng=None)`
  - `EventManager.phase: str`, `.name: str`, `.color: tuple`, `.speed_override: str | None`, `.tnt_storm: bool`
  - `EventManager.remaining_ms() -> int`, `.progress() -> float`, `.update(hud) -> None`

- [ ] **Step 1: Write the failing test**

Append to `test_events.py`, **above** the `if __name__ == "__main__":` block:

```python
class FakeClock:
    """Injected in place of pygame.time.get_ticks."""

    def __init__(self):
        self.now = 0

    def __call__(self):
        return self.now

    def advance(self, ms):
        self.now += ms


class StubRng:
    """Forces a chosen event and a fixed gap, so cycles are deterministic."""

    def __init__(self, event_name, gap_ms):
        self.event_name = event_name
        self.gap_ms = gap_ms

    def choice(self, seq):
        return next(e for e in seq if e["name"] == self.event_name)

    def randint(self, a, b):
        return self.gap_ms


class FakeHud:
    def __init__(self):
        self.ore_multiplier = 1


def _manager(event_name, gap_ms=60000):
    import events

    clock = FakeClock()
    mgr = events.EventManager(clock=clock, rng=StubRng(event_name, gap_ms))
    return mgr, clock


def test_phases_advance_on_schedule():
    import events

    mgr, clock = _manager("SLOW MOTION")
    assert mgr.phase == events.IDLE, mgr.phase

    # One millisecond before the gap elapses, still idle.
    clock.advance(59999)
    mgr.update(FakeHud())
    assert mgr.phase == events.IDLE, mgr.phase

    # Gap elapsed -> warning.
    clock.advance(1)
    mgr.update(FakeHud())
    assert mgr.phase == events.WARNING, mgr.phase

    # Warning lasts exactly WARNING_MS.
    clock.advance(events.WARNING_MS - 1)
    mgr.update(FakeHud())
    assert mgr.phase == events.WARNING, mgr.phase

    clock.advance(1)
    mgr.update(FakeHud())
    assert mgr.phase == events.ACTIVE, mgr.phase


def test_active_phase_ends_and_reschedules():
    import events

    mgr, clock = _manager("SLOW MOTION")
    clock.advance(60000)
    mgr.update(FakeHud())          # -> warning
    clock.advance(events.WARNING_MS)
    mgr.update(FakeHud())          # -> active

    duration = mgr.event["duration_ms"]
    clock.advance(duration)
    mgr.update(FakeHud())          # -> idle, next event scheduled
    assert mgr.phase == events.IDLE, mgr.phase
    assert mgr.remaining_ms() == 60000, mgr.remaining_ms()


def test_disabled_manager_never_leaves_idle():
    import events

    clock = FakeClock()
    mgr = events.EventManager(
        enabled=False, clock=clock, rng=StubRng("TNT STORM", 60000)
    )
    clock.advance(10_000_000)
    mgr.update(FakeHud())
    assert mgr.phase == events.IDLE, mgr.phase
    assert mgr.tnt_storm is False


def test_progress_runs_zero_to_one_across_active():
    import events

    mgr, clock = _manager("GOLD FEVER")
    clock.advance(60000)
    mgr.update(FakeHud())
    clock.advance(events.WARNING_MS)
    mgr.update(FakeHud())
    assert mgr.progress() == 0.0, mgr.progress()

    duration = mgr.event["duration_ms"]
    clock.advance(duration // 2)
    assert abs(mgr.progress() - 0.5) < 0.01, mgr.progress()
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
.venv/Scripts/python test_events.py
```

Expected: `ModuleNotFoundError: No module named 'events'`.

- [ ] **Step 3: Create `src/events.py`**

```python
"""Timed random events that give the stream a heartbeat.

Pure state: this module performs no rendering. `Hud` reads the public
attributes and draws the ticker. `main.py` reads the flags each frame.
"""
import random

import pygame

IDLE = "idle"
WARNING = "warning"
ACTIVE = "active"

WARNING_MS = 3000

EVENTS = [
    {"name": "ORE RUSH",    "duration_ms": 15000, "color": (255, 200,  40)},
    {"name": "TNT STORM",   "duration_ms": 12000, "color": (235,  60,  50)},
    {"name": "SLOW MOTION", "duration_ms": 10000, "color": ( 80, 210, 235)},
    {"name": "GOLD FEVER",  "duration_ms": 20000, "color": (250, 230,  90)},
]


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

    def progress(self):
        """0.0 at the start of ACTIVE, 1.0 at its end. 0.0 in other phases."""
        if self.phase != ACTIVE or not self.event:
            return 0.0
        total = self.event["duration_ms"]
        return 1.0 - (self.remaining_ms() / total)

    # ---------- per-frame tick ----------

    def update(self, hud):
        if not self.enabled:
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
        pass

    def _restore(self, hud):
        pass
```

- [ ] **Step 4: Run the test to verify it passes**

```bash
.venv/Scripts/python test_events.py
```

Expected: all six tests `PASS`, `0 failure(s)`.

- [ ] **Step 5: Commit**

```bash
git add src/events.py test_events.py
git commit -m "feat: add event state machine with injected clock and rng"
```

---

### Task 3: Event effects — apply and restore

Wires the four events to their mechanisms. The restore assertions here are the most important test in the project: a leaked flag strands a live stream.

**Files:**
- Modify: `src/events.py` (`_apply`, `_restore`, plus `ORE_RUSH_WEIGHTS`)
- Test: `test_events.py` (append)

**Interfaces:**
- Consumes: `Hud.ore_multiplier` from Task 1; `EventManager` from Task 2
- Produces: `events.ORE_RUSH_WEIGHTS: dict[str, int]`; `_apply`/`_restore` behaviour on `chunk.noise_ranges`, `hud.ore_multiplier`, `self.tnt_storm`, `self.speed_override`

- [ ] **Step 1: Write the failing test**

Append to `test_events.py`, above the `if __name__ == "__main__":` block:

```python
def _run_full_cycle(event_name, hud):
    """Drive one event from idle through active and back to idle."""
    import events

    mgr, clock = _manager(event_name)
    clock.advance(60000)
    mgr.update(hud)                       # -> warning
    clock.advance(events.WARNING_MS)
    mgr.update(hud)                       # -> active
    return mgr, clock


def test_slow_motion_sets_and_clears_speed_override():
    import events

    hud = FakeHud()
    mgr, clock = _run_full_cycle("SLOW MOTION", hud)
    assert mgr.speed_override == "Slow", mgr.speed_override

    clock.advance(mgr.event["duration_ms"])
    mgr.update(hud)
    assert mgr.speed_override is None, mgr.speed_override


def test_tnt_storm_sets_and_clears_flag():
    hud = FakeHud()
    mgr, clock = _run_full_cycle("TNT STORM", hud)
    assert mgr.tnt_storm is True

    clock.advance(mgr.event["duration_ms"])
    mgr.update(hud)
    assert mgr.tnt_storm is False


def test_gold_fever_sets_and_clears_multiplier():
    hud = FakeHud()
    mgr, clock = _run_full_cycle("GOLD FEVER", hud)
    assert hud.ore_multiplier == 3, hud.ore_multiplier

    clock.advance(mgr.event["duration_ms"])
    mgr.update(hud)
    assert hud.ore_multiplier == 1, hud.ore_multiplier


def test_ore_rush_swaps_and_restores_noise_ranges():
    import chunk as chunk_module

    original = chunk_module.noise_ranges
    hud = FakeHud()
    mgr, clock = _run_full_cycle("ORE RUSH", hud)
    assert chunk_module.noise_ranges is not original

    clock.advance(mgr.event["duration_ms"])
    mgr.update(hud)
    assert chunk_module.noise_ranges is original, "noise_ranges not restored"


def test_ore_rush_weights_exclude_hard_filler_blocks():
    import events

    for excluded in ("obsidian", "diorite", "granite", "mossy_cobblestone"):
        assert excluded not in events.ORE_RUSH_WEIGHTS, excluded
    assert events.ORE_RUSH_WEIGHTS["diamond_ore"] > events.ORE_RUSH_WEIGHTS["stone"]


def test_two_consecutive_cycles_do_not_overlap():
    """The second event must not start while the first is still active."""
    import events

    hud = FakeHud()
    mgr, clock = _run_full_cycle("TNT STORM", hud)
    assert mgr.phase == events.ACTIVE

    clock.advance(mgr.event["duration_ms"])
    mgr.update(hud)
    assert mgr.phase == events.IDLE, mgr.phase
    assert mgr.tnt_storm is False

    # Nothing fires again until a fresh gap has elapsed.
    clock.advance(59999)
    mgr.update(hud)
    assert mgr.phase == events.IDLE, mgr.phase
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
.venv/Scripts/python test_events.py
```

Expected: `FAIL test_slow_motion_sets_and_clears_speed_override: None`, plus failures on the storm, gold fever, ore rush, and `ORE_RUSH_WEIGHTS` tests — `_apply` is still `pass`.

- [ ] **Step 3: Add the ORE RUSH weights to `src/events.py`**

Add these imports at the top of `src/events.py`, below `import pygame`:

```python
import chunk as chunk_module
from chunk import generate_noise_ranges
```

> Note: `src/chunk.py` shadows the Python standard library's `chunk` module. That is intentional and pre-existing — `src/` is first on `sys.path` when the game is launched from the project root.

Then add the weights constant below `EVENTS`:

```python
# Ore-heavy world generation for the ORE RUSH event. Blocks absent from
# this table simply do not generate while the event runs; obsidian is
# excluded deliberately because its 100 HP would blunt the payoff.
ORE_RUSH_WEIGHTS = {
    "stone": 5, "andesite": 3, "cobblestone": 3,
    "coal_ore": 15, "iron_ore": 15, "copper_ore": 12,
    "gold_ore": 12, "redstone_ore": 12, "lapis_ore": 10,
    "diamond_ore": 8, "emerald_ore": 5,
}
```

- [ ] **Step 4: Implement `_apply` and `_restore`**

Replace the two placeholder methods at the bottom of `src/events.py`:

```python
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

    def _restore(self, hud):
        # Everything is cleared unconditionally, not just the flag the
        # active event set. A leaked flag strands a live stream.
        if self._saved_noise_ranges is not None:
            chunk_module.noise_ranges = self._saved_noise_ranges
            self._saved_noise_ranges = None
        self.tnt_storm = False
        self.speed_override = None
        hud.ore_multiplier = 1
```

- [ ] **Step 5: Run the test to verify it passes**

```bash
.venv/Scripts/python test_events.py
```

Expected: all twelve tests `PASS`, `0 failure(s)`.

- [ ] **Step 6: Commit**

```bash
git add src/events.py test_events.py
git commit -m "feat: wire the four event effects with unconditional restore"
```

---

### Task 4: Command panel with icons

**Files:**
- Modify: `src/hud.py` — module constants, `Hud.__init__`, three new methods

**Interfaces:**
- Consumes: `Hud` from Task 1
- Produces: `hud.COMMAND_ROWS`, `hud.PANEL_X/PANEL_Y/PANEL_W/ROW_H/HEADER_H/ICON_SIZE`, `Hud.draw_command_panel(screen) -> None`

- [ ] **Step 1: Add the layout constants and row table to `src/hud.py`**

Add below the existing imports, above `render_text_with_outline`:

```python
# --- Command panel layout, in internal-surface pixels (1080 x 1920) ---
PANEL_X = 756
PANEL_W = 300
PANEL_Y = 180
ROW_H = 52
HEADER_H = 44
ICON_SIZE = 40

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
```

- [ ] **Step 2: Build the icon cache in `Hud.__init__`**

Add at the end of `Hud.__init__`, after `self.font = pygame.font.Font(None, 64)`:

```python
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
```

- [ ] **Step 3: Add the panel drawing methods**

Add these three methods to the `Hud` class, after `add_ore()`:

```python
    def _panel_box(self, screen, x, y, w, h, title, accent=(255, 255, 255)):
        box = pygame.Surface((w, h), pygame.SRCALPHA)
        box.fill((12, 12, 16, 200))
        screen.blit(box, (x, y))
        pygame.draw.rect(screen, accent, (x, y, w, h), 3)
        t = render_text_with_outline(title, self.panel_font, accent, (0, 0, 0), 2)
        screen.blit(t, (x + (w - t.get_width()) // 2, y + 4))

    def _panel_row(self, screen, x, y, label, subtitle):
        icon = self.icons[label]
        # BIG renders at 1.4x and overflows its box on purpose.
        ix = x + 12 + (ICON_SIZE - icon.get_width()) // 2
        iy = y + (ROW_H - icon.get_height()) // 2
        screen.blit(icon, (ix, iy))

        tx = x + 12 + ICON_SIZE + 8
        lab = render_text_with_outline(label, self.panel_font, (255, 255, 255), (0, 0, 0), 2)
        screen.blit(lab, (tx, y + 2))
        sub = render_text_with_outline(subtitle, self.small_font, (170, 170, 180), (0, 0, 0), 1)
        screen.blit(sub, (tx, y + lab.get_height() - 2))

    def draw_command_panel(self, screen):
        height = HEADER_H + len(COMMAND_ROWS) * ROW_H
        self._panel_box(screen, PANEL_X, PANEL_Y, PANEL_W, height, "COMMANDS")
        y = PANEL_Y + HEADER_H
        for label, subtitle, _cat, _name, _scale, _new in COMMAND_ROWS:
            self._panel_row(screen, PANEL_X, y, label, subtitle)
            y += ROW_H

        new_rows = [r for r in COMMAND_ROWS if r[5]]
        if not new_rows:
            return
        ny = PANEL_Y + height + 36
        nh = HEADER_H + len(new_rows) * ROW_H
        self._panel_box(screen, PANEL_X, ny, PANEL_W, nh, "NEW COMMAND", accent=(255, 215, 0))
        y = ny + HEADER_H
        for label, subtitle, _cat, _name, _scale, _new in new_rows:
            self._panel_row(screen, PANEL_X, y, label, subtitle)
            y += ROW_H
```

- [ ] **Step 4: Call it from `Hud.draw()`**

At the very end of `Hud.draw()`, after the fast/slow indicator blit, add:

```python
        self.draw_command_panel(screen)
```

- [ ] **Step 5: Verify the existing tests still pass**

```bash
.venv/Scripts/python test_events.py
```

Expected: all twelve tests still `PASS`. (Task 1's test uses `Hud.__new__`, so it is unaffected by the new `__init__` work.)

- [ ] **Step 6: Verify visually**

```bash
.venv/Scripts/python ./src/main.py
```

Expected: a bordered `COMMANDS` panel on the right with ten icon rows, a gold-bordered `NEW COMMAND` box below it containing `NUKE`, no `!` anywhere, and the pickaxe still falling normally. Close the window to exit.

- [ ] **Step 7: Commit**

```bash
git add src/hud.py
git commit -m "feat: add on-screen command panel with atlas-sourced icons"
```

---

### Task 5: Subscriber counter

**Files:**
- Modify: `src/hud.py` — `Hud.__init__`, one new method

**Interfaces:**
- Consumes: `Hud` from Task 4
- Produces: `Hud.sub_count: int` (defaults `0`), `Hud.draw_sub_count(screen) -> None`

- [ ] **Step 1: Add the attribute**

In `Hud.__init__`, next to `self.ore_multiplier = 1`, add:

```python
        # Set from main.py. Zero means "not configured" and renders nothing.
        self.sub_count = 0
```

- [ ] **Step 2: Add the drawing method**

Add to the `Hud` class after `draw_command_panel()`:

```python
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
```

- [ ] **Step 3: Call it from `Hud.draw()`**

Immediately after the `self.draw_command_panel(screen)` line added in Task 4:

```python
        self.draw_sub_count(screen)
```

- [ ] **Step 4: Verify visually**

```bash
.venv/Scripts/python ./src/main.py
```

Expected: **no** subscriber counter appears, because `sub_count` is still `0` and nothing sets it yet. This confirms the zero-means-hidden rule before Task 7 wires the data source.

- [ ] **Step 5: Commit**

```bash
git add src/hud.py
git commit -m "feat: add subscriber counter, hidden while unconfigured"
```

---

### Task 6: Event ticker

**Files:**
- Modify: `src/hud.py` — `import math`, layout constants, one new method

**Interfaces:**
- Consumes: `EventManager` from Task 3 (reads `.phase`, `.name`, `.color`, `.remaining_ms()`, `.progress()`)
- Produces: `Hud.draw_event_ticker(screen, events) -> None`

- [ ] **Step 1: Add `import math` and the ticker constants**

Add `import math` to the top of `src/hud.py`. Add below the command panel constants:

```python
# --- Event ticker layout ---
TICKER_X, TICKER_Y = 32, 880
TICKER_W, TICKER_H = 420, 90
```

- [ ] **Step 2: Add the drawing method**

Add to the `Hud` class after `draw_sub_count()`:

```python
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
```

- [ ] **Step 3: Verify the existing tests still pass**

```bash
.venv/Scripts/python test_events.py
```

Expected: twelve tests `PASS`. The ticker has no test — it is branch-light blitting, and Task 7's visual check covers it.

- [ ] **Step 4: Commit**

```bash
git add src/hud.py
git commit -m "feat: add event ticker with warning pulse and drain bar"
```

---

### Task 7: Wire everything into the game loop

**Files:**
- Modify: `config.json` — four new keys
- Modify: `src/main.py` — import, `SUBS`/`SUB` parsing, manager construction, physics step, storm spawn, draw calls

**Interfaces:**
- Consumes: `EventManager` (Task 3), `Hud.sub_count` (Task 5), `Hud.draw_event_ticker` (Task 6)
- Produces: a running game with events and a live counter

- [ ] **Step 1: Add the config keys**

In `config.json`, add these four entries inside the top-level object (a comma is needed on the line above):

```json
    "EVENTS_ENABLED": true,
    "EVENT_INTERVAL_SECONDS_MIN": 60,
    "EVENT_INTERVAL_SECONDS_MAX": 90,
    "SUB_COUNT_BASE": 0
```

- [ ] **Step 2: Verify the config still parses**

```bash
.venv/Scripts/python -c "import json;print(json.load(open('config.json'))['EVENT_INTERVAL_SECONDS_MAX'])"
```

Expected: `90`. If this errors, a comma is missing or duplicated.

- [ ] **Step 3: Add the import and the shared stats dict**

In `src/main.py`, add to the imports:

```python
from events import EventManager
```

Below the global queues block (after `mega_tnt_queue = []`), add:

```python
# Live stream stats shown on the HUD. Seeded from config, incremented by
# SUB lines, and overridden absolutely by SUBS lines.
stream_stats = {"subs": config.get("SUB_COUNT_BASE", 0)}
```

- [ ] **Step 4: Parse `SUBS` and increment on `SUB`**

In `check_command_file()`, replace the existing `SUB` branch:

```python
            elif command == "SUB":
                mega_tnt_queue.append(user)
```

with:

```python
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
```

- [ ] **Step 5: Construct the manager**

In `game()`, directly after `hud = Hud(texture_atlas, atlas_items)`, add:

```python
    events = EventManager(
        interval_min_s=config.get("EVENT_INTERVAL_SECONDS_MIN", 60),
        interval_max_s=config.get("EVENT_INTERVAL_SECONDS_MAX", 90),
        enabled=config.get("EVENTS_ENABLED", True),
    )
    last_storm_spawn = pygame.time.get_ticks()
```

- [ ] **Step 6: Let events drive the physics step**

Replace the physics step block:

```python
        step = 1/FRAMERATE
        if fast_slow_active:
            if fast_slow == "Fast": step = 1/(FRAMERATE/2)
            else: step = 1/(FRAMERATE*2)
        space.step(step)
```

with:

```python
        # An active event outranks a chat-triggered speed change.
        speed_mode = events.speed_override or (fast_slow if fast_slow_active else None)
        step = 1/FRAMERATE
        if speed_mode == "Fast": step = 1/(FRAMERATE/2)
        elif speed_mode == "Slow": step = 1/(FRAMERATE*2)
        space.step(step)
```

- [ ] **Step 7: Tick the manager and spawn storm TNT**

Immediately after `curr = pygame.time.get_ticks()`, add:

```python
        events.update(hud)

        if events.tnt_storm and curr - last_storm_spawn >= 300:
            tnt_list.append(Tnt(space, pickaxe.body.position.x,
                                pickaxe.body.position.y - 100,
                                texture_atlas, atlas_items, sound_manager,
                                owner_name="TNT STORM"))
            last_storm_spawn = curr
```

- [ ] **Step 8: Feed the HUD and draw the ticker**

Replace the HUD draw line:

```python
        hud.draw(internal_surface, pickaxe.body.position.y, fast_slow_active, fast_slow)
```

with:

```python
        hud.sub_count = stream_stats["subs"]
        hud.draw(internal_surface, pickaxe.body.position.y,
                 speed_mode is not None, speed_mode or "Normal")
        hud.draw_event_ticker(internal_surface, events)
```

- [ ] **Step 9: Run the tests**

```bash
.venv/Scripts/python test_events.py
```

Expected: twelve tests `PASS`, `0 failure(s)`.

- [ ] **Step 10: Verify the full loop visually**

Temporarily set `"EVENT_INTERVAL_SECONDS_MIN": 5` and `"EVENT_INTERVAL_SECONDS_MAX": 8` in `config.json`, plus `"SUB_COUNT_BASE": 165900`, then:

```bash
.venv/Scripts/python ./src/main.py
```

Expected, within ~30 seconds: the counter reads `165,900 subs`; the ticker shows a pulsing `... INCOMING`, then switches to the event name with a draining bar; `SLOW MOTION` visibly slows the pickaxe and the left indicator reads `Slow`; `TNT STORM` spawns a steady stream of TNT; `ORE RUSH` fills fresh chunks with ore; `GOLD FEVER` makes ore counters climb in threes. After each event the ticker disappears and behaviour returns to normal.

**Then restore `config.json` to `60` / `90` / `0`** before committing.

- [ ] **Step 11: Confirm the config was restored**

```bash
.venv/Scripts/python -c "import json;c=json.load(open('config.json'));print(c['EVENT_INTERVAL_SECONDS_MIN'],c['EVENT_INTERVAL_SECONDS_MAX'],c['SUB_COUNT_BASE'])"
```

Expected: `60 90 0`. Do not commit test values.

- [ ] **Step 12: Commit**

```bash
git add src/main.py config.json
git commit -m "feat: wire event manager, SUBS command, and ticker into game loop"
```

---

### Task 8: Streamer.bot setup documentation

**Files:**
- Modify: `README.md`

**Interfaces:**
- Consumes: the `SUBS` command from Task 7, the panel labels from Task 4
- Produces: documentation only

- [ ] **Step 1: Append the setup section to `README.md`**

Add at the end of `README.md`:

```markdown
---

## ⚡ Stream Visibility Layer

The game now shows a **command panel**, a **live subscriber counter**, and an
**event ticker**. Commands are displayed without the `!` prefix — viewers infer
it from chat, and dropping it keeps the panel readable at Shorts resolution.

### Command reference

The left column is what a viewer types. The middle column is the text your
Streamer.bot Action writes to `commands.txt`. The right column is the label
that appears on screen.

| Viewer types | Text to write in file | Shows on screen as |
|---|---|---|
| `!tnt` | `TNT:%user%` | TNT |
| `!nuke` | `NUKE:%user%` | NUKE |
| `!big` | `BIG:%user%` | BIG |
| `!fast` | `SPEED:%user%:FAST` | FAST |
| `!slow` | `SPEED:%user%:SLOW` | SLOW |
| `!diamond` | `PICKAXE:%user%:DIAMOND` | DIAMOND |
| `!gold` | `PICKAXE:%user%:GOLD` | GOLD |
| `!iron` | `PICKAXE:%user%:IRON` | IRON |
| `!stone` | `PICKAXE:%user%:STONE` | STONE |
| `!netherite` | `PICKAXE:%user%:NETHERITE` | NETHERITE |
| *(New Subscriber event)* | `SUB:%user%` | — |
| *(Super Chat / Cheer event)* | `SUPER:%user%:%message%` | — |

> **Create the missing Actions.** `!iron`, `!stone`, and `!netherite` have always
> been accepted by the game but were not in the old cheat sheet. They now appear
> in the on-screen panel, so viewers will try them. Add an Action for each.

### Subscriber counter — Option A (recommended, zero setup)

No new Streamer.bot Action is needed.

1. Check your current subscriber count on YouTube before going live.
2. Open `config.json` and set `"SUB_COUNT_BASE"` to that number, e.g.
   `"SUB_COUNT_BASE": 165900`.
3. Start the game.

The counter increments automatically on every new subscriber, because your
existing **New Subscriber** Action already writes `SUB:%user%`. It stays
accurate for the whole stream and resets to the baseline next launch.

While `SUB_COUNT_BASE` is `0` and no count has arrived, the counter is hidden
entirely — you get a clean screen rather than a visible `0`.

### Subscriber counter — Option B (optional exact sync)

Use this only if you want the count to stay exact across a very long stream.

1. **Actions** tab → right-click → **Add Action** → name it `Game - Sub Count`.
2. Add whichever YouTube sub-action your Streamer.bot version provides for
   fetching channel statistics, so the subscriber count lands in a variable.
3. Add a second sub-action: right-click → **Core** → **File IO** →
   **Write to File**.
   - **File:** the same `commands.txt` path used by every other Action.
   - **Text:** `SUBS:system:%yourSubCountVariable%`
   - Check both **Append** and **Write on New Line**.
4. **Timed Actions** tab → new timer pointing at `Game - Sub Count`, every
   5 minutes.

> **Verify the variable name first.** It differs between Streamer.bot versions
> and YouTube integration setups. Run the Action once and check that a real
> number reaches `commands.txt` rather than an unexpanded `%variable%` string.
> If it does not resolve, use Option A — it needs no variable at all. A
> malformed count is ignored by the game and the baseline stands.

### Events

Every 60–90 seconds one of four events fires, announced by a 3-second warning
on the ticker:

| Event | Duration | Effect |
|---|---|---|
| **ORE RUSH** | 15s | Newly generated chunks are packed with ore |
| **TNT STORM** | 12s | TNT spawns continuously |
| **SLOW MOTION** | 10s | Physics slow to a crawl |
| **GOLD FEVER** | 20s | Every ore drop counts triple |

Tune or disable events in `config.json`:

```json
"EVENTS_ENABLED": true,
"EVENT_INTERVAL_SECONDS_MIN": 60,
"EVENT_INTERVAL_SECONDS_MAX": 90
```

Setting `"EVENTS_ENABLED": false` disables the system and hides the ticker.

### Marking a command as NEW

Set the last field of a row in `COMMAND_ROWS` (`src/hud.py`) to `True` and it
also renders in the highlighted **NEW COMMAND** box. Clear the flag once it is
no longer new — the box loses its pull if everything lives in it.

### Running the self-checks

```bash
.venv/Scripts/python test_events.py
```
```

- [ ] **Step 2: Verify the tests still pass**

```bash
.venv/Scripts/python test_events.py
```

Expected: twelve tests `PASS`, `0 failure(s)`.

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "docs: add Streamer.bot setup for the visibility layer"
```

---

## Verification Checklist

Run after all tasks are complete:

- [ ] `.venv/Scripts/python test_events.py` → twelve tests pass, `0 failure(s)`
- [ ] `git status --short` → clean tree
- [ ] `config.json` holds production values `60` / `90` / `0`, not the Task 7 test values
- [ ] `.venv/Scripts/python ./src/main.py` launches, panel renders with icons, no `!` on screen
- [ ] `grep -rn '"!' src/hud.py` → no matches (no `!` leaked into a panel label)
- [ ] `git log --oneline` → eight feature commits on top of the initial commit
