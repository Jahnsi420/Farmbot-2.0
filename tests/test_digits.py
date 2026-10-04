from pathlib import Path

import numpy as np
import pytest

from farmbot import digits, imaging

FIXTURES = sorted((Path(__file__).parent / "fixtures").glob("loot_*.png"))


@pytest.mark.parametrize("path", FIXTURES, ids=lambda p: p.stem)
def test_reads_real_loot_numbers(path):
    expected = int(path.stem.rsplit("_", 1)[1])
    assert digits.read_number(imaging.imread(path)) == expected


def test_unreadable_region_gives_none():
    grass = np.full((40, 200, 3), (90, 160, 40), np.uint8)
    assert digits.read_number(grass) is None


def test_trim_after_gap_drops_debris_right_of_number():
    mask = np.zeros((10, 100), bool)
    mask[2:8, 5:10] = True
    mask[2:8, 80:85] = True
    trimmed = digits._trim_after_gap(mask, max_gap=5)
    assert trimmed[2:8, 5:10].all() and not trimmed[:, 80:].any()


def test_split_wide_blob_of_touching_digits():
    blob = np.ones((20, 40), bool)
    blob[:, 19] = False  # thin neck between two digits
    blob[5:15, 19] = True
    parts = digits._split_wide(blob)
    assert len(parts) == 2


def test_learn_rejects_wrong_digit_count():
    img = imaging.imread(FIXTURES[0])
    with pytest.raises(ValueError):
        digits.learn([(img, "1")])
