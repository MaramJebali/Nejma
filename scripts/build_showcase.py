# AI-generated code: written with Claude (Anthropic) at the team's direction for NASA Space Apps 2026.
"""Precompute the test targets into data/showcase/ so the deployed app can show them instantly.

Run from the repository root:  python scripts/build_showcase.py
"""
import sys
import time
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app_presets import PRESETS  # noqa: E402
from spherex import showcase  # noqa: E402
from spherex.archive import get_cutouts, query_images  # noqa: E402
from spherex.process import build_frames, plan_visits  # noqa: E402
from spherex.resolve import resolve  # noqa: E402

FOV = 0.1
MAX_PER_VISIT = 12

for label, (text, band) in PRESETS.items():
    started = time.time()
    target = resolve(text)
    records = query_images(target.ra, target.dec, band)
    visits, skipped = plan_visits(records, max_per_visit=MAX_PER_VISIT)
    wanted = [r for v in visits for r in v.records]
    cutouts, failures = get_cutouts(wanted, target.ra, target.dec, FOV * 1.5)
    frames, wcs = build_frames(visits, cutouts, target.ra, target.dec, FOV)
    path = showcase.showcase_path(text, FOV, band)
    showcase.save(path, frames, wcs, {
        "built": date.today().isoformat(),
        "n_records": len(records),
        "n_skipped": len(skipped),
        "n_failures": len(failures),
    })
    print(f"{label}: {len(frames)} frames, {len(failures)} failed downloads, {path.stat().st_size / 1e3:.0f} kB, {time.time() - started:.0f} s")
