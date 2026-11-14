# AI-generated code: written with Claude (Anthropic) at the team's direction for NASA Space Apps 2026.
import numpy as np
import pytest
from astropy.io import fits

from spherex.archive import Cutout
from spherex.spectrum import measure


def _cutout(star_flux_mjysr: float, saturate: bool = False) -> Cutout:
    n = 41
    header = fits.Header()
    header.update({
        "NAXIS": 2, "NAXIS1": n, "NAXIS2": n, "CTYPE1": "RA---TAN", "CTYPE2": "DEC--TAN",
        "CRVAL1": 150.0, "CRVAL2": 20.0, "CRPIX1": 21.0, "CRPIX2": 21.0,
        "CDELT1": -6.0 / 3600, "CDELT2": 6.0 / 3600,
    })
    yy, xx = np.mgrid[0:n, 0:n]
    image = np.full((n, n), 2.0, dtype=np.float32)  # flat background
    image[20, 20] += star_flux_mjysr  # star in one pixel at the centre
    flags = np.zeros((n, n), dtype=np.int32)
    if saturate:
        flags[20, 20] = 2
    return Cutout(
        uri="u", detector=2, mjd=61000.0, image=image, zodi=np.zeros_like(image),
        variance=np.full((n, n), 0.01, dtype=np.float32), flags=flags, header=header,
        flag_bits={"OVERFLOW": 2, "HOT": 1024}, wavelength_um=1.3, bandwidth_um=0.03,
    )


def test_flux_matches_pixel_value_times_solid_angle():
    point = measure(_cutout(100.0), 150.0, 20.0)
    pixel_sr = (6.0 / 3600 * np.pi / 180) ** 2
    assert point.flux_mjy == pytest.approx(100.0 * pixel_sr * 1e9, rel=0.02)
    assert point.wavelength_um == 1.3 and not point.saturated


def test_background_is_removed():
    point = measure(_cutout(0.0), 150.0, 20.0)
    assert point.flux_mjy == pytest.approx(0.0, abs=1e-6)


def test_saturation_is_reported():
    assert measure(_cutout(100.0, saturate=True), 150.0, 20.0).saturated


def test_empty_centre_gives_no_value_instead_of_zero():
    cutout = _cutout(100.0, saturate=True)
    cutout.image[18:23, 18:23] = np.nan  # the core of a saturated star has no value at all
    point = measure(cutout, 150.0, 20.0)
    assert np.isnan(point.flux_mjy) and point.saturated


def test_ring_measures_light_outside_the_core():
    cutout = _cutout(0.0)
    yy, xx = np.mgrid[0:41, 0:41]
    r = np.hypot(xx - 20, yy - 20)
    ring = (r >= 2.5) & (r <= 4.5)
    cutout.image[ring] += 5.0
    point = measure(cutout, 150.0, 20.0)
    pixel_sr = (6.0 / 3600 * np.pi / 180) ** 2
    assert point.ring_mjy == pytest.approx(5.0 * ring.sum() * pixel_sr * 1e9, rel=0.02)


def test_off_image_returns_none():
    assert measure(_cutout(100.0), 151.0, 20.0) is None
