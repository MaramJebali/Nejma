# AI-generated code: written with Claude (Anthropic) at the team's direction for NASA Space Apps 2026.
import base64
import json

import numpy as np

from spherex.gaia import GaiaStar
from spherex.process import Frame, target_grid
from spherex.resolve import Target
from spherex.spectrum import SpectrumPoint
from spherex.webdata import find_centroid, target_json, view_json, visit_brightness


def _star(shape, x, y, peak, noise=0.01, seed=0):
    rng = np.random.default_rng(seed)
    yy, xx = np.mgrid[0 : shape[0], 0 : shape[1]]
    return (peak * np.exp(-((xx - x) ** 2 + (yy - y) ** 2) / (2 * 1.2**2)) + rng.normal(0, noise, shape)).astype(np.float32)


def _frame(data, saturated=None, mjd=61000.0, detector=2):
    return Frame(detector=detector, mjd_start=mjd - 2, mjd_end=mjd + 2, mjd_mid=mjd, n_images=12, n_available=18,
                 data=data, wavelength_um=(1.1, 1.6), target_flags={"OVERFLOW": 3}, saturated=saturated)


def _point(mjd, flux, ring, saturated, detector=2):
    return SpectrumPoint(mjd=mjd, detector=detector, wavelength_um=1.3, bandwidth_um=0.03, flux_mjy=flux,
                         error_mjy=0.1, saturated=saturated, ring_mjy=ring)


def test_centroid_finds_a_star_off_the_expected_position():
    data = _star((61, 61), 31.4, 28.7, peak=5.0)
    x, y = find_centroid(data, 30.0, 30.0)
    assert abs(x - 31.4) < 0.3 and abs(y - 28.7) < 0.3


def test_centroid_is_refused_for_a_faint_source():
    assert find_centroid(_star((61, 61), 30.0, 30.0, peak=0.03), 30.0, 30.0) is None


def test_centroid_is_refused_for_a_saturated_star():
    data = _star((61, 61), 30.0, 30.0, peak=5.0)
    saturated = np.zeros(data.shape, dtype=bool)
    saturated[26:35, 26:35] = True
    assert find_centroid(data, 30.0, 30.0, saturated) is None


def test_visit_brightness_uses_the_aperture_when_the_star_is_not_saturated():
    frames = [_frame(np.zeros((5, 5), np.float32), mjd=61000.0), _frame(np.zeros((5, 5), np.float32), mjd=61200.0)]
    points = [_point(61000.0 + d, 10.0, 1.0, False) for d in (-1, 0, 1)] + [_point(61200.0 + d, 20.0, 2.0, False) for d in (-1, 0, 1)]
    first, second = visit_brightness(frames, points)
    assert first["kind"] == "aperture" and first["mjy"] == 10.0 and second["mjy"] == 20.0


def test_visit_brightness_falls_back_to_the_ring_for_a_saturated_star():
    frames = [_frame(np.zeros((5, 5), np.float32))]
    points = [_point(61000.0 + d, float("nan"), 7.0, True) for d in (-1, 0, 1)]
    assert visit_brightness(frames, points) == [{"kind": "ring", "mjy": 7.0, "spread": 0.0, "images": 3}]


def test_a_visit_with_too_few_measurements_has_no_brightness():
    frames = [_frame(np.zeros((5, 5), np.float32))]
    assert visit_brightness(frames, [_point(61000.0, 10.0, 1.0, False)]) == [None]


def test_view_json_is_valid_json_with_north_in_the_first_row():
    wcs, shape = target_grid(150.0, 20.0, 0.05)
    n = shape[0]
    data = np.zeros(shape, dtype=np.float32)
    data[n - 1, 3] = 9.0  # top row of the sky (north) in FITS order
    data[0, 0] = np.nan
    target = Target(label="Test", ra=150.0, dec=20.0)
    document = view_json(target, 2, [_frame(data)], wcs, {"built": "2026-11-15", "n_records": 5, "n_skipped": 0, "n_failures": 1}, [])
    json.dumps(document, allow_nan=False)  # NaN must not leak into the JSON text
    pixels = np.frombuffer(base64.b64decode(document["data"]), dtype="<f2").reshape(1, n, n)
    assert pixels[0, 0, 3] == 9.0 and np.isnan(pixels[0, n - 1, 0])
    frame = document["frames"][0]
    assert frame["marker"] == [(n - 1) / 2, (n - 1) / 2]  # the target sits on the central pixel
    assert frame["flags"] == {"OVERFLOW": 3} and document["sat"] is None and document["failures"] == 1


def test_view_json_carries_the_saturation_mask_flipped_like_the_pixels():
    wcs, shape = target_grid(150.0, 20.0, 0.05)
    n = shape[0]
    saturated = np.zeros(shape, dtype=bool)
    saturated[n - 1, 2] = True
    document = view_json(Target(label="Test", ra=150.0, dec=20.0), 2, [_frame(np.zeros(shape, np.float32), saturated)], wcs, {}, [])
    mask = np.frombuffer(base64.b64decode(document["sat"]), dtype=np.uint8).reshape(1, n, n)
    assert mask[0, 0, 2] == 1 and mask.sum() == 1


def test_target_json_turns_missing_values_into_null():
    target = Target(label="Test", ra=150.0, dec=20.0, pm_ra_cosdec=-800.0, pm_dec=10000.0, source="SIMBAD via CDS Sesame")
    stars = [GaiaStar(ra=150.01, dec=20.01, pm_ra_cosdec=1.0, pm_dec=-2.0, g_mag=15.5)]
    document = target_json(target, "test", 0.1, [_point(61000.0, float("nan"), 7.0, True)], stars)
    json.dumps(document, allow_nan=False)
    assert document["points"] == [[61000.0, 2, 1.3, None, 0.1, 1, 7.0]]
    assert document["gaia"]["stars"] == [[150.01, 20.01, 1.0, -2.0, 15.5]] and document["pm"] == [-800.0, 10000.0]
