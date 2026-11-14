# AI-generated code: written with Claude (Anthropic) at the team's direction for NASA Space Apps 2026.
"""Group SPHEREx images into visits, clean them, put them on one grid and stack each visit."""
from __future__ import annotations

import warnings
from dataclasses import dataclass, field

import numpy as np
from astropy.stats import sigma_clipped_stats
from astropy.time import Time
from astropy.wcs import WCS
from reproject import reproject_interp

from .archive import Cutout, ImageRecord

# Only broken pixels are left out of the stacks. Short-lived artefacts (cosmic rays, streaks) are rejected by
# the median over a visit instead: on bright stars SPHEREx also sets TRANSIENT and SUR_ERROR around the core,
# and masking those punched a hole in exactly the stars people look at (checked on Barnard's Star).
EXCLUDE_FLAGS = ("NONFUNC", "MISSING_DATA", "HOT", "COLD")

# Flags that are set on most pixels for bookkeeping and say nothing about contamination.
QUIET_FLAGS = ("SOURCE", "FULLSAMPLE")

GRID_ARCSEC = 3.0  # output pixel size, about half the native 6.1" pixel


def group_visits(mjds, gap_days: float = 20.0, max_span_days: float = 60.0, bin_days: float = 30.0) -> list[list[int]]:
    """Split observation times into visits.

    A gap longer than `gap_days` starts a new visit. A visit longer than `max_span_days` (a part of the sky
    that SPHEREx watches almost continuously) is cut into equal bins no longer than `bin_days`.
    Returns lists of indices into `mjds`, in time order.
    """
    mjds = np.asarray(mjds, dtype=float)
    groups: list[list[int]] = []
    for i in np.argsort(mjds, kind="stable"):
        if groups and mjds[i] - mjds[groups[-1][-1]] <= gap_days:
            groups[-1].append(int(i))
        else:
            groups.append([int(i)])
    visits: list[list[int]] = []
    for group in groups:
        start, span = mjds[group[0]], mjds[group[-1]] - mjds[group[0]]
        if span <= max_span_days:
            visits.append(group)
            continue
        n_bins = int(np.ceil(span / bin_days))
        width = span / n_bins
        bins: list[list[int]] = [[] for _ in range(n_bins)]
        for i in group:
            bins[min(int((mjds[i] - start) / width), n_bins - 1)].append(i)
        visits.extend(b for b in bins if b)
    return visits


def thin(items: list, max_n: int) -> list:
    """Keep at most max_n items, spread evenly over the list."""
    if len(items) <= max_n:
        return list(items)
    keep = np.unique(np.linspace(0, len(items) - 1, max_n).round().astype(int))
    return [items[i] for i in keep]


@dataclass
class VisitPlan:
    records: list[ImageRecord]  # images to download for this visit
    n_available: int


def plan_visits(records: list[ImageRecord], max_per_visit: int = 12, min_per_visit: int = 3) -> tuple[list[VisitPlan], list[VisitPlan]]:
    """Decide which images to use. Returns (visits to show, visits skipped for having too few images)."""
    visits, skipped = [], []
    for idx in group_visits([r.mjd for r in records]):
        group = [records[i] for i in idx]
        plan = VisitPlan(records=thin(group, max_per_visit), n_available=len(group))
        (visits if len(group) >= min_per_visit else skipped).append(plan)
    return visits, skipped


def flag_mask(flags: np.ndarray, flag_bits: dict[str, int], names) -> np.ndarray:
    value = 0
    for name in names:
        value |= flag_bits.get(name, 0)
    return (flags & value) != 0


def clean_image(cutout: Cutout, exclude=EXCLUDE_FLAGS) -> np.ndarray:
    """Remove zodiacal light and the remaining background, and blank out unusable pixels."""
    data = cutout.image - cutout.zodi
    bad = flag_mask(cutout.flags, cutout.flag_bits, exclude) | ~np.isfinite(data)
    data = np.where(bad, np.nan, data)
    good = data[np.isfinite(data)]
    if good.size:
        _, median, _ = sigma_clipped_stats(good, sigma=3.0, maxiters=5)
        data = data - median
    return data.astype(np.float32)


def target_grid(ra: float, dec: float, fov_deg: float, pixel_arcsec: float = GRID_ARCSEC) -> tuple[WCS, tuple[int, int]]:
    """A north-up, east-left grid centred on the target. The size is odd so the target sits on a pixel centre."""
    n = int(np.ceil(fov_deg * 3600 / pixel_arcsec)) | 1
    wcs = WCS(naxis=2)
    wcs.wcs.ctype = ["RA---TAN", "DEC--TAN"]
    wcs.wcs.crval = [ra, dec]
    wcs.wcs.cdelt = [-pixel_arcsec / 3600, pixel_arcsec / 3600]
    wcs.wcs.crpix = [(n + 1) / 2, (n + 1) / 2]
    return wcs, (n, n)


def to_grid(data: np.ndarray, wcs_in: WCS, wcs_out: WCS, shape: tuple[int, int]) -> np.ndarray:
    out, _ = reproject_interp((data, wcs_in), wcs_out, shape_out=shape, order="bilinear")
    return out.astype(np.float32)


def flags_near(cutout: Cutout, ra: float, dec: float, radius_px: int = 1) -> set[str]:
    """Names of the flags set within a few pixels of (ra, dec) in one image."""
    x, y = cutout.wcs.world_to_pixel_values(ra, dec)
    xi, yi = int(round(float(x))), int(round(float(y)))
    ny, nx = cutout.flags.shape
    if not (0 <= xi < nx and 0 <= yi < ny):
        return set()
    box = cutout.flags[max(yi - radius_px, 0): yi + radius_px + 1, max(xi - radius_px, 0): xi + radius_px + 1]
    value = int(np.bitwise_or.reduce(box, axis=None))
    return {name for name, bit in cutout.flag_bits.items() if value & bit and name not in QUIET_FLAGS}


@dataclass
class Frame:
    """One visit, stacked."""

    detector: int
    mjd_start: float
    mjd_end: float
    mjd_mid: float
    n_images: int
    n_available: int
    data: np.ndarray
    wavelength_um: tuple[float, float]
    target_flags: dict[str, int] = field(default_factory=dict)  # flag name -> number of images with it near the target
    flag_fractions: dict[str, float] = field(default_factory=dict)  # flag name -> mean fraction of pixels

    @property
    def date(self) -> str:
        return Time(self.mjd_mid, format="mjd").to_value("iso", subfmt="date")

    @property
    def span_days(self) -> float:
        return self.mjd_end - self.mjd_start


def stack_visit(cutouts: list[Cutout], wcs_out: WCS, shape: tuple[int, int], ra: float, dec: float, n_available: int) -> Frame:
    planes = [to_grid(clean_image(c), c.wcs, wcs_out, shape) for c in cutouts]
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)  # all-NaN pixels at the edges
        data = np.nanmedian(np.stack(planes), axis=0)
    target_flags: dict[str, int] = {}
    fractions: dict[str, float] = {}
    for c in cutouts:
        for name in flags_near(c, ra, dec):
            target_flags[name] = target_flags.get(name, 0) + 1
        for name, bit in c.flag_bits.items():
            if name not in QUIET_FLAGS:
                fractions[name] = fractions.get(name, 0.0) + float(np.mean((c.flags & bit) != 0)) / len(cutouts)
    mjds = [c.mjd for c in cutouts]
    waves = [c.wavelength_um for c in cutouts]
    return Frame(
        detector=cutouts[0].detector,
        mjd_start=min(mjds),
        mjd_end=max(mjds),
        mjd_mid=float(np.median(mjds)),
        n_images=len(cutouts),
        n_available=n_available,
        data=data,
        wavelength_um=(min(waves), max(waves)),
        target_flags=dict(sorted(target_flags.items(), key=lambda kv: -kv[1])),
        flag_fractions={k: v for k, v in sorted(fractions.items(), key=lambda kv: -kv[1]) if v > 0},
    )


def build_frames(visits: list[VisitPlan], cutouts: list[Cutout], ra: float, dec: float, fov_deg: float, min_per_visit: int = 3) -> tuple[list[Frame], WCS]:
    """Stack the downloaded cutouts visit by visit on a common grid."""
    wcs_out, shape = target_grid(ra, dec, fov_deg)
    by_uri = {c.uri: c for c in cutouts}
    frames = []
    for visit in visits:
        members = [by_uri[r.uri] for r in visit.records if r.uri in by_uri]
        if len(members) >= min_per_visit:
            frames.append(stack_visit(members, wcs_out, shape, ra, dec, visit.n_available))
    return frames, wcs_out
