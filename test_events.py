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
