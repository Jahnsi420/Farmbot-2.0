"""Screen analysis: template matching and reading loot numbers."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from farmbot import imaging

log = logging.getLogger(__name__)

Rect = tuple[float, float, float, float]  # relative x1, y1, x2, y2 (0..1)

# Where each button can appear, with generous margins. Searching only there is much faster.
DEFAULT_REGIONS: dict[str, Rect] = {
    "attack_button": (0.0, 0.6, 0.3, 1.0),
    "find_match": (0.0, 0.5, 0.4, 0.95),
    "attack_confirm": (0.55, 0.7, 1.0, 1.0),
    "next_button": (0.65, 0.5, 1.0, 0.9),
    "end_battle": (0.0, 0.6, 0.3, 0.9),
    "surrender_confirm": (0.35, 0.4, 0.85, 0.85),
    "return_home": (0.25, 0.65, 0.75, 1.0),
}


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
                 reference_width: int | None = None, regions: dict[str, Rect] | None = None):
        self.directory = Path(directory)
        self.threshold = threshold
        # Screen width the templates were cut from; other resolutions get rescaled templates.
        self.reference_width = reference_width
        self.regions = DEFAULT_REGIONS if regions is None else regions
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

    def variants(self, name: str) -> list[str]:
        """A button can look different (e.g. "Aufgeben" / "Kampf beenden"): name.png plus name.*.png."""
        extra = sorted(p.name[:-4] for p in self.directory.glob(f"{name}.*.png"))
        return [name] + extra

    def find(self, screen: np.ndarray, name: str, region: Rect | None = None,
             threshold: float | None = None) -> Match | None:
        """Best match of the template (or any of its variants)."""
        region = region or self.regions.get(name)
        area, ox, oy = crop_rel(screen, region) if region else (screen, 0, 0)
        best: Match | None = None
        for variant in self.variants(name):
            template = self.for_screen(variant, screen.shape[1])
            th, tw = template.shape[:2]
            if area.shape[0] < th or area.shape[1] < tw:
                continue
            score, loc = imaging.match_template(area, template)
            log.debug("template %s score %.3f", variant, score)
            if best is None or score > best.score:
                best = Match(loc[0] + ox, loc[1] + oy, tw, th, float(score))
        if best is None or best.score < (threshold if threshold is not None else self.threshold):
            return None
        return best
