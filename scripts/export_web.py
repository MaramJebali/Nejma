# AI-generated code: written with Claude (Anthropic) at the team's direction for NASA Space Apps 2026.
"""Write the saved test targets (data/showcase/) as JSON for the web viewer (docs/data/).

    python scripts/export_web.py

Run it after scripts/build_showcase.py. The viewer in docs/ then plays the test targets without any server.
"""
from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app_presets import PRESETS  # noqa: E402
from spherex import showcase  # noqa: E402
from spherex.archive import DETECTORS  # noqa: E402
from spherex.gaia import query_gaia  # noqa: E402
from spherex.resolve import resolve  # noqa: E402
from spherex.webdata import target_json, view_json  # noqa: E402

FOV = 0.1
OUT = Path(__file__).resolve().parents[1] / "docs" / "data"

# Shown under each name in the viewer. Kept to what the challenge statement itself says about each target.
ABOUT = {
    "Barnard's Star": "Fast-moving nearby star",
    "eps Ind B": "Pair of brown dwarfs orbiting a nearby star",
    "WISE J085510.83-071442.5": "Fast-moving brown dwarf, the coldest known",
    "RW Aur": "Variable star",
    "R Dra": "Variable star",
}


def write(path: Path, document: dict) -> int:
    path.write_text(json.dumps(document, separators=(",", ":"), allow_nan=False), encoding="utf-8")
    return path.stat().st_size


OUT.mkdir(parents=True, exist_ok=True)
index = []
for name, (query, default_band) in PRESETS.items():
    target = resolve(query)
    slug = showcase.showcase_path(query, FOV, default_band).stem.split("_fov")[0]
    points, bands, size = [], [], 0
    for band in DETECTORS:
        path = showcase.showcase_path(query, FOV, band)
        if not path.exists():
            continue
        frames, wcs, info = showcase.load(path)
        size += write(OUT / f"{slug}_d{band}.json", view_json(target, band, frames, wcs, info, info["points"]))
        points += info["points"]
        bands.append(band)
    try:
        stars = query_gaia(target.ra, target.dec, FOV * 0.75)
    except Exception as exc:  # the viewer works without the overlay
        print(f"{name}: Gaia stars not available ({type(exc).__name__})", flush=True)
        stars = []
    size += write(OUT / f"{slug}.json", target_json(target, query, FOV, points, stars))
    index.append({
        "slug": slug,
        "name": name.split(" (")[0],
        "about": ABOUT.get(query, ""),
        "query": query,
        "band": default_band,
        "bands": bands,
    })
    print(f"{name}: detectors {bands}, {len(points)} spectrum points, {len(stars)} Gaia stars, {size / 1e6:.2f} MB", flush=True)

write(OUT / "index.json", {"built": date.today().isoformat(), "fov": FOV, "detectors": {str(k): list(v) for k, v in DETECTORS.items()}, "targets": index})
print(f"Wrote {OUT}", flush=True)
