# AI-generated code: written with Claude (Anthropic) at the team's direction for NASA Space Apps 2026.
"""Live queries for the web viewer in docs/.

The viewer plays the saved test targets without any server. For any other sky position it asks this service,
which does the slow part (ask IRSA which SPHEREx images cover the position, download the cutouts, stack them)
in a background thread and reports progress while it works:

    GET /view?q=<name or coordinates>&fov=0.1&band=2   -> {"id": ..., "state": "working", ...}
    GET /job/<id>                                      -> progress, then {"state": "done", "target": ..., "view": ...}

Run locally with:  uvicorn api.main:app --port 8000
"""
from __future__ import annotations

import sys
import threading
import time
import uuid
from datetime import date
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from spherex.archive import DETECTORS, get_cutouts, query_images  # noqa: E402
from spherex.gaia import query_gaia  # noqa: E402
from spherex.process import build_frames, plan_visits  # noqa: E402
from spherex.resolve import resolve  # noqa: E402
from spherex.spectrum import measure_all  # noqa: E402
from spherex.webdata import target_json, view_json  # noqa: E402

FOVS = (0.05, 0.1, 0.2, 0.3)  # degrees, the choices the viewer offers
MAX_PER_VISIT = 12
MAX_RUNNING = 3  # IRSA is shared: keep our load on it small
KEEP_SECONDS = 30 * 60  # finished jobs are kept this long, so a repeated question is answered at once

app = FastAPI(title="Dokdo Gull live queries", docs_url=None, redoc_url=None)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://cafe2913.github.io"],
    allow_origin_regex=r"http://(localhost|127\.0\.0\.1)(:\d+)?",
    allow_methods=["GET"],
)

JOBS: dict[str, dict] = {}
LOCK = threading.Lock()


def public(job: dict) -> dict:
    """What the viewer is told about a job: everything except our bookkeeping."""
    return {k: v for k, v in job.items() if k not in ("key", "finished")}


def forget_old_jobs(now: float) -> None:
    for job_id in [i for i, j in JOBS.items() if j.get("finished") and now - j["finished"] > KEEP_SECONDS]:
        del JOBS[job_id]


def run(job: dict, text: str, fov: float, band: int) -> None:
    try:
        target = resolve(text)
        job["message"] = "Asking the SPHEREx archive which images cover this position (up to a minute)."
        records = query_images(target.ra, target.dec, band)
        visits, skipped = plan_visits(records, max_per_visit=MAX_PER_VISIT)
        wanted = [r for v in visits for r in v.records]
        if not wanted:
            raise ValueError(f"SPHEREx has no usable visits here for detector D{band} ({len(records)} images in the archive).")
        job["total"] = len(wanted)
        job["message"] = f"Downloading {len(wanted)} image cutouts."

        def progress(done: int, total: int) -> None:
            job["done"] = done
            job["message"] = f"Downloaded {done} of {total} image cutouts."

        cutouts, failures = get_cutouts(wanted, target.ra, target.dec, fov * 1.5, progress=progress)
        job["message"] = "Aligning and stacking the images."
        frames, wcs = build_frames(visits, cutouts, target.ra, target.dec, fov)
        if not frames:
            raise ValueError("Too few images could be downloaded to build a visit. Please try again in a few minutes.")
        points = measure_all(cutouts, target)
        try:
            stars = query_gaia(target.ra, target.dec, fov * 0.75)
        except Exception:  # the viewer works without the Gaia overlay
            stars = []
        info = {"built": date.today().isoformat(), "n_records": len(records), "n_skipped": len(skipped), "n_failures": len(failures)}
        job["target"] = target_json(target, text, fov, points, stars)
        job["view"] = view_json(target, band, frames, wcs, info, points)
        job["state"] = "done"
        job["message"] = "Done."
    except Exception as exc:
        job["state"] = "error"
        job["message"] = str(exc) if isinstance(exc, ValueError) else f"The SPHEREx archive did not answer ({type(exc).__name__})."
    finally:
        job["finished"] = time.time()


@app.get("/")
def about() -> dict:
    return {"service": "Dokdo Gull live queries", "viewer": "https://cafe2913.github.io/dokdo-gull/", "code": "https://github.com/cafe2913/dokdo-gull"}


@app.get("/view")
def start(q: str, fov: float = 0.1, band: int = 2) -> dict:
    text = q.strip()
    if not text or len(text) > 120:
        raise HTTPException(400, "Give an object name or coordinates (at most 120 characters).")
    if band not in DETECTORS:
        raise HTTPException(400, "The detector must be 1 to 6.")
    fov = min(FOVS, key=lambda f: abs(f - fov))
    key = (text.lower(), fov, band)
    with LOCK:
        now = time.time()
        forget_old_jobs(now)
        for job in JOBS.values():  # the same question is already answered or being worked on
            if job["key"] == key and job["state"] != "error":
                return public(job)
        if sum(j["state"] == "working" for j in JOBS.values()) >= MAX_RUNNING:
            raise HTTPException(429, "Too many positions are being fetched right now. Please try again in a minute.")
        job = {"id": uuid.uuid4().hex, "key": key, "state": "working", "done": 0, "total": 0, "message": "Finding the position."}
        JOBS[job["id"]] = job
    threading.Thread(target=run, args=(job, text, fov, band), daemon=True).start()
    return public(job)


@app.get("/job/{job_id}")
def progress(job_id: str) -> dict:
    job = JOBS.get(job_id)
    if job is None:
        raise HTTPException(404, "That request is no longer kept. Please ask again.")
    return public(job)
