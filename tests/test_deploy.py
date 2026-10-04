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


def test_to_pixels_shifts_lines_away_from_center():
    from farmbot.deploy import to_pixels

    lines = {"tl": ((0.1, 0.4), (0.3, 0.1)), "tr": ((0.7, 0.1), (0.9, 0.4))}
    plain = to_pixels(lines, 1000, 500)
    assert [c for p in plain["tl"] for c in p] == pytest.approx([100, 200, 300, 50])
    out = to_pixels(lines, 1000, 500, shift=10)
    for name in lines:
        (ax, ay), _ = out[name]
        (px, py), _ = plain[name]
        assert ay < py  # both upper lines move up, i.e. outwards
        assert abs(ax - 500) > abs(px - 500)  # and away from the middle
        assert ((ax - px) ** 2 + (ay - py) ** 2) ** 0.5 == pytest.approx(10)
