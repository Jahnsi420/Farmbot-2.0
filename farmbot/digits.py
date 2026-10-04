"""Read the game's numbers by comparing single digits with learned glyphs.

Tesseract misreads the Clash of Clans font (drops digits, confuses 9 and 5),
so each digit is cut out and matched against reference glyphs that were
learned from real screenshots (see `learn`).
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter

from farmbot import imaging

TEMPLATE_DIR = Path(__file__).parent / "digit_templates"
GLYPH_SIZE = 24  # glyphs are normalized to 24x24
MAX_DISTANCE = 0.25  # mean pixel difference above which a blob is not a digit

_templates: dict[str, np.ndarray] | None = None


def digit_mask(img: np.ndarray) -> np.ndarray:
    """Numbers are white-ish with a dark outline: keep only bright, unsaturated pixels."""
    big = imaging.scale(img, 3)
    if big.ndim == 3:
        mask = (big.min(axis=2) > 170) & (imaging.to_gray(big) > 200)
    else:
        mask = big > 200
    # remove speckles from grass and debris
    mask = np.asarray(Image.fromarray(mask.astype(np.uint8) * 255).filter(ImageFilter.MedianFilter(5))) > 0
    return _trim_after_gap(mask, max_gap=mask.shape[0] // 2)


def _trim_after_gap(mask: np.ndarray, max_gap: int) -> np.ndarray:
    """Keep the leftmost run of ink; drop everything after a gap wider than max_gap."""
    cols = np.flatnonzero(mask.any(axis=0))
    if cols.size == 0:
        return mask
    end = cols[0]
    for c in cols[1:]:
        if c - end > max_gap:
            break
        end = c
    out = mask.copy()
    out[:, end + 1:] = False
    return out


def _crop_rows(glyph: np.ndarray) -> np.ndarray:
    rows = np.flatnonzero(glyph.any(axis=1))
    return glyph[rows[0]:rows[-1] + 1] if rows.size else glyph


def _split_wide(glyph: np.ndarray) -> list[np.ndarray]:
    """Split blobs of touching digits at the column with the least ink."""
    h, w = glyph.shape
    if w <= 1.05 * h:
        return [glyph]
    ink = glyph.sum(axis=0)
    lo, hi = int(w * 0.3), int(w * 0.7)
    cut = lo + int(np.argmin(ink[lo:hi]))
    return _split_wide(_crop_rows(glyph[:, :cut])) + _split_wide(_crop_rows(glyph[:, cut + 1:]))


def _text_band(mask: np.ndarray) -> np.ndarray:
    """Restrict to the longest run of rows with substantial ink (drops specks touching digits)."""
    ink = mask.sum(axis=1)
    if not ink.any():
        return mask
    rows = ink > 0.15 * ink.max()
    best, start = (0, 0), None
    for y, on in enumerate(np.append(rows, False)):
        if on and start is None:
            start = y
        elif not on and start is not None:
            if y - start > best[1] - best[0]:
                best = (start, y)
            start = None
    return mask[best[0]:best[1]]


def segment(mask: np.ndarray) -> list[np.ndarray]:
    """Cut a digit mask into single glyphs, left to right."""
    mask = _text_band(mask)
    cols = mask.any(axis=0)
    runs, start = [], None
    for x, filled in enumerate(cols):
        if filled and start is None:
            start = x
        elif not filled and start is not None:
            runs.append((start, x))
            start = None
    if start is not None:
        runs.append((start, len(cols)))

    blobs = [_crop_rows(mask[:, a:b]) for a, b in runs]
    if not blobs:
        return []
    tallest = max(b.shape[0] for b in blobs)
    glyphs = []
    for blob in blobs:
        if blob.shape[0] >= 0.6 * tallest:  # skip specks and the thin separators
            glyphs += [g for g in _split_wide(blob) if g.size]
    return glyphs


def normalize(glyph: np.ndarray) -> np.ndarray:
    """Scale to GLYPH_SIZE height keeping the aspect ratio, centered on a square canvas."""
    h, w = glyph.shape
    new_w = max(1, min(GLYPH_SIZE, round(w * GLYPH_SIZE / h)))
    pil = Image.fromarray(glyph.astype(np.uint8) * 255).resize((new_w, GLYPH_SIZE), Image.BILINEAR)
    canvas = np.zeros((GLYPH_SIZE, GLYPH_SIZE), np.float32)
    x = (GLYPH_SIZE - new_w) // 2
    canvas[:, x:x + new_w] = np.asarray(pil, np.float32) / 255
    return canvas


def load_templates(directory: Path = TEMPLATE_DIR) -> dict[str, np.ndarray]:
    templates = {}
    for d in "0123456789":
        img = imaging.imread(directory / f"{d}.png")
        if img is not None:
            templates[d] = imaging.to_gray(img).astype(np.float32) / 255
    return templates


def classify(glyph: np.ndarray, templates: dict[str, np.ndarray]) -> tuple[str, float]:
    g = normalize(glyph)
    best = min(templates, key=lambda d: np.abs(templates[d] - g).mean())
    return best, float(np.abs(templates[best] - g).mean())


def read_number(img: np.ndarray, templates: dict[str, np.ndarray] | None = None) -> int | None:
    global _templates
    if templates is None:
        if _templates is None:
            _templates = load_templates()
        templates = _templates
    if not templates:
        raise FileNotFoundError(f"Keine Ziffern-Vorlagen in {TEMPLATE_DIR}")
    digits = ""
    for glyph in segment(digit_mask(img)):
        d, dist = classify(glyph, templates)
        if dist <= MAX_DISTANCE:
            digits += d
    return int(digits) if digits else None


def learn(samples: list[tuple[np.ndarray, str]]) -> dict[str, np.ndarray]:
    """Average glyphs per digit from (image of a number, its true value) samples."""
    collected: dict[str, list[np.ndarray]] = {d: [] for d in "0123456789"}
    for img, value in samples:
        glyphs = segment(digit_mask(img))
        expected = value.replace(" ", "")
        if len(glyphs) != len(expected):
            raise ValueError(f"'{value}': {len(glyphs)} Zeichen gefunden, {len(expected)} erwartet")
        for glyph, d in zip(glyphs, expected):
            collected[d].append(normalize(glyph))
    return {d: np.mean(g, axis=0) for d, g in collected.items() if g}


def save_templates(templates: dict[str, np.ndarray], directory: Path = TEMPLATE_DIR) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    for d, t in templates.items():
        imaging.imwrite(directory / f"{d}.png", (t * 255).round().astype(np.uint8))
