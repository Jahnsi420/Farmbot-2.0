import pytest

from farmbot.loot import Loot, LootFilter


def test_any_mode():
    f = LootFilter(min_gold=300_000, min_elixir=300_000, mode="any")
    assert f.accept(Loot(350_000, 10_000, None))
    assert not f.accept(Loot(100_000, 100_000, 0))
    assert not f.accept(Loot(None, None, None))


def test_all_mode():
    f = LootFilter(min_gold=200_000, min_elixir=200_000, min_dark=1_000, mode="all")
    assert f.accept(Loot(250_000, 250_000, 2_000))
    assert not f.accept(Loot(250_000, 250_000, 500))


def test_sum_mode():
    f = LootFilter(mode="sum", min_total=500_000)
    assert f.accept(Loot(300_000, 250_000, None))
    assert not f.accept(Loot(300_000, None, None))


def test_no_minimum_accepts_everything():
    assert LootFilter().accept(Loot(None, None, None))


def test_invalid_mode():
    with pytest.raises(ValueError):
        LootFilter(mode="most")
