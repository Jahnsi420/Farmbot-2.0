"""Screen analysis: template matching and reading loot numbers."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

log = logging.getLogger(__name__)

Rect = tuple[float, float, float, float]  # relative x1, y1, x2, y2 (0..1)


@dataclass
class Match:
    x: int
    y: int
    w: int
    h: int
    score: float

    @property
    def center(self) -> tuple[int, int]:
        return self.x + self.w // 2, self.y + self.h // 2


def crop_rel(img: np.ndarray, rect: Rect) -> tuple[np.ndarray, int, int]:
    """Crop a relative rectangle; returns the crop and its pixel offset."""
    h, w = img.shape[:2]
    x1, y1 = int(rect[0] * w), int(rect[1] * h)
    x2, y2 = int(rect[2] * w), int(rect[3] * h)
    return img[y1:y2, x1:x2], x1, y1


class Templates:
    def __init__(self, directory: str | Path, threshold: float = 0.85):
        self.directory = Path(directory)
        self.threshold = threshold
        self._cache: dict[str, np.ndarray] = {}

    def has(self, name: str) -> bool:
        return (self.directory / f"{name}.png").exists()

    def get(self, name: str) -> np.ndarray:
        if name not in self._cache:
            path = self.directory / f"{name}.png"
            img = cv2.imread(str(path), cv2.IMREAD_COLOR)
            if img is None:
                raise FileNotFoundError(
                    f"Template '{name}' fehlt ({path}). Mit 'python -m farmbot capture {name}' aufnehmen."
                )
            self._cache[name] = img
        return self._cache[name]

    def find(self, screen: np.ndarray, name: str, region: Rect | None = None,
             threshold: float | None = None) -> Match | None:
        template = self.get(name)
        area, ox, oy = crop_rel(screen, region) if region else (screen, 0, 0)
        th, tw = template.shape[:2]
        if area.shape[0] < th or area.shape[1] < tw:
            return None
        result = cv2.matchTemplate(area, template, cv2.TM_CCOEFF_NORMED)
        _, score, _, loc = cv2.minMaxLoc(result)
        log.debug("template %s score %.3f", name, score)
        if score < (threshold if threshold is not None else self.threshold):
            return None
        return Match(loc[0] + ox, loc[1] + oy, tw, th, float(score))


def parse_number(text: str) -> int | None:
    digits = re.sub(r"\D", "", text)
    return int(digits) if digits else None


def preprocess_digits(img: np.ndarray) -> np.ndarray:
    """Loot numbers are white with a dark outline: keep only bright pixels."""
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if img.ndim == 3 else img
    gray = cv2.resize(gray, None, fx=3, fy=3, interpolation=cv2.INTER_CUBIC)
    _, mask = cv2.threshold(gray, 200, 255, cv2.THRESH_BINARY)
    return cv2.bitwise_not(mask)  # black digits on white for tesseract


def read_number(img: np.ndarray) -> int | None:
    import pytesseract

    processed = preprocess_digits(img)
    text = pytesseract.image_to_string(
        processed, config="--psm 7 -c tessedit_char_whitelist=0123456789"
    )
    return parse_number(text)
