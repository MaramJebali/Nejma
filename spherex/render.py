# AI-generated code: written with Claude (Anthropic) at the team's direction for NASA Space Apps 2026.
"""Turn stacked frames into images: brightness scaling, difference images, labels and GIFs."""
from __future__ import annotations

import io

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from scipy.ndimage import maximum_filter

BACKGROUND = 24  # grey level for pixels with no data
MARKER = (255, 170, 40)


def display_limits(arrays: list[np.ndarray], low_pct: float = 1.0, high_pct: float = 99.7) -> tuple[float, float]:
    """One brightness range shared by every frame, so changes between frames are real changes."""
    values = np.concatenate([a[np.isfinite(a)].ravel() for a in arrays]) if arrays else np.array([])
    if values.size == 0:
        return 0.0, 1.0
    low, high = np.percentile(values, [low_pct, high_pct])
    if high <= low:
        high = low + 1e-6
    return float(low), float(high)


def fill_small_holes(data: np.ndarray, passes: int = 3) -> np.ndarray:
    """Fill small gaps from their brightest neighbour, for display only.

    The cores of saturated stars have no value in any SPHEREx image, which would draw them as black dots.
    Large empty areas (outside the data) stay empty.
    """
    out = data.copy()
    for _ in range(passes):
        holes = ~np.isfinite(out)
        if not holes.any():
            break
        neighbour_max = maximum_filter(np.where(holes, -np.inf, out), size=3, mode="constant", cval=-np.inf)
        fillable = holes & np.isfinite(neighbour_max)
        out[fillable] = neighbour_max[fillable]
    out[~np.isfinite(data) & ~np.isfinite(out)] = np.nan
    return out


def to_gray(data: np.ndarray, low: float, high: float, softening: float = 8.0) -> np.ndarray:
    """asinh stretch: faint sources stay visible without saturating bright stars."""
    x = np.clip((data - low) / (high - low), 0.0, 1.0)
    y = np.arcsinh(softening * x) / np.arcsinh(softening)
    out = (np.nan_to_num(y) * 255).astype(np.uint8)
    out[~np.isfinite(data)] = BACKGROUND
    return out


def difference_frames(arrays: list[np.ndarray]) -> list[np.ndarray]:
    """Each frame minus the first. A moving object shows up as a dark and bright pair."""
    reference = arrays[0]
    return [a - reference for a in arrays]


def difference_limit(arrays: list[np.ndarray], pct: float = 99.5) -> float:
    values = np.concatenate([np.abs(a[np.isfinite(a)]).ravel() for a in arrays]) if arrays else np.array([])
    limit = float(np.percentile(values, pct)) if values.size else 1.0
    return limit if limit > 0 else 1.0


def to_diverging(data: np.ndarray, limit: float) -> np.ndarray:
    """Grey for no change, white where it got brighter, black where it got fainter."""
    out = (np.nan_to_num(np.clip(data / limit, -1.0, 1.0)) * 127.5 + 127.5).astype(np.uint8)
    out[~np.isfinite(data)] = 128
    return out


def _font(size: int):
    try:
        return ImageFont.load_default(size=size)
    except TypeError:  # Pillow < 10.1
        return ImageFont.load_default()


def compose(gray: np.ndarray, label: str, scale: int, marker: tuple[float, float] | None = None, marker_radius_px: float = 3.0) -> Image.Image:
    """Enlarge one frame (north up, east left), mark the expected target position and add a caption bar."""
    image = Image.fromarray(np.flipud(gray), mode="L").convert("RGB")  # FITS rows go up, image rows go down
    image = image.resize((image.width * scale, image.height * scale), Image.NEAREST)
    draw = ImageDraw.Draw(image)
    if marker is not None:
        # Two ticks, east (left) and north (top) of the position, like a finder chart: they stay visible
        # next to bright stars, where a circle would disappear in the glare.
        x, y = marker
        cx = (x + 0.5) * scale
        cy = (gray.shape[0] - 1 - y + 0.5) * scale
        inner, outer = marker_radius_px * scale, (marker_radius_px + 5) * scale
        width = max(2, scale // 2)
        draw.line([cx - outer, cy, cx - inner, cy], fill=MARKER, width=width)
        draw.line([cx, cy - outer, cx, cy - inner], fill=MARKER, width=width)
    bar = 26
    canvas = Image.new("RGB", (image.width, image.height + bar), (12, 14, 22))
    canvas.paste(image, (0, 0))
    ImageDraw.Draw(canvas).text((8, image.height + 5), label, fill=(235, 235, 235), font=_font(15))
    return canvas


def gif_bytes(images: list[Image.Image], frame_ms: int = 700) -> bytes:
    buffer = io.BytesIO()
    images[0].save(buffer, format="GIF", save_all=True, append_images=images[1:], duration=frame_ms, loop=0, optimize=False)
    return buffer.getvalue()


def png_bytes(image: Image.Image) -> bytes:
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def display_scale(n_pixels: int, target_px: int = 480) -> int:
    return max(1, round(target_px / n_pixels))
