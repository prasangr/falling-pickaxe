# Stream Visibility Layer — Design Spec

**Date:** 2026-08-23
**Status:** Approved, ready for implementation planning
**Scope:** On-screen command panel, live subscriber counter, event ticker bar, and a four-event random event system.

---

## 1. Problem

The game already accepts seven chat commands (`TNT`, `SUB`, `SUPER`, `SPEED`, `BIG`, `NUKE`, `PICKAXE`), but **nothing on screen tells a viewer they exist**. A new viewer arriving on a Shorts stream sees a pickaxe falling and has no idea they can influence it. Discovery currently depends entirely on the stream title or pinned comment.

Separately, the stream has no pacing. Every 30-second window looks like every other 30-second window: pickaxe falls, TNT spawns, blocks break. There is no rhythm, no anticipation, and no reason for a viewer to keep watching past the first loop.

This spec addresses both with the smallest change that works: make existing features **visible**, and add a **timed event cycle** that gives the stream a heartbeat.

## 2. Goals

1. A viewer landing on the stream mid-scroll can learn a command in under three seconds without reading the title.
2. Newly added commands get a visual callout so returning viewers notice them.
3. Live subscriber count is on screen (a proven retention driver for this format).
4. Something notable happens every 60–90 seconds, announced with a warning so anticipation builds.
5. No new art assets. No new Python dependencies. No YouTube API key.

## 3. Non-goals

Explicitly deferred to later work:

- New mob entities (creeper, zombie, warden, Herobrine)
- Weather and sky hazards (rain, thunder, meteor)
- Team-battle / VS mode
- Persistent viewer leaderboards
- Wiring `src/youtube.py` into the game loop

Team-battle mode, when built, will use original team names rather than the real-footballer framing seen on competing streams — that involves real people's names and likenesses, and there is no upside to borrowing it.

## 4. Architecture

One new module plus draw methods on the existing HUD. No widget framework, no panel base class, no JSON-driven layout — there are four static panels and they change roughly never.

```
main.py
  ├── reads flags from ──> events.EventManager   (new file)
  └── passes state to ──> hud.Hud                (extended)
                            └── reads ore drops from block.ORE_DROPS
```

`EventManager` exposes **plain attributes** that the game loop reads each frame. No callbacks are threaded through the loop, and no event mutates the pickaxe or TNT list directly. This keeps event logic testable in isolation with a fake clock.

### Files touched

| File | Change | Est. lines |
|---|---|---|
| `src/events.py` | **New** — event state machine + definitions | +110 |
| `src/hud.py` | Command panel + icons, sub counter, event ticker, `add_ore()` | +105 |
| `src/main.py` | Wire `EventManager`, `SUBS` command, read flags | +18 |
| `src/block.py` | Replace 8-branch chain with `ORE_DROPS` dict | −12 |
| `test_events.py` | **New** — event cycle self-check | +55 |
| `README.md` | Streamer.bot setup for new commands | docs |
| `config.json` | Four new keys | +4 |

---

## 5. HUD Design

Internal render surface is **1080 × 1920** (9:16). The left column is existing HUD and does not move.

```
 ┌────────────────────────────────────────────────┐
 │  🪨 289                        ╔═════════════╗ │
 │  🟠 285                        ║  COMMANDS   ║ │
 │  🟡 174                        ║ [tnt]  TNT  ║ │
 │  🔴 1105                       ║ [meg]  NUKE ║ │
 │  🔵 1190                       ║ [PIK]  BIG  ║ │
 │  💎 78                         ║  ▶▶   FAST  ║ │
 │  🟢 42                         ║  ◀◀   SLOW  ║ │
 │                                ║ [pik]  DIAM ║ │
 │  Y: -1165                      ║ [pik]  GOLD ║ │
 │  Normal                        ║ [pik]  IRON ║ │
 │                                ║ [pik]  STONE║ │
 │  ╔══════════════════╗          ║ [pik]  NETH ║ │
 │  ║ ⚡ ORE RUSH      ║          ╚═════════════╝ │
 │  ║ ███████░░░  8s   ║          ╔═════════════╗ │
 │  ╚══════════════════╝          ║ NEW COMMAND ║ │
 │                                ║ [meg]  NUKE ║ │
 │  ▶ 165,909 subs                ╚═════════════╝ │
 │                                                │
 │              [ pickaxe falls here ]            │
 └────────────────────────────────────────────────┘
```

### 5.1 Command panel

**Commands render WITHOUT the `!` prefix.** The panel shows `TNT`, not `!tnt`. Rationale: the `!` is Streamer.bot trigger syntax, it adds visual noise at small Shorts resolution, and viewers reliably infer the prefix from chat. This matches how the format is presented on established streams.

Each row is an **icon**, a command name, and a small subtitle describing its effect:

| Icon source | Row label | Subtitle | Maps to file command |
|---|---|---|---|
| `block/tnt` | `TNT` | SPAWN 1 TNT | `TNT:%user%` |
| `block/mega_tnt` | `NUKE` | GIANT PICK + 30 TNT | `NUKE:%user%` |
| `pickaxe/wooden_pickaxe` @ 1.4× | `BIG` | GIANT PICKAXE | `BIG:%user%` |
| drawn chevrons `▶▶` | `FAST` | SPEED UP 5S | `SPEED:%user%:FAST` |
| drawn chevrons `◀◀` | `SLOW` | SLOW DOWN 5S | `SPEED:%user%:SLOW` |
| `pickaxe/diamond_pickaxe` | `DIAMOND` | DIAMOND SKIN 30S | `PICKAXE:%user%:DIAMOND` |
| `pickaxe/golden_pickaxe` | `GOLD` | GOLD SKIN 30S | `PICKAXE:%user%:GOLD` |
| `pickaxe/iron_pickaxe` | `IRON` | IRON SKIN 30S | `PICKAXE:%user%:IRON` |
| `pickaxe/stone_pickaxe` | `STONE` | STONE SKIN 30S | `PICKAXE:%user%:STONE` |
| `pickaxe/netherite_pickaxe` | `NETHERITE` | BEST SKIN 30S | `PICKAXE:%user%:NETHERITE` |

#### Icon sourcing — no new art assets

`atlas.py:5` builds the texture atlas by scanning `src/assets/{block,item,destroy_stage,particle,pickaxe}` and keying every PNG by its filename. **Eight of the ten icons therefore already exist** and are addressable as `atlas_items["block"]["tnt"]`, `atlas_items["pickaxe"]["diamond_pickaxe"]`, and so on — exactly the same lookup the existing HUD already uses for ore icons at `hud.py:67-71`.

The two exceptions are handled without adding files:

- **FAST / SLOW** — a double chevron pointing right or left, drawn with two `pygame.draw.polygon()` calls into a small `SRCALPHA` surface. Roughly three lines each, tinted to the row colour. Adding two PNGs for two triangles would be more work, not less.
- **BIG** — reuses `wooden_pickaxe` rendered at **1.4× the standard icon size**, deliberately overflowing its icon box. The oversized icon communicates the effect directly, so no distinct artwork is needed.

**Icon geometry:** 40 × 40px inside the 52px row, left-aligned with an 8px gutter, so the label baseline starts at `panel_x + 48`. `BIG` renders at 56 × 56px, centred on the same 40px box, and overflows symmetrically into the row padding.

Icons are subsurfaced from the atlas **once at `Hud.__init__`** and cached in a dict, not re-cut per frame. The atlas has already been scaled by `BLOCK_SCALE_FACTOR` (≈7.5×) by the time the HUD receives it, so each icon is downscaled once to 40px at init and reused. Re-scaling ten icons every frame at 60fps would be pure waste.

The list lives as a module constant in `hud.py`, directly beside the drawing code. It is deliberately **not** in `config.json`: adding a command already requires editing the parser in `main.py`, so a config indirection would only mean editing two files instead of one.

Entries carry an optional `new=True` flag. Flagged entries are rendered **again** in a separate highlighted "NEW COMMAND" box below the main panel. This is the mechanism that gets returning viewers to try additions instead of defaulting to `!tnt` forever.

**Geometry:** panel width 300px, right-aligned at `x = 756`, top at `y = 180`. Row height 52px, header 44px. Ten rows → `44 + (10 × 52) = 564px`, so the panel bottom sits at `y = 744`. The NEW box starts at `y = 780`.

### 5.2 Subscriber counter

Bottom-left at `(32, 1000)`, rendered as `▶ 165,909` with thousands separators.

**Data source — no API key required.** Two mechanisms, in priority order:

1. **Baseline + increment (default, zero setup).** `config.json` gains `SUB_COUNT_BASE`. The streamer sets it to their current count before going live. Every `SUB:%user%` line that arrives — which Streamer.bot already sends for the Mega TNT — increments the on-screen number by one. Accurate for the duration of a stream, and requires no new Streamer.bot action at all.
2. **Exact sync (optional override).** A `SUBS:system:<count>` line sets the number absolutely. A Streamer.bot timed action can push the real figure periodically if the streamer wants drift-free accuracy.

**Zero means hidden.** If `SUB_COUNT_BASE` is `0` or absent *and* no `SUBS` line has arrived, the counter **does not render at all** — it does not display `▶ 0`. A streamer who has not configured the baseline gets a clean screen rather than an embarrassing zero, and nothing breaks when Streamer.bot is not running. Once either source supplies a non-zero count, the counter appears and stays.

### 5.3 Event ticker

Left column at `(32, 880)`, 420 × 90px. Three visual states:

- **Idle** — not rendered.
- **Warning** (3s before event) — event name pulsing, text reads `INCOMING`. The pulse reuses the same sine-brightness trick as the TNT blink in `tnt.py:106-109`.
- **Active** — event name, colour bar draining left-to-right, remaining seconds as `8s`.

Bar colour is per-event (see §6). All text uses the existing `render_text_with_outline()` helper in `hud.py:4`.

---

## 6. Event System (`src/events.py`)

### 6.1 State machine

```
        60–90s random
IDLE ──────────────────> WARNING ──3s──> ACTIVE ──10–20s──> IDLE
                                                              │
                                          (all flags restored)┘
```

Exactly one event is active at a time. The next interval is rolled when an event ends, so events never stack.

### 6.2 Event definitions

| Event | Duration | Bar colour | Mechanism |
|---|---|---|---|
| **ORE RUSH** | 15s | Gold | Swaps `chunk.noise_ranges` for an ore-heavy weighting; restores the original on end |
| **TNT STORM** | 12s | Red | Sets `tnt_storm = True`; the game loop spawns one TNT every 300ms while set |
| **SLOW MOTION** | 10s | Cyan | Sets `speed_override = "Slow"`; the existing fast/slow physics-step branch handles it |
| **GOLD FEVER** | 20s | Yellow | Sets `hud.ore_multiplier = 3` |

ORE RUSH weighting drops stone-family blocks near zero and raises every ore:

```python
ORE_RUSH_WEIGHTS = {
    "stone": 5, "andesite": 3, "cobblestone": 3,
    "coal_ore": 15, "iron_ore": 15, "copper_ore": 12,
    "gold_ore": 12, "redstone_ore": 12, "lapis_ore": 10,
    "diamond_ore": 8, "emerald_ore": 5,
}
```

Blocks omitted from this dict (`diorite`, `granite`, `mossy_cobblestone`, `obsidian`) simply do not generate for the duration of the event. That is intentional — obsidian in particular has 100 HP and would blunt the payoff.

**Known limitation:** ORE RUSH only affects chunks generated *during* the event, not blocks already on screen. Because the pickaxe is continuously falling into fresh chunks, the effect appears on screen within roughly a second. This is accepted, not a defect to fix — regenerating live chunks would mean tearing down and rebuilding pymunk bodies mid-frame.

**Reuse note:** SLOW MOTION deliberately drives the *existing* `fast_slow_active` / `fast_slow` machinery in `main.py:205-208` rather than introducing a parallel time-scaling path. One time-scale mechanism, one place to debug.

### 6.3 Interface

```python
class EventManager:
    def __init__(self, clock=pygame.time.get_ticks, rng=random.Random()):
        ...

    def update(self, hud) -> None:
        """Advance the state machine. Applies and restores flags at transitions."""

    def draw(self, surface) -> None:
        """Render the ticker. No-op while IDLE."""

    # Flags read by the game loop each frame:
    speed_override: str | None   # "Slow" | "Fast" | None
    tnt_storm: bool
    phase: str                   # "idle" | "warning" | "active"
```

The `clock` and `rng` parameters are injected **because the test needs them** (§8), not on speculation. `hud.ore_multiplier` and `chunk.noise_ranges` are mutated directly at transition points rather than being polled every frame.

### 6.4 Game loop integration

`main.py` gains, inside the existing loop:

- `events.update(hud)` once per frame
- A `tnt_storm` branch on the existing TNT spawn timer
- `events.speed_override` consulted alongside `fast_slow_active` when computing the physics step
- `events.draw(internal_surface)` after `hud.draw(...)`

---

## 7. Ore Drop Refactor (`src/block.py`)

`block.py:115-130` currently maps ore name → HUD counter through an eight-branch `if/elif` chain. GOLD FEVER's multiplier would have to be applied in all eight places.

Replaced with a module-level dict:

```python
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

and a single call site: `hud.add_ore(*ORE_DROPS[self.name])` when the name is present.

`Hud.add_ore()` applies the multiplier in one place:

```python
def add_ore(self, key, lo, hi):
    self.amounts[key] += random.randint(lo, hi) * self.ore_multiplier
```

Existing drop quantities are preserved exactly, including the `randint(4, 5)` for redstone and `randint(4, 8)` for lapis. Net line change is negative.

---

## 8. Testing

One runnable check: `test_events.py`, plain `assert`, no framework.

It drives `EventManager` with a fake clock through a complete cycle and asserts:

1. `phase` is `idle` before the first interval elapses.
2. `phase` becomes `warning` exactly 3s before activation.
3. `phase` becomes `active` at activation, and the matching flag is set.
4. **On end, every flag is restored** — `speed_override is None`, `tnt_storm is False`, `hud.ore_multiplier == 1`, and `chunk.noise_ranges` is the original object.
5. Two consecutive cycles never overlap.

Assertion 4 is the important one. A leaked event flag means a stream stuck in permanent slow motion or spawning TNT forever, and it would not be obvious from a screenshot — it is exactly the failure that costs a live broadcast.

The HUD drawing code gets no test. It is pure blitting with no branching logic worth pinning down, and a visual check on the running game covers it.

---

## 9. Configuration

Three keys added to `config.json`:

```json
"EVENTS_ENABLED": true,
"EVENT_INTERVAL_SECONDS_MIN": 60,
"EVENT_INTERVAL_SECONDS_MAX": 90,
"SUB_COUNT_BASE": 0
```

`EVENTS_ENABLED: false` disables the whole system including the ticker, so the streamer can turn it off mid-stream without a code change.

---

## 10. Streamer.bot Setup

Everything in the existing README setup continues to work unchanged. The visibility layer adds **no required Streamer.bot configuration** — the command panel is purely cosmetic and the subscriber counter works off the `SUB` action that already exists.

The sections below cover the optional additions.

### 10.1 Existing commands — no change needed

For reference, this is the current mapping. The **left column is what a viewer types**; the **middle column is the text written to `commands.txt`**; the right column is the label that now appears in the on-screen panel.

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

If you have not yet created Actions for `!iron`, `!stone`, and `!netherite`, add them now — they appear in the on-screen panel, so viewers will try them.

### 10.2 Subscriber counter — Option A (recommended, zero setup)

No new Action required.

1. Before going live, check your current subscriber count on YouTube.
2. Open `config.json` in the game folder.
3. Set `"SUB_COUNT_BASE"` to that number, e.g. `"SUB_COUNT_BASE": 165900`.
4. Start the game.

The counter increments automatically on every new subscriber, because your existing **New Subscriber** Action already writes `SUB:%user%`. The number stays accurate for the whole stream and resets to the baseline next launch.

### 10.3 Subscriber counter — Option B (optional exact sync)

Use this only if you want the count to stay exact across a very long stream without touching `config.json`.

1. In Streamer.bot, go to the **Actions** tab.
2. Right-click → **Add Action** → name it `Game - Sub Count`.
3. In the **Sub-Actions** box, add whichever YouTube sub-action your Streamer.bot version provides for fetching channel or broadcast statistics, so that the subscriber count lands in a variable.
4. Add a second sub-action: right-click → **Core** → **File IO** → **Write to File**.
   - **File:** the same `commands.txt` path you used for every other Action.
   - **Text:** `SUBS:system:%yourSubCountVariable%`
   - Check both **Append** and **Write on New Line**.
5. Go to the **Timed Actions** tab, create a timer pointing at `Game - Sub Count`, and set it to run every 5 minutes.

> **Verify the variable name.** The exact name of the subscriber-count variable differs between Streamer.bot versions and YouTube integration setups. Before relying on this, run the Action once and check the Streamer.bot logs (or the resulting line in `commands.txt`) to confirm a real number arrives rather than an unexpanded `%variable%` string. If the value does not resolve, use Option A instead — it needs no variable at all.

The game accepts any well-formed `SUBS:system:<number>` line and ignores malformed ones, so a misconfigured Action degrades to "counter keeps using the baseline" rather than crashing.

### 10.4 Marking a command as NEW

When you add a command and want the highlighted callout, set `new=True` on its entry in the command list in `src/hud.py`. It then renders in the **NEW COMMAND** box as well as the main panel. Remove the flag once it is no longer new — the box loses its pull if everything lives in it.

---

## 11. Risks

| Risk | Mitigation |
|---|---|
| Ticker or panel overlaps the falling pickaxe on some resolutions | All geometry is against the fixed 1080×1920 internal surface, which is scaled as a unit. Layout cannot shift with window size. |
| Event flags leak and stick the stream in a bad state | Assertion 4 in `test_events.py` covers exactly this. |
| `SUBS` line carries a malformed number | Parsed inside the existing `try/except` in `check_command_file()`; a bad line is ignored and the baseline stands. |
| Ten panel rows crowd a 9:16 Shorts frame | Rows are 52px on a 1920px-tall surface; the panel occupies the right third, which is currently empty. |
| Events fire during a quiet moment and go unnoticed | The 3s warning phase exists for this. It can be tuned via the interval config keys without a code change. |

## 12. Open items for the implementation plan

- Exact font sizes for panel subtitles at Shorts resolution — needs a visual pass on the running game, not a decision made on paper.
- Whether `NUKE` alone belongs in the NEW box at launch, or `NUKE` plus the three newly-documented skin commands.
