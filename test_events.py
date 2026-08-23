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
