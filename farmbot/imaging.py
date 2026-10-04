"""Image I/O and template matching on RGB numpy arrays.

Only needs numpy and Pillow. OpenCV is used for matching when installed
because it is faster, but it is optional (it is hard to install on Termux).
"""

from __future__ import annotations

import io
from pathlib import Path

import numpy as np
from PIL import Image

try:
    import cv2
except ImportError:  # pragma: no cover - depends on the environment
    cv2 = None


def decode(data: bytes) -> np.ndarray:
    return np.asarray(Image.open(io.BytesIO(data)).convert("RGB"))


def imread(path: str | Path) -> np.ndarray | None:
    try:
        with Image.open(path) as img:
            return np.asarray(img.convert("RGB"))
    except (FileNotFoundError, OSError):
        return None


def imwrite(path: str | Path, img: np.ndarray) -> None:
    Image.fromarray(np.ascontiguousarray(img)).save(path)


def to_gray(img: np.ndarray) -> np.ndarray:
    if img.ndim == 2:
        return img
    return np.asarray(Image.fromarray(img).convert("L"))


def scale(img: np.ndarray, factor: float) -> np.ndarray:
    pil = Image.fromarray(img)
    size = (round(pil.width * factor), round(pil.height * factor))
    return np.asarray(pil.resize(size, Image.BICUBIC))


def _window_sum(a: np.ndarray, h: int, w: int) -> np.ndarray:
    ii = np.pad(a, ((1, 0), (1, 0))).cumsum(0).cumsum(1)
    return ii[h:, w:] - ii[:-h, w:] - ii[h:, :-w] + ii[:-h, :-w]


def _ncc_numpy(image: np.ndarray, templ: np.ndarray) -> np.ndarray:
    """Normalized cross-correlation, same as cv2.TM_CCOEFF_NORMED, via FFT."""
    image = image.astype(np.float64)
    templ = templ.astype(np.float64)
    th, tw = templ.shape
    ih, iw = image.shape
    t = templ - templ.mean()
    t_norm = np.sqrt((t * t).sum())

    shape = (ih + th - 1, iw + tw - 1)
    spectrum = np.fft.rfft2(image, shape) * np.fft.rfft2(t[::-1, ::-1], shape)
    corr = np.fft.irfft2(spectrum, shape)[th - 1:ih, tw - 1:iw]

    n = th * tw
    s1 = _window_sum(image, th, tw)
    s2 = _window_sum(image * image, th, tw)
    denom = np.sqrt(np.clip(s2 - s1 * s1 / n, 0, None)) * t_norm
    out = np.zeros_like(corr)
    np.divide(corr, denom, out=out, where=denom > 1e-6)
    return out


def match_template(image: np.ndarray, templ: np.ndarray) -> tuple[float, tuple[int, int]]:
    """Best match of `templ` in `image`: (score -1..1, (x, y) of the top-left corner)."""
    if cv2 is not None:
        result = cv2.matchTemplate(image, templ, cv2.TM_CCOEFF_NORMED)
        _, score, _, loc = cv2.minMaxLoc(result)
        return float(score), (int(loc[0]), int(loc[1]))
    # The numpy path is slow on phones: match at half resolution when the
    # template is big enough. A position off by a pixel doesn't matter for taps.
    factor = 0.5 if min(templ.shape[:2]) >= 24 else 1.0
    image, templ = to_gray(image), to_gray(templ)
    if factor != 1.0:
        image, templ = scale(image, factor), scale(templ, factor)
    result = _ncc_numpy(image, templ)
    y, x = np.unravel_index(int(np.argmax(result)), result.shape)
    return float(result[y, x]), (round(x / factor), round(y / factor))
