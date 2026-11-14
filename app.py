# AI-generated code: written with Claude (Anthropic) at the team's direction for NASA Space Apps 2026.
"""Dokdo Gull: a time-lapse viewer for SPHEREx images."""
from __future__ import annotations

import base64

import numpy as np
import streamlit as st

from app_presets import PRESETS
from spherex import gaia, render, showcase, spectrum
from spherex.archive import DETECTORS, get_cutouts, is_cached, query_images
from spherex.process import EXCLUDE_FLAGS, build_frames, plan_visits
from spherex.resolve import Target, mjd_to_year, resolve
FOVS = [0.05, 0.1, 0.2, 0.3]  # degrees
MODES = {"animation": "Animation", "difference": "Difference", "stack": "All visits stacked"}
MAX_PER_VISIT = 12
MARKER_RADIUS_PX = 4.0  # on the 3" grid, so 12": larger than the 7.5" PSF

st.set_page_config(page_title="Dokdo Gull | SPHEREx time-lapse viewer", page_icon="🔭", layout="wide")
ss = st.session_state


def init_state() -> None:
    """Fill the controls from the URL once, so links like ?target=R%20Dra&band=2 open that view."""
    if ss.get("initialized"):
        return
    params = st.query_params
    text = ""
    if params.get("ra") and params.get("dec"):
        text = f"{params['ra']} {params['dec']}"
    elif params.get("target"):
        text = params["target"]
    try:
        fov = float(params.get("fov", 0.1))
    except ValueError:
        fov = 0.1
    try:
        band = int(params.get("band", 2))
    except ValueError:
        band = 2
    ss.target_text = text
    ss.fov = min(FOVS, key=lambda f: abs(f - fov))
    ss.band = band if band in DETECTORS else 2
    ss.mode = params.get("mode") if params.get("mode") in MODES else "animation"
    ss.request = (text, ss.fov, ss.band) if text else None
    ss.initialized = True


def apply_preset() -> None:
    choice = ss.preset
    if choice in PRESETS:
        ss.target_text, ss.band = PRESETS[choice]
        submit()


def submit() -> None:
    text = ss.target_text.strip()
    if not text:
        return
    ss.live = False
    ss.request = (text, ss.fov, ss.band)
    params = {"target": text, "fov": f"{ss.fov:g}", "band": str(ss.band), "mode": ss.mode}
    st.query_params.from_dict(params)


@st.cache_data(show_spinner=False, ttl=6 * 3600)
def cached_resolve(text: str) -> Target:
    return resolve(text)


def get_frames(target: Target, fov: float, band: int, text: str = "", live: bool = False):
    """Query, download (with a progress bar) and stack. Results are kept for the session.

    Test targets come from data/showcase/ unless `live` is set, so they play without waiting for IRSA.
    """
    key = (round(target.ra, 5), round(target.dec, 5), fov, band, live)
    cache = ss.setdefault("frames_cache", {})
    if key in cache:
        return cache[key]
    stored = showcase.showcase_path(text, fov, band)
    if not live and text and stored.exists():
        frames, wcs, info = showcase.load(stored)
        result = {"frames": frames, "wcs": wcs, "n_records": info["n_records"], "skipped": [None] * info["n_skipped"],
                  "failures": [None] * info["n_failures"], "showcase": info["built"], "points": info["points"]}
        cache[key] = result
        return result
    with st.spinner("Searching the SPHEREx archive at IRSA (this can take up to a minute)..."):
        records = query_images(target.ra, target.dec, band)
    visits, skipped = plan_visits(records, max_per_visit=MAX_PER_VISIT)
    wanted = [r for v in visits for r in v.records]
    size = fov * 1.5  # room for the image rotation
    todo = sum(not is_cached(r, target.ra, target.dec, size) for r in wanted)
    bar = st.progress(0.0, text=f"Downloading {todo} new image cutouts ({len(wanted) - todo} already saved)...") if wanted else None

    def progress(done: int, total: int) -> None:
        if bar is not None:
            bar.progress(done / total, text=f"Downloaded {done} of {total} image cutouts")

    cutouts, failures = get_cutouts(wanted, target.ra, target.dec, size, progress=progress)
    if bar is not None:
        bar.empty()
    with st.spinner("Aligning and stacking images..."):
        frames, wcs = build_frames(visits, cutouts, target.ra, target.dec, fov)
        points = spectrum.measure_all(cutouts, target)
    result = {"frames": frames, "wcs": wcs, "n_records": len(records), "skipped": skipped, "failures": failures,
              "showcase": None, "points": points}
    if len(cache) >= 4:
        cache.pop(next(iter(cache)))
    cache[key] = result
    return result


def other_detector_points(target: Target, fov: float, band: int) -> list:
    """Spectrum points from the five detectors not on screen (4 images per visit each, to keep it quick)."""
    key = ("spectrum", round(target.ra, 5), round(target.dec, 5), band)
    if key in ss:
        return ss[key]
    others = [d for d in DETECTORS if d != band]
    bar = st.progress(0.0, text="Measuring the other detectors...")
    points = []
    for i, det in enumerate(others):
        visits, _ = plan_visits(query_images(target.ra, target.dec, det), max_per_visit=4)
        wanted = [r for v in visits for r in v.records]
        cutouts, _ = get_cutouts(wanted, target.ra, target.dec, fov * 1.5)
        points += spectrum.measure_all(cutouts, target)
        bar.progress((i + 1) / len(others), text=f"Measured detector D{det} ({i + 1} of {len(others)})")
    bar.empty()
    ss[key] = points
    return points


def show_spectrum(points, frames) -> None:
    def visit_of(mjd: float) -> str:
        for f in frames:
            if f.mjd_start - 1 <= mjd <= f.mjd_end + 1:
                return f.date
        return "other dates"

    rows = [
        {
            "Wavelength (um)": round(p.wavelength_um, 4),
            "Brightness (mJy)": round(p.flux_mjy, 3),
            "Visit": visit_of(p.mjd),
            "Saturated": p.saturated,
        }
        for p in points
    ]
    st.scatter_chart(rows, x="Wavelength (um)", y="Brightness (mJy)", color="Visit", height=360)
    saturated = sum(p.saturated for p in points)
    if saturated > len(points) / 2:
        st.warning(
            f"The target is saturated in {saturated} of {len(points)} images, so these values are too low. "
            "Compare visits with each other rather than reading the numbers."
        )
    st.caption(
        "Each dot is one SPHEREx image. Every image sees the target at a slightly different wavelength, so the dots "
        "together trace its spectrum. Colours separate the visits: a gap between colours at the same wavelength means "
        "the object changed brightness."
    )


def marker_positions(target: Target, frames, wcs) -> list[tuple[float, float]]:
    out = []
    for f in frames:
        ra, dec = target.position_at(mjd_to_year(f.mjd_mid))
        x, y = wcs.world_to_pixel_values(ra, dec)
        out.append((float(x), float(y)))
    return out


def frame_label(f) -> str:
    return f"{f.date}   D{f.detector} {f.wavelength_um[0]:.2f}-{f.wavelength_um[1]:.2f} um   {f.n_images} images"


def show_gif(images, frame_ms: int) -> None:
    data = base64.b64encode(render.gif_bytes(images, frame_ms)).decode()
    st.markdown(
        f'<img src="data:image/gif;base64,{data}" style="max-width:100%;image-rendering:pixelated" alt="SPHEREx time-lapse">',
        unsafe_allow_html=True,
    )


init_state()

with st.sidebar:
    st.header("Where to look")
    st.selectbox("Test targets", ["Choose one..."] + list(PRESETS), key="preset", on_change=apply_preset)
    st.text_input(
        "Object name or coordinates",
        key="target_text",
        placeholder="R Dra   or   248.167 66.755   or   16:32:40 +66:45:18",
        help="Coordinates are Right Ascension and declination (ICRS), in degrees or h:m:s d:m:s.",
    )
    st.select_slider("Field of view", options=FOVS, key="fov", format_func=lambda v: f"{v * 60:.0f} arcmin")
    st.selectbox(
        "Detector (wavelength band)",
        options=list(DETECTORS),
        key="band",
        format_func=lambda d: f"D{d}: {DETECTORS[d][0]:.2f}-{DETECTORS[d][1]:.2f} um",
    )
    st.button("Show", type="primary", on_click=submit, use_container_width=True)
    st.caption(
        "Larger fields show faster-moving objects but take longer to download. "
        "Images are cached, so a second look at the same place is quick."
    )

st.title("Dokdo Gull (독도괭이갈매기)")
st.caption("See how a patch of sky changes over time in NASA SPHEREx images.")

if not ss.request:
    st.markdown(
        """
SPHEREx maps the whole sky every six months in 102 near-infrared colours. Stars that move, asteroids,
comets and variable stars show up as changes between those visits.

1. Pick a **test target** on the left, or type an object name or coordinates and press **Show**.
2. The viewer finds every SPHEREx image of that spot, stacks the images from each visit and plays the
   visits in order.
3. Use **Difference** to see only what changed. The orange ticks show where a known moving object is
   expected to be on each date.
"""
    )
    st.stop()

text, fov, band = ss.request
try:
    target = cached_resolve(text)
except Exception as exc:
    st.error(f"Could not find that position: {exc}")
    st.stop()

try:
    result = get_frames(target, fov, band, text, live=ss.get("live", False))
except Exception as exc:
    st.error(f"The SPHEREx archive did not answer ({type(exc).__name__}). Please try again in a minute.")
    st.stop()

frames, wcs = result["frames"], result["wcs"]
st.subheader(target.label)
motion = (
    f"Proper motion {np.hypot(target.pm_ra_cosdec, target.pm_dec) / 1000:.2f}\"/yr (SIMBAD). "
    if target.has_motion
    else ""
)
st.caption(f"RA {target.ra:.5f}°, Dec {target.dec:+.5f}° (2026.0). {motion}Detector D{band}, field {fov * 60:.0f} arcmin.")

if result["showcase"]:
    st.caption(f"Saved result from {result['showcase']}, so it opens instantly.")
    if st.button("Check the archive for newer images"):
        ss.live = True
        st.rerun()

if result["failures"]:
    st.warning(f"{len(result['failures'])} image(s) could not be downloaded and were left out.")
if result["skipped"]:
    st.info(f"{len(result['skipped'])} short visit(s) with fewer than 3 images were left out.")
if not frames:
    st.error(f"No usable SPHEREx visits found here ({result['n_records']} images in the archive for this detector).")
    st.stop()

controls = st.columns([3, 2, 2])
mode = controls[0].radio("View", list(MODES), key="mode", format_func=MODES.get, horizontal=True)
frame_ms = controls[1].slider("Frame time (ms)", 200, 2000, 700, step=100)
show_marker = controls[2].checkbox("Mark expected position", value=True, help="Orange ticks: where the target should be on each date, from its catalogue proper motion.")
show_gaia = controls[2].checkbox(
    "Gaia DR3 stars",
    value=False,
    help="Blue circles: Gaia DR3 stars moved to each visit's date. Pink: stars moving faster than 0.1\"/yr. "
    "A SPHEREx source with no circle is not in Gaia, which is worth a closer look (cold brown dwarfs are invisible to Gaia).",
)

arrays = [render.fill_small_holes(f.data) for f in frames]
scale = render.display_scale(arrays[0].shape[0])
markers = marker_positions(target, frames, wcs) if show_marker else [None] * len(frames)
overlays = [None] * len(frames)
if show_gaia:
    try:
        g_limit = controls[2].slider("Gaia stars brighter than G =", 10.0, 21.0, 16.0, step=0.5)
        with st.spinner("Loading Gaia DR3 stars (about 30 seconds the first time)..."):
            stars = gaia.query_gaia(target.ra, target.dec, fov * 0.75)
        shown = [s for s in stars if s.g_mag <= g_limit or s.is_fast]  # fast movers are always shown
        overlays = [gaia.pixel_positions(shown, wcs, mjd_to_year(f.mjd_mid), arrays[0].shape) for f in frames]
        n_fast = sum(s.is_fast for s in stars)
        st.caption(
            f"Showing {len(shown)} of {len(stars)} Gaia DR3 stars in the field (G <= {g_limit:g}, plus all fast movers). "
            f"{n_fast} move faster than 0.1\"/yr."
        )
    except Exception as exc:
        st.warning(f"Gaia stars could not be loaded ({type(exc).__name__}).")

if mode == "stack":
    with np.errstate(all="ignore"):
        deep = np.nanmedian(np.stack(arrays), axis=0)
    low, high = render.display_limits([deep])
    image = render.compose(render.to_gray(deep, low, high), f"All {len(frames)} visits   D{band}", scale, None)
    st.image(render.png_bytes(image), caption="Median of all visits. Moving objects fade, steady ones get clearer.")
elif mode == "difference":
    if len(frames) < 2:
        st.info("Difference needs at least two visits.")
    else:
        diffs = render.difference_frames(arrays)[1:]
        limit = render.difference_limit(diffs)
        images = [
            render.compose(render.to_diverging(d, limit), f"{f.date} minus {frames[0].date}", scale, m, MARKER_RADIUS_PX, o)
            for d, f, m, o in zip(diffs, frames[1:], markers[1:], overlays[1:])
        ]
        show_gif(images, frame_ms)
        st.caption("White: brighter than on the first visit. Black: fainter. A moving star leaves a black and white pair.")
else:
    low, high = render.display_limits(arrays)
    images = [
        render.compose(render.to_gray(a, low, high), frame_label(f), scale, m, MARKER_RADIUS_PX, o)
        for a, f, m, o in zip(arrays, frames, markers, overlays)
    ]
    show_gif(images, frame_ms)
    st.caption("North is up, east is left. All frames use the same brightness scale.")

st.subheader("Spectrum at the target")
points = list(result.get("points") or [])
if st.toggle("Add the other five detectors (0.75 to 5 um, downloads about 60 more images)", key="all_detectors"):
    try:
        points += other_detector_points(target, fov, band)
    except Exception as exc:
        st.warning(f"Some detectors could not be measured ({type(exc).__name__}).")
if points:
    show_spectrum(points, frames)
else:
    st.info("No spectrum points: the target is too close to the edge of the images.")

with st.expander("Visits used", expanded=True):
    rows = [
        {
            "Visit (median date)": f.date,
            "Days covered": round(f.span_days, 1),
            "Images used": f"{f.n_images} of {f.n_available}",
            "Wavelength (um)": f"{f.wavelength_um[0]:.2f}-{f.wavelength_um[1]:.2f}",
            "Flags near target (images)": ", ".join(f"{k} ({v})" for k, v in f.target_flags.items()) or "none",
        }
        for f in frames
    ]
    st.dataframe(rows, use_container_width=True, hide_index=True)
    st.caption(
        "Each visit is the median of up to "
        f"{MAX_PER_VISIT} images. Zodiacal light is removed and pixels flagged "
        + ", ".join(EXCLUDE_FLAGS)
        + " are left out."
    )

st.caption(
    "Data: NASA SPHEREx spectral images from the NASA/IPAC Infrared Science Archive (IRSA). "
    "Gaia DR3 (ESA) via IRSA. Names resolved with CDS Sesame/SIMBAD. Code: https://github.com/cafe2913/dokdo-gull"
)
