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


def test_disabled_mid_active_restores_and_returns_to_idle():
    """When disabled while ACTIVE, update() must restore effects and return to IDLE."""
    import events

    hud = FakeHud()
    mgr, clock = _run_full_cycle("TNT STORM", hud)
    assert mgr.phase == events.ACTIVE
    assert mgr.tnt_storm is True

    # Now disable while active
    mgr.enabled = False
    mgr.update(hud)

    # Should have restored and returned to IDLE
    assert mgr.phase == events.IDLE, mgr.phase
    assert mgr.tnt_storm is False, mgr.tnt_storm
    assert mgr.speed_override is None
    assert hud.ore_multiplier == 1, hud.ore_multiplier


def test_restore_clears_all_flags_not_just_active_event():
    """_restore() must clear ALL flags, not just the one set by the active event."""
    import events

    hud = FakeHud()
    # Dirty the flags with values NOT set by SLOW MOTION
    hud.ore_multiplier = 7
    mgr, clock = _run_full_cycle("SLOW MOTION", hud)
    mgr.tnt_storm = True  # Set a flag the SLOW MOTION event didn't set
    assert mgr.speed_override == "Slow"
    assert mgr.tnt_storm is True
    assert hud.ore_multiplier == 7

    # Complete the cycle
    clock.advance(mgr.event["duration_ms"])
    mgr.update(hud)

    # All flags should be cleared
    assert mgr.tnt_storm is False, mgr.tnt_storm
    assert mgr.quake is False, mgr.quake
    assert mgr.storm is False, mgr.storm
    assert mgr.speed_override is None, mgr.speed_override
    assert hud.ore_multiplier == 1, hud.ore_multiplier


def test_spin_multiplier_survives_skin_change():
    """Spin boosts damage, and a mid-spin skin swap must not silently eat it."""
    import pickaxe as pickaxe_mod

    now = [0]
    real_get_ticks = pickaxe_mod.pygame.time.get_ticks
    pickaxe_mod.pygame.time.get_ticks = lambda: now[0]

    # Bypass __init__ so the test needs no pymunk space or pygame display.
    p = pickaxe_mod.Pickaxe.__new__(pickaxe_mod.Pickaxe)
    p.damage = 2
    p.damage_multiplier = 1
    p.spin_end_time = 0
    p.spin_rate = 0
    p.is_enlarged = False

    p.spin(duration=10000, multiplier=3, rate=12)
    assert p.damage_multiplier == 3, p.damage_multiplier
    assert p.spin_end_time == 10000, p.spin_end_time

    # Re-triggering extends rather than restarts.
    now[0] = 4000
    p.spin(duration=10000, multiplier=3, rate=12)
    assert p.spin_end_time == 20000, p.spin_end_time

    # A skin change reassigns damage from the material table; the multiplier
    # must ride through it, or spin silently stops boosting.
    atlas = type("A", (), {"subsurface": lambda self, r: None})()
    p.pickaxe("diamond_pickaxe", atlas, {"pickaxe": {"diamond_pickaxe": None}})
    assert p.damage == 10, p.damage
    assert p.damage_multiplier == 3, p.damage_multiplier

    pickaxe_mod.pygame.time.get_ticks = real_get_ticks
def test_block_tints_cover_every_ore():
    import atlas
    import block

    missing = set(block.ORE_DROPS) - set(atlas.BLOCK_TINTS)
    assert not missing, missing


def test_apply_block_tints_actually_changes_pixels():
    """subsurface() shares pixels with the parent -- if that ever stops being
    true the grading silently no-ops and every block goes back to grey."""
    import pygame
    import atlas

    pygame.init()
    surf = pygame.Surface((32, 32), pygame.SRCALPHA)
    surf.fill((128, 128, 128, 255))
    textures = {"block": {"redstone_ore": (0, 0, 16, 16)}}

    atlas.apply_block_tints(surf, textures)

    r, g, b, a = surf.get_at((4, 4))
    assert r > g and r > b, (r, g, b)   # Pushed toward red.
    assert a == 255, a                  # Alpha untouched.
    assert surf.get_at((24, 24))[:3] == (128, 128, 128)  # Outside the rect.


def test_countdown_appears_only_in_the_final_stretch():
    import events

    mgr, clock = _manager("GOLD FEVER", gap_ms=60000)
    hud = FakeHud()

    # Too far out: nothing to show.
    clock.advance(40000)
    assert mgr.countdown_secs() is None, mgr.countdown_secs()

    # Inside the window: counts down in whole seconds.
    clock.advance(10000)  # T-10s
    assert mgr.countdown_secs() == 10, mgr.countdown_secs()

    # Once the warning takes over, the countdown yields to the reveal.
    clock.advance(10000)
    mgr.update(hud)
    assert mgr.phase == events.WARNING, mgr.phase
    assert mgr.countdown_secs() is None, mgr.countdown_secs()


def test_multiply_clones_enter_and_leave_the_space():
    """MULTIPLY adds real bodies; despawn must remove every one of them, or
    the space leaks 15 pickaxes per use until the sim crawls."""
    import pygame
    import pymunk
    import pickaxe as pickaxe_mod

    pygame.init()
    space = pymunk.Space()
    texture = pygame.Surface((16, 16), pygame.SRCALPHA)
    original = pickaxe_mod.Pickaxe(space, 0, 0, texture, None, damage=6)
    before = len(space.bodies)

    clones = pickaxe_mod.spawn_clones(space, original, count=15)
    assert len(clones) == 15, len(clones)
    assert len(space.bodies) == before + 15, len(space.bodies)
    assert all(c.damage == 6 for c in clones)  # Clones inherit the real damage.

    pickaxe_mod.despawn_clones(space, clones, original)
    assert clones == [], clones
    assert len(space.bodies) == before, len(space.bodies)
    assert original.body in space.bodies  # The real pickaxe survives.


def test_daylight_tint_tracks_the_clock():
    from daylight import tint_for

    # Midday leaves the artwork essentially untouched.
    r, g, b = tint_for(14)
    assert (r, g, b) == (255, 255, 255), (r, g, b)

    # Small hours go blue-dominant.
    r, g, b = tint_for(2)
    assert b > r and b > g, (r, g, b)

    # Sunrise and golden hour go warm.
    for hour in (7, 18):
        r, g, b = tint_for(hour)
        assert r > b, (hour, r, g, b)

    # The midnight wrap must not jump, or the background flickers at 00:00.
    before, after = tint_for(23.99), tint_for(0.01)
    assert all(abs(a - b) <= 2 for a, b in zip(before, after)), (before, after)

    # Out-of-range hours wrap rather than falling off the table.
    assert tint_for(25.5) == tint_for(1.5)


class FakeBlock:
    def __init__(self, x, y):
        self.hp = 1000
        self.destroyed = False
        self.body = type("B", (), {"position": type("P", (), {"x": x, "y": y})()})()


def test_blast_damages_only_what_is_in_range():
    """TNT, mega TNT and lightning all route through blast(). If the radius
    test breaks, every one of them breaks at once."""
    import chunk as chunk_module
    import tnt
    from constants import BLOCK_SIZE

    near = FakeBlock(0, 0)          # Dead centre: maximum damage.
    edge = FakeBlock(2 * BLOCK_SIZE, 0)
    far = FakeBlock(50 * BLOCK_SIZE, 0)

    saved = dict(chunk_module.chunks)
    chunk_module.chunks.clear()
    chunk_module.chunks["test"] = [[near, edge, far]]
    try:
        tnt.blast((0, 0), 3 * BLOCK_SIZE, 100)
    finally:
        chunk_module.chunks.clear()
        chunk_module.chunks.update(saved)

    assert near.hp == 900, near.hp                 # Full 100 damage.
    assert 900 < edge.hp < 1000, edge.hp           # Partial, falls off.
    assert far.hp == 1000, far.hp                  # Untouched.


def test_storm_strikes_on_schedule_and_expires():
    import weather

    now = [0]
    storm = weather.Storm(duration_ms=5000, strike_interval_ms=1000,
                          clock=lambda: now[0])
    camera = type("C", (), {"shake": lambda self, *a: None})()
    pickaxe = type("P", (), {"body": type("B", (), {
        "position": type("Pos", (), {"x": 0.0, "y": 0.0})()})()})()

    assert not storm.expired()
    for _ in range(5):
        now[0] += 1000
        storm.update(pickaxe, camera, None)   # None: no sound in tests.

    assert storm.strikes == 5, storm.strikes
    assert storm.expired(), (now[0], storm.ends_at)


def test_earthquake_and_thunderstorm_set_and_clear_their_flags():
    import events

    for event_name, flag in (("EARTHQUAKE", "quake"), ("THUNDERSTORM", "storm")):
        mgr, clock = _manager(event_name)
        hud = FakeHud()

        clock.advance(60000)
        mgr.update(hud)                      # -> WARNING
        clock.advance(events.WARNING_MS)
        mgr.update(hud)                      # -> ACTIVE
        assert mgr.phase == events.ACTIVE, mgr.phase
        assert getattr(mgr, flag) is True, (event_name, flag)

        clock.advance(mgr.event["duration_ms"])
        mgr.update(hud)                      # -> back to IDLE
        assert getattr(mgr, flag) is False, (event_name, flag)


def test_lava_burn_halves_damage_and_water_cures_it():
    """The burn must survive a skin change and stack with SPIN rather than
    being overwritten by it -- both write to the damage path."""
    import pickaxe as pickaxe_mod

    now = [0]
    real_get_ticks = pickaxe_mod.pygame.time.get_ticks
    pickaxe_mod.pygame.time.get_ticks = lambda: now[0]
    try:
        p = pickaxe_mod.Pickaxe.__new__(pickaxe_mod.Pickaxe)
        p.damage, p.damage_multiplier = 10, 1
        p.overheated_until = p.spin_end_time = 0
        p.submerged = False
        p.is_enlarged = False

        assert p.heat_factor() == 1.0

        p.overheat(20000)
        assert p.overheated_until == 20000, p.overheated_until
        assert p.heat_factor() == 0.5

        # A burn and a spin coexist: 10 * 3 * 0.5 = 15, not 5 and not 30.
        p.damage_multiplier = 3
        assert p.damage * p.damage_multiplier * p.heat_factor() == 15

        # Water on a burn cures it.
        assert p.douse() == "cured"
        assert p.overheated_until == 0
        assert p.heat_factor() == 1.0

        # Water with nothing burning pours a pool instead -- never a no-op.
        assert p.douse() == "wet"
        assert p.overheated_until == 0
    finally:
        pickaxe_mod.pygame.time.get_ticks = real_get_ticks


def test_lava_never_generates_above_its_depth():
    """Force the RNG to always roll lava, then check the depth gate still
    keeps it out of shallow chunks."""
    import chunk as chunk_module

    class StubBlock:
        def __init__(self, space, x, y, name, atlas, items):
            self.name = name

    real_block, real_random = chunk_module.Block, chunk_module.random.random
    chunk_module.Block = StubBlock
    chunk_module.random.random = lambda: 0.0  # Always below LAVA_CHANCE.
    try:
        shallow = chunk_module.generate_chunk(0, chunk_module.LAVA_START_CHUNK - 1,
                                              None, None, None)
        deep = chunk_module.generate_chunk(0, chunk_module.LAVA_START_CHUNK,
                                           None, None, None)
    finally:
        chunk_module.Block = real_block
        chunk_module.random.random = real_random

    names_shallow = {b.name for row in shallow for b in row if b}
    names_deep = {b.name for row in deep for b in row if b}
    assert "lava" not in names_shallow, names_shallow
    assert "lava" in names_deep, names_deep


def test_water_pours_fills_then_drains():
    """The pool must fill from the pour, actually contain the axe, and drain
    back out -- if fill() never crosses the threshold, buoyancy never fires
    and !water silently does nothing."""
    from constants import BLOCK_SIZE
    import weather

    now = [0]
    axe = type("P", (), {"body": type("B", (), {
        "position": type("Pos", (), {"x": 500.0, "y": 2000.0})()})()})()

    pool = weather.Water(500.0, 2000.0, duration_ms=10000,
                         width_blocks=3.2, depth_blocks=1.2,
                         clock=lambda: now[0])

    # Nothing has poured in yet, so nothing floats.
    assert pool.fill() == 0.0, pool.fill()
    assert not pool.covers(500.0, 2000.0)

    # Droplets are spawned while pouring.
    pool.update(axe)
    assert pool.drops, "no droplets spawned during the pour"

    # Once the pour lands, the axe is in the water.
    now[0] = weather.Water.POUR_MS
    for _ in range(30):
        pool.update(axe)
    assert pool.fill() == 1.0, pool.fill()
    assert pool.covers(500.0, 2000.0)
    assert not pool.covers(500.0 + 5 * BLOCK_SIZE, 2000.0)   # Outside stays dry.

    # Mid-drain the level drops back below the float threshold.
    now[0] = 10000 - int(weather.Water.DRAIN_MS * 0.2)
    assert pool.fill() < 0.35, pool.fill()
    assert not pool.covers(500.0, 2000.0)

    now[0] = 10000
    assert pool.expired()


def test_water_takes_the_shape_of_the_mined_hole():
    """Water must pour around terrain, not float as a rectangle over it."""
    import chunk as chunk_module
    import weather
    from constants import BLOCK_SIZE, CHUNK_HEIGHT

    class SolidBlock:
        destroyed = False

    now = [0]
    axe = type("P", (), {"body": type("B", (), {
        "position": type("Pos", (), {"x": 4.5 * BLOCK_SIZE,
                                     "y": 4.5 * BLOCK_SIZE})()})()})()

    # One loaded chunk: every cell solid, then carve a single column out.
    saved = dict(chunk_module.chunks)
    chunk_module.chunks.clear()
    chunk_module.chunks[(0, 0)] = [[SolidBlock() for _ in range(9)]
                                   for _ in range(CHUNK_HEIGHT)]
    try:
        pool = weather.Water(4.5 * BLOCK_SIZE, 4.5 * BLOCK_SIZE,
                             duration_ms=10000, clock=lambda: now[0])
        now[0] = weather.Water.POUR_MS          # Fully poured.

        # Solid rock everywhere: the water has nowhere to go.
        assert pool.cells() == [], pool.cells()

        # Carve column 4 open; water may now occupy only that column.
        for row in chunk_module.chunks[(0, 0)]:
            row[4] = None
        rects = pool.cells()
        assert rects, "water found no room in the mined column"
        for rx, _ry, rw, _rh in rects:
            assert 4 * BLOCK_SIZE <= rx < 5 * BLOCK_SIZE, (rx, rw)
    finally:
        chunk_module.chunks.clear()
        chunk_module.chunks.update(saved)


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
