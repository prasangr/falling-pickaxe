# ⛏️ Falling Pickaxe: Ultimate Edition

### Streamer.bot Integrated

This is a heavily modified version of the popular interactive streaming game designed to maximize audience engagement across multiple platforms with zero API headaches.

---

### 🌟 Credits & Original Project

This project is built upon the excellent foundation of the original **[Falling Pickaxe](https://github.com/vycdev/falling-pickaxe)** repository by **[vycdev](https://github.com/vycdev)**.

While the original project focuses on direct YouTube API integration, this "Ultimate Edition" re-engineers the core communication system to work seamlessly with **Streamer.bot** via a robust local file-watcher system.

---

### 🚀 Why This Edition?

By replacing direct API polling with local command-file listening, this version eliminates firewall issues, removes reliance on Google/YouTube API quotas, and unlocks instant compatibility with any platform Streamer.bot supports.

#### Key Features

* ✅ **Streamer.bot Native:** Receives commands instantly via a local `commands.txt` file written by bot actions.
* ✅ **Multi-Platform:** Works simultaneously with chat from Twitch, YouTube, Kick, and Trovo.
* ✅ **Zero API Keys:** No complex Google Cloud setup or quota limits required.
* 💥 **"Nuke" Combo:** New `!nuke` command triggers a Giant Pickaxe + massive TNT shower instantly.
* ⏳ **Auto-Reverting Skins:** Premium skins (Diamond, Gold) automatically revert to wood after a configurable time.
* 🔊 **Full Audio:** Restored and optimized sound effects for all game events.

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
| `!spin` | `SPIN:%user%` | SPIN |
| `!multiply` | `MULTIPLY:%user%` | MULTIPLY |
| `!quake` | `QUAKE:%user%` | QUAKE |
| `!storm` | `STORM:%user%` | STORM |
| `!water` | `WATER:%user%` | WATER |
| `!fast` | `SPEED:%user%:FAST` | FAST |
| `!slow` | `SPEED:%user%:SLOW` | SLOW |
| `!diamond` | `PICKAXE:%user%:DIAMOND` | DIAMOND |
| `!gold` | `PICKAXE:%user%:GOLD` | GOLD |
| `!iron` | `PICKAXE:%user%:IRON` | IRON |
| `!stone` | `PICKAXE:%user%:STONE` | STONE |
| `!netherite` | `PICKAXE:%user%:NETHERITE` | NETHERITE |
| `!heli` | `HELI:%user%` | HELI |
| `left` | `LEFT:%user%` | *(vote panel)* |
| `mid` | `MID:%user%` | *(vote panel)* |
| `right` | `RIGHT:%user%` | *(vote panel)* |
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

### Nuke Meter

Every chat command charges one shared bar on screen. When it is full, a
5-second countdown starts, then a nuke clears the screen and credits the viewer
who filled it.

| Source | Charge |
|---|---|
| Any chat command | 1 |
| `!nuke` | 5 |
| New subscriber | 20 |
| Super Chat | 30 |
| Nothing at all | 10 per minute, so a quiet stream still gets a nuke every 10 minutes |

No new Streamer.bot Actions are needed. Tune or disable it in `config.json`:
`NUKE_METER_ENABLED`, `NUKE_METER_CAPACITY`, `NUKE_PASSIVE_CHARGE_PER_MINUTE`,
`NUKE_COUNTDOWN_SECONDS`, `NUKE_RADIUS_BLOCKS` and `NUKE_DAMAGE`. Raise the
capacity as the chat gets busier, or nukes stop feeling special.

### Depth record

The deepest point ever reached is saved to `records.json` and shown as
`RECORD`, so each stream has a number to beat. A `NEW DEPTH RECORD!` banner
appears once per stream when it falls. Delete the file to start again.

### Clip log

Nukes and new records are written to `logs/clips_YYYY-MM-DD.csv` with the local
time and the time since the game started. To turn them into Shorts, work out
each moment's position in the stream recording from those times.

### Helicopter

A helicopter flies in, hovers while chat votes, then bombs the left, middle and
right of the screen, hitting the winning lane with a Mega TNT. Each viewer has
one vote and can change it. With no votes, all three lanes are bombed equally.

It flies when a viewer types `!heli`, or on its own if nobody has called one for
`HELI_AUTO_INTERVAL_SECONDS`. **Add Streamer.bot Actions for `!heli`, `left`,
`mid` and `right`** using the command reference above; until then only the
automatic flights run, with no voting.

Tune it with `HELI_ENABLED`, `HELI_COOLDOWN_SECONDS`,
`HELI_AUTO_INTERVAL_SECONDS` and `HELI_VOTE_SECONDS`. Stream delay eats into the
vote, so raise `HELI_VOTE_SECONDS` if votes arrive after the bombs.

### Talking pickaxe

The pickaxe has a face that reacts to what is happening, and speech bubbles that
name the viewer responsible. It also talks to itself when chat is quiet. Its
lines are all in `LINES` in `src/voice.py`, ready to edit. `{USER}` becomes the
viewer's name. Turn it off with `VOICE_ENABLED`, and change how often it talks to
itself with `VOICE_IDLE_SECONDS_MIN` and `VOICE_IDLE_SECONDS_MAX`.

### Marking a command as NEW

Set the last field of a row in `COMMAND_ROWS` (`src/hud.py`) to `True` and it
gets a red **NEW** tag in the menu. Clear the flag once it is no longer new — the
tag loses its pull if everything has one. A new command also needs a row in
`COMMAND_ROWS` and a place in `MENU_GROUPS`.

### Running the self-checks

```bash
.venv/Scripts/python test_events.py
```
