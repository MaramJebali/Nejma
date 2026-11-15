# AI-generated code: written with Claude (Anthropic) at the team's direction for NASA Space Apps 2026.
"""Live queries for the web viewer in docs/.

The viewer plays the saved test targets without any server. For any other sky position it asks this service,
which does the slow part (ask IRSA which SPHEREx images cover the position, download the cutouts, stack them)
in a background thread and reports progress while it works:

    GET  /view?q=<name or coordinates>&fov=0.1&band=2   -> {"id": ..., "state": "working", ...}
    GET  /job/<id>                                      -> progress, then {"state": "done", "target": ..., "view": ...}
    POST /v1/composite  {"q": ..., "fov": 0.1}          -> the same report, for all six detectors at once
    GET  /v1/job/<id>                                   -> progress of a composite job

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
from pydantic import BaseModel

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from spherex.archive import DETECTORS, get_cutouts, query_images  # noqa: E402
from spherex.gaia import query_gaia  # noqa: E402
from spherex.process import build_frames, combine_frames, group_visits, plan_visits  # noqa: E402
from spherex.resolve import resolve  # noqa: E402
from spherex.spectrum import measure_all  # noqa: E402
from spherex.webdata import target_json, view_json  # noqa: E402

FOVS = (0.05, 0.1, 0.2, 0.3)  # degrees, the choices the viewer offers
MAX_PER_VISIT = 12
MAX_COMPOSITE_PER_VISIT = 4  # six detectors at once: fewer images per visit keeps the download bounded
MIN_COMPOSITE_DETECTORS = 3  # a date is only used when this many detectors saw it
COMPOSITE_TOLERANCE_DAYS = 5.0  # visits this close in time are the same epoch in different detectors
MAX_RUNNING = 3  # IRSA is shared: keep our load on it small
KEEP_SECONDS = 30 * 60  # finished single-detector jobs are kept this long, so a repeated question is answered at once
COMPOSITE_KEEP_SECONDS = 6 * 60 * 60  # a six-detector composite is expensive; keep it for the working session

app = FastAPI(title="Nejma live queries", docs_url=None, redoc_url=None)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_origin_regex=r"http://(localhost|127\.0\.0\.1)(:\d+)?",
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

JOBS: dict[str, dict] = {}
LOCK = threading.Lock()


class CompositeRequest(BaseModel):
    q: str
    fov: float = 0.1


def public(job: dict) -> dict:
    """What the viewer is told about a job: everything except our bookkeeping."""
    return {k: v for k, v in job.items() if k not in ("key", "finished", "keep")}


def forget_old_jobs(now: float) -> None:
    for job_id in [i for i, j in JOBS.items()
                   if j.get("finished") and now - j["finished"] > j.get("keep", KEEP_SECONDS)]:
        del JOBS[job_id]


def run(job: dict, text: str, fov: float, band: int) -> None:
    try:
        target = resolve(text)
        job["message"] = "Asking the SPHEREx archive which images cover this position (up to a minute)."
        # Someone is waiting on a web page: give up on a silent archive after about three minutes, not twenty.
        records = query_images(target.ra, target.dec, band, timeout=90, attempts=2)
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
            stars = query_gaia(target.ra, target.dec, fov * 0.75, timeout=60, attempts=1)
        except Exception:  # the viewer works without the Gaia overlay
            stars = []
        info = {"built": date.today().isoformat(), "n_records": len(records), "n_skipped": len(skipped), "n_failures": len(failures)}
        job["target"] = target_json(target, text, fov, points, stars)
        job["view"] = view_json(target, band, frames, wcs, info, points)
        job["state"] = "done"
        job["message"] = "Done."
    except Exception as exc:
        job["state"] = "error"
        job["message"] = str(exc) if isinstance(exc, ValueError) else "The SPHEREx archive at IRSA is not answering right now. Please try again later"
    finally:
        job["finished"] = time.time()


def align_composite(frames_by_band: dict[int, list], tolerance_days: float = COMPOSITE_TOLERANCE_DAYS,
                    min_detectors: int = MIN_COMPOSITE_DETECTORS) -> list:
    """One broadband frame per epoch, from whichever detectors saw that epoch.

    All detectors are stacked on the same grid (see process.target_grid), so a date can be assembled by taking the
    closest visit in each detector. Epochs seen by fewer than `min_detectors` are dropped: a one-detector frame
    would not be a composite.
    """
    keyed = [(band, f) for band, frames in frames_by_band.items() for f in frames]
    if not keyed:
        return []
    clusters = group_visits([f.mjd_mid for _, f in keyed], gap_days=tolerance_days,
                            max_span_days=tolerance_days * 2, bin_days=tolerance_days * 2)
    out = []
    for idx in clusters:
        members = [keyed[i] for i in idx]
        anchor_mjd = sorted(f.mjd_mid for _, f in members)[len(members) // 2]
        chosen: dict[int, object] = {}
        for band, frame in members:
            best = chosen.get(band)
            if best is None or abs(frame.mjd_mid - anchor_mjd) < abs(best.mjd_mid - anchor_mjd):
                chosen[band] = frame
        if len(chosen) >= min_detectors:
            out.append(combine_frames(list(chosen.values())))
    return sorted(out, key=lambda f: f.mjd_mid)


def run_composite(job: dict, text: str, fov: float) -> None:
    try:
        target = resolve(text)
        job["message"] = "Asking the SPHEREx archive which images cover this position in all six detectors (a minute or two)."
        records_by_band: dict[int, list] = {}
        visits_by_band: dict[int, list] = {}
        skipped = 0
        for band in DETECTORS:
            records = query_images(target.ra, target.dec, band, timeout=90, attempts=2)
            visits, too_few = plan_visits(records, max_per_visit=MAX_COMPOSITE_PER_VISIT)
            records_by_band[band] = records
            visits_by_band[band] = visits
            skipped += len(too_few)
        wanted = [r for visits in visits_by_band.values() for v in visits for r in v.records]
        if not wanted:
            raise ValueError("SPHEREx has no usable visits here in any of the six detectors.")
        job["total"] = len(wanted)
        job["message"] = f"Downloading {len(wanted)} image cutouts from the six detectors."

        def progress(done: int, total: int) -> None:
            job["done"] = done
            job["message"] = f"Downloaded {done} of {total} image cutouts."

        cutouts, failures = get_cutouts(wanted, target.ra, target.dec, fov * 1.5, progress=progress)
        job["message"] = "Aligning the detectors and stacking each visit."
        frames_by_band = {}
        for band, visits in visits_by_band.items():
            frames, _ = build_frames(visits, cutouts, target.ra, target.dec, fov, min_per_visit=2)
            if frames:
                frames_by_band[band] = frames
        frames = align_composite(frames_by_band)
        if len(frames) < 2:
            raise ValueError("Too few dates were seen by three or more detectors to build a composite. "
                             "Try a smaller field of view or another position.")
        points = measure_all(cutouts, target)
        try:
            stars = query_gaia(target.ra, target.dec, fov * 0.75, timeout=60, attempts=1)
        except Exception:  # the viewer works without the Gaia overlay
            stars = []
        info = {"built": date.today().isoformat(), "n_records": sum(len(r) for r in records_by_band.values()),
                "n_skipped": skipped, "n_failures": len(failures)}
        job["target"] = target_json(target, text, fov, points, stars)
        job["view"] = view_json(target, 0, frames, None, info, points)
        job["detectors"] = sorted(frames_by_band)
        job["state"] = "done"
        job["message"] = "Done."
    except Exception as exc:
        job["state"] = "error"
        job["message"] = str(exc) if isinstance(exc, ValueError) else "The SPHEREx archive at IRSA is not answering right now. Please try again later"
    finally:
        job["finished"] = time.time()


def _start(kind: str, text: str, fov: float, band: int | None = None) -> dict:
    text = text.strip()
    if not text or len(text) > 120:
        raise HTTPException(400, "Give an object name or coordinates (at most 120 characters).")
    if band is not None and band not in DETECTORS:
        raise HTTPException(400, "The detector must be 1 to 6.")
    fov = min(FOVS, key=lambda f: abs(f - fov))
    key = (text.lower(), fov, band if band is not None else "composite")
    with LOCK:
        now = time.time()
        forget_old_jobs(now)
        for job in JOBS.values():  # the same question is already answered or being worked on
            if job["key"] == key and job["state"] != "error":
                return public(job)
        if sum(j["state"] == "working" for j in JOBS.values()) >= MAX_RUNNING:
            raise HTTPException(429, "Too many positions are being fetched right now. Please try again in a minute.")
        job = {"id": uuid.uuid4().hex, "key": key, "state": "working", "done": 0, "total": 0,
               "message": "Finding the position."}
        if kind == "composite":
            job["keep"] = COMPOSITE_KEEP_SECONDS
        JOBS[job["id"]] = job
    worker = run_composite if kind == "composite" else run
    args = (job, text, fov) if kind == "composite" else (job, text, fov, band)
    threading.Thread(target=worker, args=args, daemon=True).start()
    return public(job)


@app.get("/")
def about() -> dict:
    return {"service": "Nejma live queries"}


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "Nejma live queries"}


# On Vercel the function receives the full path (/api/health), while local runs use the bare
# path (/health). Mount the same app under /api so both spellings answer.
app.mount("/api", app)


@app.get("/view")
def start(q: str, fov: float = 0.1, band: int = 2) -> dict:
    return _start("view", q, fov, band)


@app.post("/v1/composite")
def composite(request: CompositeRequest) -> dict:
    """All six detectors for one position: a 0.75-5.01 um composite, one frame per shared epoch."""
    return _start("composite", request.q, request.fov)


@app.get("/job/{job_id}")
@app.get("/v1/job/{job_id}")
def progress(job_id: str) -> dict:
    job = JOBS.get(job_id)
    if job is None:
        raise HTTPException(404, "That request is no longer kept. Please ask again.")
    return public(job)
