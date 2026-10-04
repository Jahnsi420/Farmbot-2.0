import pytest

from farmbot.deploy import line_points, spread

LINES = {"a": ((0.1, 0.4), (0.3, 0.1)), "b": ((0.7, 0.1), (0.9, 0.4))}


def test_line_points_are_evenly_spaced_on_the_line():
    pts = line_points(LINES["a"], 4)
    assert len(pts) == 4
    assert pts[0] == pytest.approx((0.125, 0.3625))
    assert pts[-1] == pytest.approx((0.275, 0.1375))
    for x, y in pts:
        assert y == pytest.approx(0.4 - (x - 0.1) * 1.5)


def test_spread_distributes_counts():
    pts = spread(LINES, ["a", "b"], 5)
    assert len(pts) == 5
    assert sum(1 for x, _ in pts if x < 0.5) == 3
    assert spread(LINES, ["a"], 0) == []


def test_spread_rejects_unknown_line():
    with pytest.raises(ValueError):
        spread(LINES, ["north"], 3)
