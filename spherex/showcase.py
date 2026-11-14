# AI-generated code: written with Claude (Anthropic) at the team's direction for NASA Space Apps 2026.
"""Save and load stacked frames, so the test targets play instantly without waiting for IRSA."""
from __future__ import annotations

import json
import re
from dataclasses import asdict
from pathlib import Path

import numpy as np
from astropy.io import fits
from astropy.wcs import WCS

from .process import Frame
from .spectrum import SpectrumPoint

SHOWCASE_DIR = Path(__file__).resolve().parents[1] / "data" / "showcase"


def showcase_path(text: str, fov: float, band: int) -> Path:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return SHOWCASE_DIR / f"{slug}_fov{fov:g}_d{band}.npz"


def save(path: Path, frames: list[Frame], wcs: WCS, info: dict, points: list[SpectrumPoint] = ()) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    arrays = ("data", "saturated")
    meta = [{k: getattr(f, k) for k in f.__dataclass_fields__ if k not in arrays} for f in frames]
    extra = {}
    if frames and all(f.saturated is not None for f in frames):
        extra["sat"] = np.stack([f.saturated.astype(np.uint8) for f in frames])
    np.savez_compressed(
        path,
        data=np.stack([f.data.astype(np.float32) for f in frames]),
        meta=np.array(json.dumps({"frames": meta, "wcs": wcs.to_header_string(), "points": [asdict(p) for p in points], **info})),
        **extra,
    )


def load(path: Path) -> tuple[list[Frame], WCS, dict]:
    """Returns (frames, grid WCS, info). info["points"] holds the SpectrumPoints."""
    with np.load(path) as stored:
        meta = json.loads(str(stored["meta"]))
        data = stored["data"]
        sat = stored["sat"].astype(bool) if "sat" in stored else [None] * len(data)  # files saved before the mask existed
    frames = []
    for array, mask, m in zip(data, sat, meta.pop("frames")):
        m["wavelength_um"] = tuple(m["wavelength_um"])
        frames.append(Frame(data=array, saturated=mask, **m))
    wcs = WCS(fits.Header.fromstring(meta.pop("wcs")))
    meta["points"] = [SpectrumPoint(**p) for p in meta.get("points", [])]
    return frames, wcs, meta
