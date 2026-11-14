# AI-generated code: written with Claude (Anthropic) at the team's direction for NASA Space Apps 2026.
import numpy as np
import pytest
from astropy.wcs import WCS

from spherex.archive import Cutout, ImageRecord
from spherex.process import flag_mask, group_visits, plan_visits, saturated_pixels, target_grid, thin, to_grid


def test_saturated_pixels_include_the_empty_core():
    image = np.ones((9, 9), dtype=np.float32)
    image[4, 4] = np.nan  # empty centre of a saturated star
    image[0, 0] = np.nan  # an unrelated empty pixel
    flags = np.zeros((9, 9), dtype=np.int32)
    flags[3:6, 3:6] = 2
    flags[4, 4] = 0  # the empty centre itself carries no flag
    cutout = Cutout(uri="u", detector=2, mjd=61000.0, image=image, zodi=np.zeros_like(image),
                    variance=np.ones_like(image), flags=flags, header={}, flag_bits={"OVERFLOW": 2},
                    wavelength_um=1.3, bandwidth_um=0.03)
    mask = saturated_pixels(cutout)
    assert mask[4, 4] and mask[3, 3] and not mask[0, 0] and mask.sum() == 9


def test_group_visits_splits_on_gaps():
    mjds = [100, 101, 105, 300, 302, 600]
    assert group_visits(mjds) == [[0, 1, 2], [3, 4], [5]]


def test_group_visits_sorts_input():
    assert group_visits([300, 100, 101]) == [[1, 2], [0]]


def test_long_coverage_is_binned():
    mjds = np.arange(0, 90, 1.0)  # observed every day for 90 days
    visits = group_visits(mjds)
    assert len(visits) == 3
    for v in visits:
        span = mjds[v[-1]] - mjds[v[0]]
        assert span <= 30
    assert sorted(i for v in visits for i in v) == list(range(90))


def test_thin_keeps_ends_and_count():
    items = list(range(20))
    kept = thin(items, 5)
    assert len(kept) == 5 and kept[0] == 0 and kept[-1] == 19
    assert thin(items[:3], 5) == [0, 1, 2]


def test_plan_visits_skips_small_visits():
    records = [ImageRecord(uri=f"u{i}", detector=2, mjd=m) for i, m in enumerate([10, 11, 12, 13, 200, 201])]
    visits, skipped = plan_visits(records, max_per_visit=3, min_per_visit=3)
    assert [len(v.records) for v in visits] == [3]
    assert visits[0].n_available == 4
    assert [v.n_available for v in skipped] == [2]


def test_flag_mask_uses_named_bits():
    flags = np.array([[0, 1, 2, 3, 2097152]])
    bits = {"TRANSIENT": 1, "OVERFLOW": 2, "SOURCE": 2097152}
    assert flag_mask(flags, bits, ["TRANSIENT"]).tolist() == [[False, True, False, True, False]]
    assert flag_mask(flags, bits, ["MISSING_NAME"]).tolist() == [[False] * 5]


def test_target_grid_is_odd_and_centred():
    wcs, shape = target_grid(150.0, 20.0, 0.1)
    assert shape[0] % 2 == 1 and shape[0] == shape[1]
    x, y = wcs.world_to_pixel_values(150.0, 20.0)
    assert x == pytest.approx((shape[1] - 1) / 2)
    assert y == pytest.approx((shape[0] - 1) / 2)


def _star(shape, x0, y0, sigma=1.2):
    yy, xx = np.mgrid[0:shape[0], 0:shape[1]]
    return np.exp(-((xx - x0) ** 2 + (yy - y0) ** 2) / (2 * sigma ** 2)).astype(np.float32)


def _centroid(img):
    yy, xx = np.mgrid[0:img.shape[0], 0:img.shape[1]]
    w = np.clip(np.nan_to_num(img), 0, None)
    return (w * xx).sum() / w.sum(), (w * yy).sum() / w.sum()


def test_reprojection_keeps_star_position():
    """A star placed at a known sky position in a rotated 6" image lands at that position on the 3" grid."""
    ra0, dec0 = 150.0, 20.0
    src = WCS(naxis=2)
    src.wcs.ctype = ["RA---TAN", "DEC--TAN"]
    src.wcs.crval = [ra0, dec0]
    src.wcs.crpix = [30.5, 30.5]
    angle = np.radians(37.0)
    scale = 6.1 / 3600
    src.wcs.cd = scale * np.array([[-np.cos(angle), np.sin(angle)], [np.sin(angle), np.cos(angle)]])
    star_ra, star_dec = ra0 + 20 / 3600 / np.cos(np.radians(dec0)), dec0 - 15 / 3600
    sx, sy = src.world_to_pixel_values(star_ra, star_dec)
    image = _star((60, 60), sx, sy)

    out_wcs, shape = target_grid(ra0, dec0, 0.05)
    out = to_grid(image, src, out_wcs, shape)
    ex, ey = out_wcs.world_to_pixel_values(star_ra, star_dec)
    cx, cy = _centroid(out)
    assert cx == pytest.approx(ex, abs=0.3)
    assert cy == pytest.approx(ey, abs=0.3)


def test_shift_between_epochs_is_recovered():
    """Two images of a star that moved 6" north: the measured shift on the output grid is 2 pixels."""
    ra0, dec0 = 150.0, 20.0
    src = WCS(naxis=2)
    src.wcs.ctype = ["RA---TAN", "DEC--TAN"]
    src.wcs.crval = [ra0, dec0]
    src.wcs.crpix = [30.5, 30.5]
    src.wcs.cdelt = [-6.1 / 3600, 6.1 / 3600]
    out_wcs, shape = target_grid(ra0, dec0, 0.05)
    positions = [(ra0, dec0), (ra0, dec0 + 6 / 3600)]
    centroids = []
    for ra, dec in positions:
        sx, sy = src.world_to_pixel_values(ra, dec)
        centroids.append(_centroid(to_grid(_star((60, 60), sx, sy), src, out_wcs, shape)))
    assert centroids[1][1] - centroids[0][1] == pytest.approx(2.0, abs=0.15)
    assert centroids[1][0] - centroids[0][0] == pytest.approx(0.0, abs=0.15)
