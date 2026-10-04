import numpy as np

from farmbot.vision import Templates, crop_rel


def test_find_template(tmp_path):
    import cv2

    rng = np.random.default_rng(0)
    screen = rng.integers(0, 255, (400, 600, 3), dtype=np.uint8)
    button = screen[300:340, 50:150].copy()
    cv2.imwrite(str(tmp_path / "attack_button.png"), button)

    t = Templates(tmp_path)
    m = t.find(screen, "attack_button")
    assert m is not None and (m.x, m.y) == (50, 300)
    assert m.center == (100, 320)
    # restricted to a region that doesn't contain the button
    assert t.find(screen, "attack_button", region=(0.5, 0.0, 1.0, 0.5)) is None


def test_crop_rel():
    img = np.zeros((100, 200, 3), np.uint8)
    crop, x, y = crop_rel(img, (0.5, 0.5, 1.0, 1.0))
    assert crop.shape == (50, 100, 3) and (x, y) == (100, 50)
