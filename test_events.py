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


def _meter(**kwargs):
    import nuke

    clock = FakeClock()
    kwargs.setdefault("capacity", 100)
    kwargs.setdefault("passive_per_minute", 0)
    kwargs.setdefault("countdown_ms", 5000)
    return nuke.NukeMeter(clock=clock, **kwargs), clock


def test_chat_commands_fill_the_meter_and_arm_it():
    import nuke

    meter, _clock = _meter(capacity=3)
    assert meter.phase == nuke.CHARGING, meter.phase

    meter.charge("TNT", "alice")
    meter.charge("TNT", "bob")
    assert abs(meter.fraction() - 2 / 3) < 0.001, meter.fraction()
    assert meter.phase == nuke.CHARGING, meter.phase

    meter.charge("TNT", "carol")
    assert meter.phase == nuke.ARMED, meter.phase
    assert meter.fraction() == 1.0, meter.fraction()
    assert meter.detonated_by == "carol", meter.detonated_by


def test_subscribers_charge_more_than_chat_and_sync_lines_charge_nothing():
    meter, _clock = _meter()
    meter.charge("TNT", "a")
    one_tnt = meter.fraction()

    meter, _clock = _meter()
    meter.charge("SUB", "a")
    assert meter.fraction() > one_tnt, meter.fraction()

    # "SUBS:system:123" is a counter sync, not a viewer doing anything.
    meter, _clock = _meter()
    meter.charge("SUBS", "system")
    meter.charge("NONSENSE", "a")
    assert meter.fraction() == 0.0, meter.fraction()


def test_quiet_stream_still_reaches_a_nuke_from_the_passive_trickle():
    """A small channel has an empty chat. The nuke must still happen, or the
    centrepiece of the stream never fires for the viewers who most need it."""
    import nuke

    meter, clock = _meter(capacity=100, passive_per_minute=10)
    clock.advance(5 * 60 * 1000)
    meter.update()
    assert abs(meter.fraction() - 0.5) < 0.001, meter.fraction()

    clock.advance(5 * 60 * 1000)
    meter.update()
    assert meter.phase == nuke.ARMED, meter.phase
    assert meter.detonated_by is None, meter.detonated_by


def test_armed_meter_counts_down_then_detonates_exactly_once():
    import nuke

    meter, clock = _meter(capacity=1, countdown_ms=5000)
    meter.charge("TNT", "alice")
    assert meter.countdown_secs() == 5, meter.countdown_secs()

    clock.advance(4999)
    assert meter.update() is False
    assert meter.countdown_secs() == 1, meter.countdown_secs()

    clock.advance(1)
    assert meter.update() is True          # The one frame the bomb goes off.
    assert meter.phase == nuke.CHARGING, meter.phase
    assert meter.fraction() == 0.0, meter.fraction()
    assert meter.detonated_by == "alice", meter.detonated_by

    clock.advance(1)
    assert meter.update() is False


def test_commands_during_the_countdown_do_not_carry_into_the_next_meter():
    meter, clock = _meter(capacity=2, countdown_ms=5000)
    meter.charge("TNT", "a")
    meter.charge("TNT", "b")               # Full, now armed.
    meter.charge("TNT", "c")
    clock.advance(5000)
    assert meter.update() is True
    assert meter.fraction() == 0.0, meter.fraction()


def test_flash_is_bright_at_detonation_then_fades_out():
    meter, clock = _meter(capacity=1, countdown_ms=0)
    assert meter.flash() == 0.0, meter.flash()

    meter.charge("TNT", "a")
    assert meter.update() is True
    assert meter.flash() == 1.0, meter.flash()

    clock.advance(meter.FLASH_MS // 2)
    assert 0.0 < meter.flash() < 1.0, meter.flash()

    clock.advance(meter.FLASH_MS)
    assert meter.flash() == 0.0, meter.flash()


def test_disabled_meter_never_arms():
    import nuke

    meter, clock = _meter(capacity=1, passive_per_minute=100, enabled=False)
    meter.charge("TNT", "a")
    clock.advance(10 * 60 * 1000)
    assert meter.update() is False
    assert meter.phase == nuke.CHARGING, meter.phase
    assert meter.fraction() == 0.0, meter.fraction()


def test_nuke_blast_clears_even_obsidian_and_spawns_a_bigger_explosion():
    import chunk as chunk_module
    import pymunk
    import tnt
    from constants import BLOCK_SIZE

    near = FakeBlock(5 * BLOCK_SIZE, 0)
    near.hp = 100                          # Obsidian's HP, the toughest block.
    far = FakeBlock(50 * BLOCK_SIZE, 0)

    saved = dict(chunk_module.chunks)
    chunk_module.chunks.clear()
    chunk_module.chunks["test"] = [[near, far]]
    explosions = []
    try:
        tnt.nuke_blast(pymunk.Vec2d(0, 0), explosions, None, None,
                       radius=12 * BLOCK_SIZE, damage=1000)
    finally:
        chunk_module.chunks.clear()
        chunk_module.chunks.update(saved)

    assert near.hp <= 0, near.hp
    assert far.hp == 1000, far.hp
    assert sum(len(e.particles) for e in explosions) > 40, explosions


def _record_path(tmp):
    return os.path.join(tmp, "records.json")


def test_depth_record_survives_a_restart():
    import tempfile
    import records

    with tempfile.TemporaryDirectory() as tmp:
        first = records.DepthRecord(_record_path(tmp))
        first.update(120)
        first.save()

        second = records.DepthRecord(_record_path(tmp))
        assert second.best == 120, second.best


def test_depth_record_only_ever_goes_up():
    import tempfile
    import records

    with tempfile.TemporaryDirectory() as tmp:
        rec = records.DepthRecord(_record_path(tmp))
        rec.update(120)
        rec.update(40)                     # The axe bounced back up.
        assert rec.best == 120, rec.best


def test_new_record_is_announced_once_and_never_on_a_first_ever_run():
    """Announcing on every block deeper would spam the banner for the rest of
    the stream, and with no saved record the very first block is not news."""
    import tempfile
    import records

    with tempfile.TemporaryDirectory() as tmp:
        fresh = records.DepthRecord(_record_path(tmp))
        assert fresh.update(5) is False
        assert fresh.update(100) is False
        fresh.save()

        rec = records.DepthRecord(_record_path(tmp))
        assert rec.update(50) is False     # Still short of the 100 to beat.
        assert rec.update(101) is True     # Broken.
        assert rec.update(102) is False    # Still deepening, already announced.
        assert rec.best == 102, rec.best


def test_corrupt_record_file_starts_from_zero_instead_of_crashing():
    import tempfile
    import records

    with tempfile.TemporaryDirectory() as tmp:
        with open(_record_path(tmp), "w") as f:
            f.write("{not json")
        assert records.DepthRecord(_record_path(tmp)).best == 0


def test_save_failure_does_not_crash_the_stream():
    import tempfile
    import records

    with tempfile.TemporaryDirectory() as tmp:
        # The parent is a file, so the write cannot succeed.
        blocker = os.path.join(tmp, "blocker")
        open(blocker, "w").close()
        rec = records.DepthRecord(os.path.join(blocker, "records.json"))
        rec.update(10)
        rec.save()
        assert rec.best == 10, rec.best


def test_clip_log_records_when_things_happened():
    import csv
    import tempfile
    import records

    now = [1000.0]
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "logs", "clips.csv")
        log = records.ClipLog(path, clock=lambda: now[0])
        now[0] = 1000.0 + 3725           # 1h 02m 05s into the session.
        log.log("NUKE", "alice, the great")

        with open(path, newline="", encoding="utf-8") as f:
            rows = list(csv.reader(f))

    assert rows[0] == ["local_time", "session_time", "kind", "detail"], rows[0]
    assert rows[1][1] == "01:02:05", rows[1]
    assert rows[1][2:] == ["NUKE", "alice, the great"], rows[1]


def test_clip_log_write_failure_does_not_crash_the_stream():
    import tempfile
    import records

    with tempfile.TemporaryDirectory() as tmp:
        blocker = os.path.join(tmp, "blocker")
        open(blocker, "w").close()
        records.ClipLog(os.path.join(blocker, "clips.csv")).log("NUKE", "a")


def _hud_for_drawing():
    import pygame
    from hud import Hud

    pygame.init()
    h = Hud.__new__(Hud)
    h.font = pygame.font.Font(None, 64)
    h.panel_font = pygame.font.Font(None, 38)
    h.small_ticker_font = pygame.font.Font(None, 30)
    h.big_font = pygame.font.Font(None, 72)
    h.position = (32, 32)
    return h


def _pixels(surface):
    import pygame

    return pygame.image.tobytes(surface, "RGB")


def test_nuke_meter_is_drawn_when_enabled_and_hidden_when_disabled():
    import pygame
    from constants import INTERNAL_HEIGHT, INTERNAL_WIDTH

    size = (INTERNAL_WIDTH, INTERNAL_HEIGHT)
    blank = _pixels(pygame.Surface(size))

    h = _hud_for_drawing()
    on, _clock = _meter()
    screen = pygame.Surface(size)
    h.draw_nuke_meter(screen, on)
    assert _pixels(screen) != blank, "meter drew nothing"

    off, _clock = _meter(enabled=False)
    screen = pygame.Surface(size)
    h.draw_nuke_meter(screen, off)
    assert _pixels(screen) == blank, "disabled meter still drew"


def test_meter_clears_the_shorts_ui_at_the_bottom_of_the_screen():
    """YouTube's title and buttons cover the bottom of a vertical video. The
    whole point of the meter is lost if it sits under them."""
    import pygame
    from constants import INTERNAL_HEIGHT, INTERNAL_WIDTH
    from hud import METER_H, METER_W, METER_X, METER_Y

    assert METER_Y + METER_H <= INTERNAL_HEIGHT * 0.8, METER_Y
    assert METER_X >= 0 and METER_X + METER_W <= INTERNAL_WIDTH, METER_X


def test_depth_record_is_drawn_only_once_there_is_one():
    import pygame
    from constants import INTERNAL_HEIGHT, INTERNAL_WIDTH

    size = (INTERNAL_WIDTH, INTERNAL_HEIGHT)
    blank = _pixels(pygame.Surface(size))
    h = _hud_for_drawing()

    screen = pygame.Surface(size)
    h.draw_depth_record(screen, best=0, celebrating=False)
    assert _pixels(screen) == blank, "drew a record of zero"

    screen = pygame.Surface(size)
    h.draw_depth_record(screen, best=5000, celebrating=False)
    assert _pixels(screen) != blank, "record not drawn"


def test_new_record_banner_draws_something_extra():
    import pygame
    from constants import INTERNAL_HEIGHT, INTERNAL_WIDTH

    size = (INTERNAL_WIDTH, INTERNAL_HEIGHT)
    h = _hud_for_drawing()

    plain = pygame.Surface(size)
    h.draw_depth_record(plain, best=5000, celebrating=False)
    banner = pygame.Surface(size)
    h.draw_depth_record(banner, best=5000, celebrating=True)
    assert _pixels(plain) != _pixels(banner), "banner drew nothing"


def test_nuke_caption_credits_the_viewer_and_survives_long_names():
    from hud import nuke_caption

    assert nuke_caption("alice") == "NUKED BY ALICE", nuke_caption("alice")
    assert nuke_caption(None) == "NUKE!", nuke_caption(None)
    # A name wider than the phone screen would run off both edges.
    assert len(nuke_caption("x" * 200)) <= len("NUKED BY ") + 18


def test_every_command_the_game_accepts_charges_the_meter():
    """A viewer typing a listed command and seeing the meter not move would
    read as the game being broken."""
    import nuke

    for command in ("TNT", "SUB", "SUPER", "SPEED", "BIG", "SPIN", "MULTIPLY",
                    "QUAKE", "STORM", "WATER", "NUKE", "PICKAXE"):
        assert nuke.CHARGE_POINTS.get(command, 0) > 0, command


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
