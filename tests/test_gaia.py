# AI-generated code: written with Claude (Anthropic) at the team's direction for NASA Space Apps 2026.
import pytest

from spherex.gaia import GaiaStar, pixel_positions
from spherex.process import target_grid


def test_fast_star_moves_on_grid():
    wcs, shape = target_grid(150.0, 20.0, 0.05)
    star = GaiaStar(ra=150.0, dec=20.0, pm_ra_cosdec=0.0, pm_dec=3000.0, g_mag=10.0)  # 3"/yr north = 1 px/yr
    (x0, y0, fast), = pixel_positions([star], wcs, 2016.0, shape)
    (x1, y1, _), = pixel_positions([star], wcs, 2026.0, shape)
    assert fast
    assert y1 - y0 == pytest.approx(10.0, abs=0.01)
    assert x1 == pytest.approx(x0, abs=0.01)


def test_stars_outside_frame_are_dropped():
    wcs, shape = target_grid(150.0, 20.0, 0.05)
    far = GaiaStar(ra=151.0, dec=20.0, pm_ra_cosdec=0.0, pm_dec=0.0, g_mag=10.0)
    assert pixel_positions([far], wcs, 2026.0, shape) == []
