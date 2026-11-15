# AI-generated code: written with Claude (Anthropic) at the team's direction for NASA Space Apps 2026.
"""Gaia DR3 stars around a position (from IRSA), moved to the date of each SPHEREx visit."""
from __future__ import annotations

import csv
import io
import json
from dataclasses import dataclass

import numpy as np

from .archive import TAP_URL, cache_dir, http_get
from .resolve import propagate

GAIA_EPOCH = 2016.0  # reference epoch of Gaia DR3 positions
FAST_MAS_PER_YR = 100.0  # proper motion above which a star is highlighted


@dataclass(frozen=True)
class GaiaStar:
    ra: float
    dec: float
    pm_ra_cosdec: float  # mas/yr, 0 when Gaia has no proper motion
    pm_dec: float
    g_mag: float

    @property
    def total_pm(self) -> float:
        return float(np.hypot(self.pm_ra_cosdec, self.pm_dec))

    @property
    def is_fast(self) -> bool:
        return self.total_pm >= FAST_MAS_PER_YR

    def position_at(self, year: float) -> tuple[float, float]:
        return propagate(self.ra, self.dec, self.pm_ra_cosdec, self.pm_dec, GAIA_EPOCH, year)


def _float(value: str, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def query_gaia(ra: float, dec: float, radius_deg: float, max_stars: int = 1500, *, timeout: float = 180, attempts: int = 4) -> list[GaiaStar]:
    """Brightest Gaia DR3 sources within radius_deg, cached on disk (the catalogue does not change)."""
    path = cache_dir() / "gaia" / f"{ra:.4f}_{dec:+.4f}_{radius_deg:.3f}.json"
    if path.exists():
        return [GaiaStar(**row) for row in json.loads(path.read_text())]
    adql = (
        f"SELECT TOP {max_stars} ra, dec, pmra, pmdec, phot_g_mean_mag FROM gaia_dr3_source "
        f"WHERE 1 = CONTAINS(POINT('ICRS', ra, dec), CIRCLE('ICRS', {ra:.6f}, {dec:.6f}, {radius_deg:.5f})) "
        "ORDER BY phot_g_mean_mag"
    )
    response = http_get(TAP_URL, params={"QUERY": adql, "FORMAT": "CSV"}, timeout=timeout, attempts=attempts)
    stars = [
        GaiaStar(
            ra=float(row["ra"]),
            dec=float(row["dec"]),
            pm_ra_cosdec=_float(row["pmra"]),
            pm_dec=_float(row["pmdec"]),
            g_mag=_float(row["phot_g_mean_mag"], 99.0),
        )
        for row in csv.DictReader(io.StringIO(response.text))
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps([s.__dict__ for s in stars]))
    return stars


def pixel_positions(stars: list[GaiaStar], wcs, year: float, shape: tuple[int, int]) -> list[tuple[float, float, bool]]:
    """(x, y, is_fast) of each star on the output grid at a given date, keeping only those inside the frame."""
    out = []
    for s in stars:
        x, y = wcs.world_to_pixel_values(*s.position_at(year))
        if 0 <= x < shape[1] and 0 <= y < shape[0]:
            out.append((float(x), float(y), s.is_fast))
    return out
