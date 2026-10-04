import pytest

from farmbot.deploy import SIDES, Diamond, edge_points, spread

D = Diamond(top=(0.5, 0.1), right=(0.9, 0.5), bottom=(0.5, 0.9), left=(0.1, 0.5))


def test_center():
    assert D.center == pytest.approx((0.5, 0.5))


def test_edge_points_lie_on_edge():
    pts = edge_points(D, "top_right", 5)
    assert len(pts) == 5
    for x, y in pts:
        # top_right edge: from (0.5, 0.1) to (0.9, 0.5) -> y = x - 0.4
        assert y == pytest.approx(x - 0.4)
        assert 0.5 < x < 0.9


def test_outward_moves_away_from_center():
    inner = edge_points(D, "bottom_left", 3)
    outer = edge_points(D, "bottom_left", 3, outward=0.1)
    for (ix, iy), (ox, oy) in zip(inner, outer):
        assert ox < ix and oy > iy


def test_spread_distributes_counts():
    pts = spread(D, list(SIDES), 10)
    assert len(pts) == 10
    assert spread(D, ["top_left"], 0) == []


def test_spread_rejects_unknown_side():
    with pytest.raises(ValueError):
        spread(D, ["north"], 3)
