import numpy as np
import pytest

from farmbot import imaging
from farmbot.vision import Templates, crop_rel, preprocess_digits


@pytest.fixture(params=["opencv", "numpy"])
def backend(request, monkeypatch):
    if request.param == "numpy":
        monkeypatch.setattr(imaging, "cv2", None)
    elif imaging.cv2 is None:
        pytest.skip("OpenCV nicht installiert")
    return request.param


def test_find_template(tmp_path, backend):
    rng = np.random.default_rng(0)
    screen = rng.integers(0, 255, (400, 600, 3), dtype=np.uint8)
    button = screen[300:340, 50:150].copy()
    imaging.imwrite(tmp_path / "attack_button.png", button)

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


def test_numpy_ncc_matches_opencv():
    cv2 = pytest.importorskip("cv2")
    rng = np.random.default_rng(1)
    image = rng.integers(0, 255, (60, 80), dtype=np.uint8)
    templ = image[20:35, 30:50].copy()
    expected = cv2.matchTemplate(image, templ, cv2.TM_CCOEFF_NORMED)
    assert np.allclose(imaging._ncc_numpy(image, templ), expected, atol=1e-4)


def test_preprocess_digits_keeps_bright_pixels():
    img = np.zeros((10, 20, 3), np.uint8)
    img[2:8, 5:10] = 255
    out = preprocess_digits(img)
    assert out.shape == (30, 60)
    assert out[15, 20] == 0 and out[0, 0] == 255


def test_png_roundtrip(tmp_path):
    img = np.arange(4 * 5 * 3, dtype=np.uint8).reshape(4, 5, 3)
    imaging.imwrite(tmp_path / "x.png", img)
    assert np.array_equal(imaging.imread(tmp_path / "x.png"), img)
    data = (tmp_path / "x.png").read_bytes()
    assert np.array_equal(imaging.decode(data), img)
