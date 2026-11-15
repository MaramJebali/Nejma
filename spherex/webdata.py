# AI-generated code: written with Claude (Anthropic) at the team's direction for NASA Space Apps 2026.
"""Plain JSON for the web viewer in docs/, so saved test targets and live queries look the same to it.

Two documents describe one look at the sky:
  target: who we are looking at (position, proper motion, Gaia stars around it, every spectrum point)
  view:   the stacked frames of one detector (pixels, dates, flags, where the target should be and was found)
"""
from __future__ import annotations

import base64
import math

import numpy as np
from astropy.wcs import WCS

from .gaia import GAIA_EPOCH, GaiaStar
from .process import GRID_ARCSEC, Frame
from .resolve import VIEW_EPOCH, Target, mjd_to_year
from .spectrum import SpectrumPoint

CENTROID_HALF_BOX = 4  # grid pixels either side of the expected position (12")
MIN_CENTROID_SNR = 8.0  # fainter than this, a centroid mostly reports where we looked
MAX_SATURATED_IN_BOX = 0.3  # more saturated than this and the centre of light is not the centre of the star


def _number(value: float, digits: int = 4) -> float | None:
    """Rounded float, or None for NaN and infinity (JSON has no NaN)."""
    value = float(value)
    return round(value, digits) if math.isfinite(value) else None


def _pack(array: np.ndarray) -> str:
    return base64.b64encode(np.ascontiguousarray(array).tobytes()).decode("ascii")


def find_centroid(data: np.ndarray, x: float, y: float, saturated: np.ndarray | None = None) -> tuple[float, float] | None:
    """Centre of light near (x, y) in array coordinates, or None when it cannot be trusted.

    It is not trusted when the source is faint (the answer would just be the middle of the search box) or when
    much of the box is saturated (a clipped star has no well-defined centre of light).
    """
    half = CENTROID_HALF_BOX
    xi, yi = int(round(x)), int(round(y))
    ny, nx = data.shape
    if not (half <= xi < nx - half and half <= yi < ny - half):
        return None
    window = (slice(yi - half, yi + half + 1), slice(xi - half, xi + half + 1))
    if saturated is not None and saturated[window].mean() > MAX_SATURATED_IN_BOX:
        return None
    box = data[window].astype(float)
    finite = data[np.isfinite(data)]
    if finite.size == 0 or not np.isfinite(box).any():
        return None
    noise = 1.4826 * float(np.median(np.abs(finite - np.median(finite))))
    box = np.where(np.isfinite(box), box, np.nanmax(box))  # an empty pixel inside a star is a clipped peak
    box = box - np.median(box)
    box[box < 0] = 0
    if box.sum() <= 0 or noise <= 0 or box.max() < MIN_CENTROID_SNR * noise:
        return None
    ys, xs = np.mgrid[-half : half + 1, -half : half + 1]
    return xi + float((box * xs).sum() / box.sum()), yi + float((box * ys).sum() / box.sum())


def visit_brightness(frames: list[Frame], points: list[SpectrumPoint]) -> list[dict | None]:
    """One brightness per visit: the median over that visit's images.

    Uses the usual aperture value unless most images are saturated; then it uses the ring outside the core,
    which only says how the brightness changed, not what it was.
    """
    # A broadband frame (detector 0) is made from every detector, so it uses every spectral point.
    band = [p for p in points if frames and (frames[0].detector == 0 or p.detector == frames[0].detector)]
    usable = [p for p in band if not p.saturated and math.isfinite(p.flux_mjy)]
    kind = "aperture" if band and len(usable) >= len(band) / 2 else "ring"
    out: list[dict | None] = []
    for f in frames:
        visit = [p for p in band if f.mjd_start - 1 <= p.mjd <= f.mjd_end + 1]
        if kind == "aperture":
            values = [p.flux_mjy for p in visit if not p.saturated and math.isfinite(p.flux_mjy)]
        else:
            values = [p.ring_mjy for p in visit if math.isfinite(p.ring_mjy)]
        if len(values) < 3:
            out.append(None)
            continue
        median = float(np.median(values))
        out.append({"kind": kind, "mjy": _number(median), "spread": _number(float(np.std(values)) / abs(median), 3) if median else None, "images": len(values)})
    return out


def view_json(target: Target, band: int, frames: list[Frame], wcs: WCS, info: dict, points: list[SpectrumPoint]) -> dict:
    """The frames of one detector. Rows are flipped so that row 0 is north, as an image is drawn."""
    n = frames[0].data.shape[0]
    brightness = visit_brightness(frames, points)
    described = []
    for f, visit in zip(frames, brightness):
        ra, dec = target.position_at(mjd_to_year(f.mjd_mid))
        x, y = (float(v) for v in wcs.world_to_pixel_values(ra, dec))
        found = find_centroid(f.data, x, y, f.saturated)
        described.append({
            "date": f.date,
            "mjd": round(f.mjd_mid, 3),
            "year": round(mjd_to_year(f.mjd_mid), 4),
            "days": round(f.span_days, 1),
            "images": f.n_images,
            "available": f.n_available,
            "wl": [round(f.wavelength_um[0], 3), round(f.wavelength_um[1], 3)],
            "flags": f.target_flags,
            "marker": [round(x, 2), round(n - 1 - y, 2)],
            "centroid": [round(found[0], 2), round(n - 1 - found[1], 2)] if found else None,
            "brightness": visit,
        })
    masks = [f.saturated for f in frames]
    has_mask = all(m is not None for m in masks) and any(m.any() for m in masks)
    return {
        "band": band,
        "n": n,
        "frames": described,
        "data": _pack(np.stack([f.data[::-1] for f in frames]).astype("<f2")),
        "sat": _pack(np.stack([m[::-1] for m in masks]).astype(np.uint8)) if has_mask else None,
        "built": info.get("built"),
        "records": info.get("n_records"),
        "failures": info.get("n_failures"),
        "skipped": info.get("n_skipped"),
    }


def target_json(target: Target, query: str, fov: float, points: list[SpectrumPoint], stars: list[GaiaStar]) -> dict:
    return {
        "label": target.label,
        "query": query,
        "ra": round(target.ra, 6),
        "dec": round(target.dec, 6),
        "pm": [round(target.pm_ra_cosdec, 2), round(target.pm_dec, 2)],
        "epoch": VIEW_EPOCH,
        "source": target.source,
        "fov": fov,
        "arcsec": GRID_ARCSEC,
        "gaia": {
            "epoch": GAIA_EPOCH,
            "stars": [[round(s.ra, 6), round(s.dec, 6), round(s.pm_ra_cosdec, 1), round(s.pm_dec, 1), round(s.g_mag, 2)] for s in stars],
        },
        "points": [
            [round(p.mjd, 3), p.detector, round(p.wavelength_um, 4), _number(p.flux_mjy), _number(p.error_mjy), int(p.saturated), _number(p.ring_mjy)]
            for p in points
        ],
    }
