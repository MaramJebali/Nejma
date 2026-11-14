# AI-generated code: written with Claude (Anthropic) at the team's direction for NASA Space Apps 2026.
"""Precompute the test targets into data/showcase/ so the deployed app can show them instantly.

Every target is saved for all six detectors, so switching the wavelength band is instant too.
Files that already exist are kept; pass --rebuild to recompute them.

Run from the repository root:  python scripts/build_showcase.py [--rebuild]
"""
import sys
import time
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app_presets import PRESETS  # noqa: E402
from spherex import showcase  # noqa: E402
from spherex.archive import DETECTORS, get_cutouts, query_images  # noqa: E402
from spherex.process import build_frames, plan_visits  # noqa: E402
from spherex.resolve import resolve  # noqa: E402
from spherex.spectrum import measure_all  # noqa: E402

FOV = 0.1
MAX_PER_VISIT = 12
rebuild = "--rebuild" in sys.argv

for label, (text, _) in PRESETS.items():
    target = resolve(text)
    for band in DETECTORS:
        path = showcase.showcase_path(text, FOV, band)
        if path.exists() and not rebuild:
            print(f"{label} D{band}: kept existing file", flush=True)
            continue
        started = time.time()
        try:
            records = query_images(target.ra, target.dec, band)
            visits, skipped = plan_visits(records, max_per_visit=MAX_PER_VISIT)
            wanted = [r for v in visits for r in v.records]
            cutouts, failures = get_cutouts(wanted, target.ra, target.dec, FOV * 1.5)
            frames, wcs = build_frames(visits, cutouts, target.ra, target.dec, FOV)
        except Exception as exc:  # keep going with the other detectors
            print(f"{label} D{band}: FAILED ({type(exc).__name__}: {exc})", flush=True)
            continue
        if not frames:
            print(f"{label} D{band}: no usable visits ({len(records)} images), not saved", flush=True)
            continue
        showcase.save(path, frames, wcs, {
            "built": date.today().isoformat(),
            "n_records": len(records),
            "n_skipped": len(skipped),
            "n_failures": len(failures),
        }, measure_all(cutouts, target))
        print(f"{label} D{band}: {len(frames)} frames, {len(failures)} failed downloads, "
              f"{path.stat().st_size / 1e3:.0f} kB, {time.time() - started:.0f} s", flush=True)
