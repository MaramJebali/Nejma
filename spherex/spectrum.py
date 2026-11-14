# AI-generated code: written with Claude (Anthropic) at the team's direction for NASA Space Apps 2026.
"""Spectra on the fly: every SPHEREx image sees the target at its own wavelength, so measuring the target's
brightness in each image and plotting it against that wavelength gives a spectrum."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from astropy.wcs.utils import proj_plane_pixel_area

from .archive import Cutout
from .process import SATURATION_FLAGS, clean_image, saturated_pixels  # noqa: F401  (SATURATION_FLAGS is re-exported)
from .resolve import Target, mjd_to_year

APERTURE_PX = 2.0  # native pixels (about 12")
ANNULUS_PX = (4.0, 7.0)
MIN_APERTURE_COVERAGE = 0.8  # below this the centre is mostly empty (saturated) and no brightness is reported

# For stars too bright to measure at the centre: the light in a ring outside the saturated core rises and falls
# with the star, so it shows changes between visits. Checked on Barnard's Star (which is steady): the ring value
# still wanders by roughly 20% from visit to visit, so only larger changes mean anything.
RING_PX = (2.5, 4.5)
RING_BACKGROUND_PX = (12.0, 16.0)
MIN_RING_COVERAGE = 0.7


@dataclass(frozen=True)
class SpectrumPoint:
    mjd: float
    detector: int
    wavelength_um: float
    bandwidth_um: float
    flux_mjy: float  # NaN when the centre of the star could not be measured
    error_mjy: float
    saturated: bool
    ring_mjy: float = float("nan")  # brightness in the ring outside the core: a relative measure only


def measure(cutout: Cutout, ra: float, dec: float) -> SpectrumPoint | None:
    """Aperture photometry at (ra, dec) in one cutout, in mJy. None when the position is off the image."""
    x, y = cutout.wcs.world_to_pixel_values(ra, dec)
    x, y = float(x), float(y)
    ny, nx = cutout.image.shape
    if not (ANNULUS_PX[1] <= x < nx - ANNULUS_PX[1] and ANNULUS_PX[1] <= y < ny - ANNULUS_PX[1]):
        return None
    data = clean_image(cutout)
    yy, xx = np.mgrid[0:ny, 0:nx]
    r = np.hypot(xx - x, yy - y)
    aperture = r <= APERTURE_PX
    annulus = (r >= ANNULUS_PX[0]) & (r <= ANNULUS_PX[1]) & np.isfinite(data)
    background = float(np.nanmedian(data[annulus])) if annulus.any() else 0.0
    values = data[aperture] - background
    overflow = saturated_pixels(cutout)
    saturated = bool(overflow[aperture].any()) or bool(np.any(~np.isfinite(values)))
    # MJy/sr per pixel -> mJy: multiply by the pixel solid angle (sr) and 1e9 mJy/MJy
    pixel_sr = proj_plane_pixel_area(cutout.wcs.celestial) * (np.pi / 180) ** 2
    to_mjy = pixel_sr * 1e9
    if np.isfinite(values).mean() >= MIN_APERTURE_COVERAGE:
        flux = float(np.nansum(values)) * to_mjy
        error = float(np.sqrt(np.nansum(cutout.variance[aperture]))) * to_mjy
    else:  # the centre is empty: an empty sum would read as "0 mJy", which is wrong
        flux = error = float("nan")
    return SpectrumPoint(
        mjd=cutout.mjd,
        detector=cutout.detector,
        wavelength_um=cutout.wavelength_um,
        bandwidth_um=cutout.bandwidth_um,
        flux_mjy=flux,
        error_mjy=error,
        saturated=saturated,
        ring_mjy=_ring_brightness(data, r, overflow, to_mjy),
    )


def _ring_brightness(data: np.ndarray, r: np.ndarray, overflow: np.ndarray, to_mjy: float) -> float:
    """Light in the ring outside the core, in mJy, or NaN when too little of the ring can be used."""
    ring = (r >= RING_PX[0]) & (r <= RING_PX[1])
    good = ring & ~overflow & np.isfinite(data)
    far = (r >= RING_BACKGROUND_PX[0]) & (r <= RING_BACKGROUND_PX[1]) & np.isfinite(data)
    if good.sum() < MIN_RING_COVERAGE * ring.sum() or far.sum() < 20:
        return float("nan")
    return (float(np.mean(data[good])) - float(np.median(data[far]))) * int(ring.sum()) * to_mjy


def measure_all(cutouts: list[Cutout], target: Target) -> list[SpectrumPoint]:
    """Measure the target in every cutout, following its proper motion to each image's date."""
    points = []
    for c in cutouts:
        ra, dec = target.position_at(mjd_to_year(c.mjd))
        point = measure(c, ra, dec)
        if point is not None:
            points.append(point)
    return sorted(points, key=lambda p: (p.mjd, p.wavelength_um))
