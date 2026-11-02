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
                    "QUAKE", "STORM", "WATER", "NUKE", "PICKAXE",
                    "HELI", "LEFT", "MID", "RIGHT"):
        assert nuke.CHARGE_POINTS.get(command, 0) > 0, command


# ---------- command menu ----------

def _real_hud():
    """A real Hud, icons and all. The menu is built from them, so bypassing
    __init__ would test nothing."""
    from pathlib import Path
    import pygame
    from atlas import create_texture_atlas
    from hud import Hud

    pygame.init()
    if pygame.display.get_surface() is None:
        pygame.display.set_mode((1, 1))
    assets = Path(__file__).parent / "src" / "assets"
    atlas, items = create_texture_atlas(assets)
    return Hud(atlas, items)


def test_menu_lists_every_command_exactly_once():
    """The old NEW COMMAND box repeated six rows. Each command gets one row."""
    import hud

    listed = [label for _name, _color, labels in hud.MENU_GROUPS for label in labels]
    assert len(listed) == len(set(listed)), listed
    assert set(listed) == {row[0] for row in hud.COMMAND_ROWS}, listed
    assert "HELI" in listed, listed


def test_menu_and_feed_stop_above_the_nuke_meter():
    import hud

    bottom = hud.MENU_Y + hud.menu_height() + hud.FEED_GAP + hud.FEED_H
    assert bottom < hud.METER_Y, bottom
    assert hud.MENU_X + hud.MENU_W <= 1080, hud.MENU_X


def test_real_menu_draws():
    import pygame
    from constants import INTERNAL_HEIGHT, INTERNAL_WIDTH

    size = (INTERNAL_WIDTH, INTERNAL_HEIGHT)
    h = _real_hud()
    screen = pygame.Surface(size)
    h.draw_command_panel(screen)
    assert _pixels(screen) != _pixels(pygame.Surface(size)), "menu drew nothing"


def test_feed_shows_the_latest_three_actions():
    """Viewers typing and seeing their own name is the point of the feed."""
    from collections import deque
    from hud import Hud

    h = Hud.__new__(Hud)
    h.feed = deque(maxlen=3)
    for i in range(5):
        h.add_feed(f"user{i}", "TNT")
    assert [u for u, _c in h.feed] == ["USER4", "USER3", "USER2"], list(h.feed)


def test_feed_ignores_lines_with_no_viewer_behind_them():
    from collections import deque
    from hud import Hud

    h = Hud.__new__(Hud)
    h.feed = deque(maxlen=3)
    h.add_feed("system", None)
    assert not h.feed, list(h.feed)


def test_feed_label_names_what_the_viewer_actually_typed():
    from hud import feed_label

    assert feed_label("TNT", "") == "TNT"
    assert feed_label("SPEED", "FAST") == "FAST"
    assert feed_label("PICKAXE", "diamond") == "DIAMOND"
    assert feed_label("SUB", "") == "SUB"
    assert feed_label("SUBS", "123") is None     # A counter sync, not a viewer.
    assert feed_label("NONSENSE", "") is None


# ---------- talking pickaxe ----------

class FixedRng:
    """Always picks the first option, so spoken lines are predictable."""

    def choice(self, seq):
        return seq[0]

    def randint(self, a, b):
        return a


def _voice(**kwargs):
    import voice

    clock = FakeClock()
    kwargs.setdefault("rng", FixedRng())
    return voice.PickaxeVoice(clock=clock, **kwargs), clock


def test_display_name_is_safe_to_put_on_screen():
    from voice import display_name

    assert display_name("@rahul_07") == "RAHUL_07"
    assert len(display_name("x" * 200)) <= 14
    # The stream font has no Devanagari glyphs: this would draw as empty boxes.
    assert display_name("राहुल") == "SOMEONE"
    assert display_name("") == "SOMEONE"
    assert display_name(None) == "SOMEONE"


def test_pickaxe_speaks_the_viewers_name():
    import voice

    v, _clock = _voice()
    voice.LINES["TEST"] = (voice.SCARED, ["{USER} WHY"])
    v.react("TEST", "rahul")
    assert v.line == "RAHUL WHY", v.line
    assert v.mood == voice.SCARED, v.mood


def test_name_containing_braces_cannot_break_the_line():
    import voice

    v, _clock = _voice()
    voice.LINES["TEST"] = (voice.SCARED, ["{USER} WHY"])
    v.react("TEST", "{0}{bad}")
    assert v.line is not None, v.line


def test_speech_bubble_expires_and_mood_returns_to_neutral():
    import voice

    v, clock = _voice()
    v.react("TNT", "a")
    assert v.line is not None
    clock.advance(voice.BUBBLE_MS)
    v.update()
    assert v.line is None, v.line
    assert v.mood == voice.NEUTRAL, v.mood


def test_chat_spam_cannot_talk_over_the_current_line():
    """In a busy chat a new line every command is unreadable flicker."""
    import voice

    v, clock = _voice()
    v.react("TNT", "first")
    spoken = v.line
    clock.advance(100)
    v.react("SPIN", "second")
    assert v.line == spoken, v.line


def test_big_moments_interrupt_whatever_is_being_said():
    import voice

    v, clock = _voice()
    v.react("TNT", "a")
    clock.advance(100)
    v.react("DETONATE", force=True)
    assert v.line == voice.LINES["DETONATE"][1][0], v.line


def test_quiet_pickaxe_starts_talking_to_itself():
    """An empty chat is exactly when the stream most needs a personality."""
    import voice

    v, clock = _voice(idle_min_ms=1000, idle_max_ms=1000)
    clock.advance(999)
    v.update()
    assert v.line is None, v.line
    clock.advance(1)
    v.update()
    assert v.line is not None


def test_unknown_reaction_and_disabled_voice_stay_silent():
    v, _clock = _voice()
    v.react("NOT_A_KEY", "a")
    assert v.line is None, v.line

    v, clock = _voice(enabled=False, idle_min_ms=1, idle_max_ms=1)
    v.react("TNT", "a", force=True)
    clock.advance(10)
    v.update()
    assert v.line is None, v.line


def test_every_line_fits_in_a_speech_bubble():
    import voice

    for key, (_mood, lines) in voice.LINES.items():
        assert lines, key
        for line in lines:
            filled = line.replace("{USER}", "W" * voice.NAME_MAX)
            assert len(filled) <= voice.LINE_MAX, (key, filled)


def test_moments_nobody_caused_do_not_blame_someone():
    """An automatic helicopter saying "SOMEONE CALLED BACKUP" is just wrong."""
    import voice

    for key in ("HELI_AUTO", "ARMED", "DETONATE", "RECORD", "BOMBING", "LAVA", "IDLE"):
        for line in voice.LINES[key][1]:
            assert "{USER}" not in line, (key, line)


def test_face_stays_on_the_pick_head_as_the_axe_rotates():
    import math
    from hud import face_offset

    x0, y0 = face_offset(0, 1)
    assert x0 > 0 and y0 < 0, (x0, y0)                 # Up and right: the head.

    x180, y180 = face_offset(math.pi, 1)
    assert abs(x180 + x0) < 0.01 and abs(y180 + y0) < 0.01, (x180, y180)

    big_x, big_y = face_offset(0, 3)                   # !big triples the sprite.
    assert abs(big_x - 3 * x0) < 0.01 and abs(big_y - 3 * y0) < 0.01


def test_real_face_and_bubble_draw():
    import pygame
    import pymunk
    import voice
    from constants import INTERNAL_HEIGHT, INTERNAL_WIDTH

    size = (INTERNAL_WIDTH, INTERNAL_HEIGHT)
    blank = _pixels(pygame.Surface(size))
    h = _real_hud()
    axe = type("Axe", (), {
        "body": pymunk.Body(1, 1),
        "texture": pygame.Surface((120, 120)),
    })()
    axe.body.position = (540, 960)
    camera = type("Cam", (), {"offset_x": 0, "offset_y": 0})()

    for mood in (voice.NEUTRAL, voice.SCARED, voice.HAPPY, voice.DIZZY):
        v, _clock = _voice()
        v.mood = mood
        screen = pygame.Surface(size)
        h.draw_pickaxe_face(screen, axe, camera, v)
        assert _pixels(screen) != blank, mood

    v, _clock = _voice()
    screen = pygame.Surface(size)
    h.draw_speech_bubble(screen, axe, camera, v)
    assert _pixels(screen) == blank, "bubble drawn with nothing to say"

    v.react("TNT", "a")
    h.draw_speech_bubble(screen, axe, camera, v)
    assert _pixels(screen) != blank, "bubble drew nothing"


def test_long_viewer_names_stay_on_their_tnt():
    """A long name ran off both edges of the screen, right over the menu."""
    from pathlib import Path
    import pygame
    import pymunk
    import tnt
    from atlas import create_texture_atlas
    from voice import NAME_MAX

    pygame.init()
    if pygame.display.get_surface() is None:
        pygame.display.set_mode((1, 1))
    atlas, items = create_texture_atlas(Path(__file__).parent / "src" / "assets")
    sound = type("S", (), {"play_sound": lambda self, name: None})()

    bomb = tnt.Tnt(pymunk.Space(), 0, 0, atlas, items, sound,
                   owner_name="Prasang_NukeCraft_Fan_With_A_Very_Long_Name")
    assert len(bomb.owner_name) <= NAME_MAX, bomb.owner_name

    # Anonymous TNT stays anonymous rather than becoming "SOMEONE".
    assert tnt.Tnt(pymunk.Space(), 0, 0, atlas, items, sound).owner_name is None


def test_hindi_username_cannot_jam_the_command_file():
    """On Windows the file was read as cp1252, where some UTF-8 Hindi bytes are
    undefined. The read failed before the file was cleared, so that one line
    failed forever and every later chat command was silently lost."""
    import tempfile
    from pathlib import Path
    import main

    real_path, real_queue = main.COMMANDS_PATH, list(main.chat_queue)
    main.chat_queue.clear()
    with tempfile.TemporaryDirectory() as tmp:
        main.COMMANDS_PATH = Path(tmp) / "commands.txt"
        main.COMMANDS_PATH.write_bytes("SPIN:राहुल\nTNT:alice\n".encode("utf-8"))
        try:
            main.check_command_file()
            seen = [(c, u) for c, u, _v in main.chat_queue]
            left = main.COMMANDS_PATH.read_text()
        finally:
            main.COMMANDS_PATH = real_path
            main.chat_queue[:] = real_queue
            for queue in (main.spin_queue, main.tnt_queue):
                queue.clear()

    assert seen == [("SPIN", "राहुल"), ("TNT", "alice")], seen
    assert left == "", repr(left)


# ---------- helicopter ----------

def _heli(pilot="alice", vote_ms=10000):
    import helicopter

    clock = FakeClock()
    return helicopter.Helicopter(pilot, vote_ms=vote_ms, clock=clock), clock


def _fly_until(heli, clock, phase, limit_ms=120000):
    """Advance a frame at a time, collecting every bomb dropped on the way."""
    bombs = []
    for _ in range(limit_ms // 16):
        if heli.phase == phase:
            return bombs
        clock.advance(16)
        bombs.extend(heli.update())
    raise AssertionError(f"never reached {phase}, stuck in {heli.phase}")


def test_helicopter_arrives_waits_for_the_vote_then_bombs_then_leaves():
    import helicopter

    heli, clock = _heli()
    assert heli.phase == helicopter.ARRIVING, heli.phase

    assert _fly_until(heli, clock, helicopter.VOTING) == []
    clock.advance(9999)
    assert heli.update() == []
    assert heli.phase == helicopter.VOTING, heli.phase

    clock.advance(1)
    heli.update()
    assert heli.phase == helicopter.BOMBING, heli.phase

    _fly_until(heli, clock, helicopter.GONE)


def test_helicopter_hovers_fully_on_screen_during_the_vote():
    """The vote is when everyone is looking at it, and when they need the menu
    to see what to type. The art is 300px wide."""
    import helicopter
    from hud import MENU_X

    heli, clock = _heli()
    _fly_until(heli, clock, helicopter.VOTING)
    assert heli.x - 150 >= 0, heli.x
    assert heli.x + 150 <= MENU_X, heli.x


def test_viewer_gets_one_vote_and_can_change_it():
    """Otherwise one viewer spamming LEFT decides every bombing run."""
    import helicopter

    heli, clock = _heli()
    _fly_until(heli, clock, helicopter.VOTING)
    heli.vote("spammer", "LEFT")
    heli.vote("spammer", "LEFT")
    heli.vote("spammer", "LEFT")
    assert heli.tally() == {"LEFT": 1, "MID": 0, "RIGHT": 0}, heli.tally()

    heli.vote("spammer", "RIGHT")
    assert heli.tally() == {"LEFT": 0, "MID": 0, "RIGHT": 1}, heli.tally()


def test_votes_only_count_during_the_vote():
    import helicopter

    heli, clock = _heli()
    heli.vote("early", "LEFT")
    assert sum(heli.tally().values()) == 0, heli.tally()

    _fly_until(heli, clock, helicopter.VOTING)
    clock.advance(10000)
    heli.update()
    heli.vote("late", "LEFT")
    assert sum(heli.tally().values()) == 0, heli.tally()


def _bombs_by_lane(bombs):
    import helicopter

    counts = {lane: 0 for lane in helicopter.LANES}
    megas = {lane: 0 for lane in helicopter.LANES}
    for x, kind in bombs:
        lane = min(helicopter.LANES, key=lambda l: abs(helicopter.LANES[l] - x))
        counts[lane] += 1
        if kind == helicopter.MEGA:
            megas[lane] += 1
    return counts, megas


def test_winning_lane_gets_hit_hardest():
    import helicopter

    heli, clock = _heli()
    _fly_until(heli, clock, helicopter.VOTING)
    heli.vote("a", "LEFT")
    heli.vote("b", "RIGHT")
    heli.vote("c", "RIGHT")
    bombs = _fly_until(heli, clock, helicopter.GONE)

    counts, megas = _bombs_by_lane(bombs)
    assert counts["RIGHT"] > counts["LEFT"], counts
    assert counts["RIGHT"] > counts["MID"], counts
    assert counts["LEFT"] > 0 and counts["MID"] > 0, counts   # Left, mid AND right.
    assert megas["RIGHT"] == 1, megas
    assert megas["LEFT"] == 0 and megas["MID"] == 0, megas


def test_empty_chat_still_gets_a_full_bombing_run():
    import helicopter

    heli, clock = _heli()
    bombs = _fly_until(heli, clock, helicopter.GONE)
    counts, _megas = _bombs_by_lane(bombs)
    assert counts["LEFT"] == counts["MID"] == counts["RIGHT"] > 0, counts


def test_tied_vote_favours_nobody():
    import helicopter

    heli, clock = _heli()
    _fly_until(heli, clock, helicopter.VOTING)
    heli.vote("a", "LEFT")
    heli.vote("b", "RIGHT")
    assert heli.winner() is None, heli.winner()


def test_bombs_drop_inside_the_shaft_in_flight_order():
    """A bomb outside the bedrock walls explodes where nobody can see it."""
    import helicopter
    from constants import BLOCK_SIZE, CHUNK_WIDTH

    heli, clock = _heli()
    _fly_until(heli, clock, helicopter.VOTING)
    heli.vote("a", "MID")
    bombs = _fly_until(heli, clock, helicopter.GONE)

    xs = [x for x, _kind in bombs]
    assert xs
    assert all(BLOCK_SIZE < x < BLOCK_SIZE * (CHUNK_WIDTH - 1) for x in xs), xs
    assert xs == sorted(xs), xs


def _dispatcher(**kwargs):
    import helicopter

    clock = FakeClock()
    kwargs.setdefault("cooldown_ms", 30000)
    kwargs.setdefault("auto_ms", 240000)
    kwargs.setdefault("vote_ms", 1000)
    return helicopter.Dispatcher(clock=clock, **kwargs), clock


def _run_dispatcher_until_clear(dispatcher, clock):
    for _ in range(200000 // 16):
        if dispatcher.active is None:
            return
        clock.advance(16)
        dispatcher.update()
    raise AssertionError("helicopter never left")


def test_heli_spam_only_launches_one():
    d, _clock = _dispatcher()
    assert d.request("first") is True
    first = d.active
    assert d.request("second") is False
    assert d.active is first
    assert d.active.pilot == "first", d.active.pilot


def test_heli_has_a_cooldown_after_it_leaves():
    d, clock = _dispatcher()
    d.request("a")
    _run_dispatcher_until_clear(d, clock)

    assert d.request("b") is False
    clock.advance(30000)
    assert d.request("b") is True


def test_quiet_stream_still_gets_a_helicopter():
    d, clock = _dispatcher(auto_ms=240000)
    clock.advance(239999)
    d.update()
    assert d.active is None
    clock.advance(1)
    d.update()
    assert d.active is not None
    assert d.active.pilot is None, d.active.pilot


def test_chat_summoning_a_helicopter_resets_the_auto_timer():
    d, clock = _dispatcher(auto_ms=240000)
    clock.advance(200000)
    d.request("a")
    _run_dispatcher_until_clear(d, clock)
    clock.advance(1000)
    d.update()
    assert d.active is None, "auto heli fired straight after a chat one"


def test_votes_with_no_helicopter_up_are_ignored():
    d, _clock = _dispatcher()
    d.vote("a", "LEFT")                     # Must not raise.
    assert d.active is None


def test_disabled_dispatcher_never_flies():
    d, clock = _dispatcher(enabled=False)
    assert d.request("a") is False
    clock.advance(10_000_000)
    d.update()
    assert d.active is None


def test_real_helicopter_and_vote_panel_draw():
    import pygame
    import helicopter
    from constants import INTERNAL_HEIGHT, INTERNAL_WIDTH

    size = (INTERNAL_WIDTH, INTERNAL_HEIGHT)
    blank = _pixels(pygame.Surface(size))
    h = _hud_for_drawing()

    heli, clock = _heli()
    _fly_until(heli, clock, helicopter.VOTING)
    heli.vote("a", "LEFT")
    screen = pygame.Surface(size)
    h.draw_helicopter(screen, heli)
    assert _pixels(screen) != blank, "helicopter drew nothing"

    # Autopilot has no name to show, and that must not crash the stream.
    heli, clock = _heli(pilot=None)
    _fly_until(heli, clock, helicopter.VOTING)
    h.draw_helicopter(pygame.Surface(size), heli)


def test_blocks_the_pickaxe_has_passed_leave_the_physics_world():
    import pygame
    import pymunk
    import chunk
    from block import Block

    atlas = pygame.Surface((64, 64))
    items = {"block": {"stone": pygame.Rect(0, 0, 16, 16)}}
    space = pymunk.Space()

    def stone():
        return Block(space, 0, 0, "stone", atlas, items)

    # A mined block has already left the world; removing it twice would crash.
    mined = stone()
    mined.hp = 0
    mined.update(space, None)

    untouched = stone()
    passed = [[untouched, mined, None]]
    ahead = [[stone(), stone()]]
    saved = dict(chunk.chunks)
    chunk.chunks.clear()
    chunk.chunks.update({(0, 3): passed, (0, 4): ahead})
    try:
        chunk.clean_chunks(4, space)
        assert list(chunk.chunks) == [(0, 4)], list(chunk.chunks)
        assert len(space.shapes) == 2, f"{len(space.shapes)} shapes left, expected the 2 ahead"
        assert len(space.bodies) == 2, f"{len(space.bodies)} bodies left, expected the 2 ahead"
        assert untouched.shape.body is None, "passed block's shape still points at its body"
        assert mined.shape.body is None, "mined block's shape still points at its body"
    finally:
        chunk.chunks.clear()
        chunk.chunks.update(saved)


def _thing_in_space(space):
    import pymunk

    body = pymunk.Body(1, 1)
    shape = pymunk.Circle(body, 5)
    space.add(body, shape)
    return body, shape


def test_detonated_tnt_lets_go_of_its_body():
    # A shape still pointing at a freed body crashes the whole game, with no
    # error message, when Python later frees the shape.
    import pymunk
    import tnt

    for cls in (tnt.Tnt, tnt.MegaTnt):
        space = pymunk.Space()
        bomb = cls.__new__(cls)
        bomb.space = space
        bomb.detonated = True
        bomb.body, bomb.shape = _thing_in_space(space)
        bombs = [bomb]
        bomb.update(bombs, [], None)
        assert bombs == [], cls
        assert bomb.shape.body is None, f"{cls.__name__} shape still points at its body"
        assert len(space.shapes) == 0, cls


def test_despawned_clones_let_go_of_their_body():
    from types import SimpleNamespace
    import pymunk
    import pickaxe

    space = pymunk.Space()
    body, shape = _thing_in_space(space)
    clones = [SimpleNamespace(body=body, shapes=[shape])]
    pickaxe.despawn_clones(space, clones)
    assert clones == []
    assert shape.body is None, "clone shape still points at its body"
    assert len(space.shapes) == 0


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
