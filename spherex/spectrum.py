# AI-generated code: written with Claude (Anthropic) at the team's direction for NASA Space Apps 2026.
"""Spectra on the fly: every SPHEREx image sees the target at its own wavelength, so measuring the target's
brightness in each image and plotting it against that wavelength gives a spectrum."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from astropy.wcs.utils import proj_plane_pixel_area

from .archive import Cutout
from .process import clean_image
from .resolve import Target, mjd_to_year

APERTURE_PX = 2.0  # native pixels (about 12")
ANNULUS_PX = (4.0, 7.0)
SATURATION_FLAGS = ("OVERFLOW",)


@dataclass(frozen=True)
class SpectrumPoint:
    mjd: float
    detector: int
    wavelength_um: float
    bandwidth_um: float
    flux_mjy: float
    error_mjy: float
    saturated: bool


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
    saturated_bits = sum(cutout.flag_bits.get(n, 0) for n in SATURATION_FLAGS)
    saturated = bool(np.any(cutout.flags[aperture] & saturated_bits)) or bool(np.any(~np.isfinite(values)))
    # MJy/sr per pixel -> mJy: multiply by the pixel solid angle (sr) and 1e9 mJy/MJy
    pixel_sr = proj_plane_pixel_area(cutout.wcs.celestial) * (np.pi / 180) ** 2
    to_mjy = pixel_sr * 1e9
    flux = float(np.nansum(values)) * to_mjy
    error = float(np.sqrt(np.nansum(cutout.variance[aperture]))) * to_mjy
    return SpectrumPoint(
        mjd=cutout.mjd,
        detector=cutout.detector,
        wavelength_um=cutout.wavelength_um,
        bandwidth_um=cutout.bandwidth_um,
        flux_mjy=flux,
        error_mjy=error,
        saturated=saturated,
    )


def measure_all(cutouts: list[Cutout], target: Target) -> list[SpectrumPoint]:
    """Measure the target in every cutout, following its proper motion to each image's date."""
    points = []
    for c in cutouts:
        ra, dec = target.position_at(mjd_to_year(c.mjd))
        point = measure(c, ra, dec)
        if point is not None:
            points.append(point)
    return sorted(points, key=lambda p: (p.mjd, p.wavelength_um))
