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

SHOWCASE_DIR = Path(__file__).resolve().parents[1] / "data" / "showcase"


def showcase_path(text: str, fov: float, band: int) -> Path:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return SHOWCASE_DIR / f"{slug}_fov{fov:g}_d{band}.npz"


def save(path: Path, frames: list[Frame], wcs: WCS, info: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    meta = [{k: v for k, v in asdict(f).items() if k != "data"} for f in frames]
    np.savez_compressed(
        path,
        data=np.stack([f.data.astype(np.float32) for f in frames]),
        meta=np.array(json.dumps({"frames": meta, "wcs": wcs.to_header_string(), **info})),
    )


def load(path: Path) -> tuple[list[Frame], WCS, dict]:
    with np.load(path) as stored:
        meta = json.loads(str(stored["meta"]))
        data = stored["data"]
    frames = []
    for array, m in zip(data, meta.pop("frames")):
        m["wavelength_um"] = tuple(m["wavelength_um"])
        frames.append(Frame(data=array, **m))
    wcs = WCS(fits.Header.fromstring(meta.pop("wcs")))
    return frames, wcs, meta
