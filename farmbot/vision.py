"""Screen analysis: template matching and reading loot numbers."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from farmbot import imaging

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
    def __init__(self, directory: str | Path, threshold: float = 0.85,
                 reference_width: int | None = None):
        self.directory = Path(directory)
        self.threshold = threshold
        # Screen width the templates were cut from; other resolutions get rescaled templates.
        self.reference_width = reference_width
        self._cache: dict[str, np.ndarray] = {}
        self._scaled: dict[tuple[str, int], np.ndarray] = {}

    def has(self, name: str) -> bool:
        return (self.directory / f"{name}.png").exists()

    def get(self, name: str) -> np.ndarray:
        if name not in self._cache:
            path = self.directory / f"{name}.png"
            img = imaging.imread(path)
            if img is None:
                raise FileNotFoundError(
                    f"Template '{name}' fehlt ({path}). Mit 'python -m farmbot capture {name}' aufnehmen."
                )
            self._cache[name] = img
        return self._cache[name]

    def for_screen(self, name: str, screen_width: int) -> np.ndarray:
        template = self.get(name)
        if not self.reference_width or screen_width == self.reference_width:
            return template
        key = (name, screen_width)
        if key not in self._scaled:
            self._scaled[key] = imaging.scale(template, screen_width / self.reference_width)
        return self._scaled[key]

    def find(self, screen: np.ndarray, name: str, region: Rect | None = None,
             threshold: float | None = None) -> Match | None:
        template = self.for_screen(name, screen.shape[1])
        area, ox, oy = crop_rel(screen, region) if region else (screen, 0, 0)
        th, tw = template.shape[:2]
        if area.shape[0] < th or area.shape[1] < tw:
            return None
        score, loc = imaging.match_template(area, template)
        log.debug("template %s score %.3f", name, score)
        if score < (threshold if threshold is not None else self.threshold):
            return None
        return Match(loc[0] + ox, loc[1] + oy, tw, th, float(score))
