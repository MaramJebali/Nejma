# Dokdo Gull (독도괭이갈매기)

A public web tool that shows how a patch of sky changes over time in images from NASA's SPHEREx mission.
Built for the 2026 NASA Space Apps Challenge, ["Planet X and SPHEREx"](https://www.spaceappschallenge.org/2026/challenges/planet-x-and-spherex/).

**Try it: https://cafe2913.github.io/dokdo-gull/** (for example [RW Aurigae, difference view](https://cafe2913.github.io/dokdo-gull/?target=RW%20Aur&mode=diff)
or [WISE 0855 at the longest wavelengths](https://cafe2913.github.io/dokdo-gull/?target=WISE%20J085510.83-071442.5&band=6)).
The five test targets play at once. Any other position is computed live, in one to three minutes, by the first
version of the viewer at https://dokdo-gull.streamlit.app.

Enter a sky position (Right Ascension and declination) or an object name. The tool finds every SPHEREx
spectral image that covers that position, stacks the images taken during each visit, and plays the visits
back like a short video so that moving or changing objects stand out.

## What it does

- **Time-lapse:** one frame per SPHEREx visit (about every six months), all on the same north-up grid and
  brightness scale. Play, pause, step, zoom and pan.
- **Blink two visits:** flip between any two visits; anything that jumps has moved.
- **Difference view:** one visit minus another. A moving object is half black, half white; one that changed
  brightness is white or black all over.
- **All visits stacked:** a deeper image in which moving objects fade.
- **Expected position:** for named objects, orange ticks show where the object should be on each date, using
  its proper motion from SIMBAD. The measured shift is shown next to the predicted one.
- **Gaia DR3 overlay:** Gaia stars moved to each visit's date; stars faster than 0.1"/yr are highlighted.
  A SPHEREx source without a Gaia circle is worth a closer look.
- **Spectrum on the fly:** every SPHEREx image sees the target at its own wavelength, so measuring the target
  in each image gives a spectrum from 0.75 to 5 um across the six detectors.
- **Brightness over time:** the median brightness of each visit, one line per detector.
- **Contamination flags:** the flags SPHEREx sets near the target are listed for each visit, and saturated
  pixels can be painted on the image.
- **The same sky from other telescopes:** 2MASS, WISE and the Digitized Sky Survey next to the SPHEREx image,
  with the SPHEREx position marked.
- **Shareable links:** `?target=R%20Dra&fov=0.1&band=2&mode=diff`, or `?ra=248.167&dec=66.755`.
  Add `&embed=1` to show only the viewer inside another site.
- **Always current:** the archive query names no data release, so new SPHEREx images appear automatically.

## Test targets (checked on November 14 and 15, 2026)

| Target | Detector | What we saw |
|---|---|---|
| Barnard's Star | D2 | Measured 9.9" of motion in 360 days; the SIMBAD proper motion predicts 10.3". Saturated core |
| Epsilon Indi B | D5 | Measured 6.6" of motion in 522 days; predicted 6.7" |
| WISE 0855-0714 | D6 | Faint source at the expected position, about 0.4 to 0.65 mJy; between the two visits where it is clear enough to locate it moved 3.5" in 163 days (predicted 3.6"). It has no Gaia counterpart |
| RW Aurigae | D2 | Saturated. The light just outside the core was about 1.45 times brighter in 2026 than in September 2025 |
| R Draconis | D2 | Saturated in every image. The light just outside the core fell to about 0.3 times its June 2025 value by June 2026 |

As a check on an object outside the test list, a live query for Luhman 16 (detector D5) measured 2.8" of motion
in a year against a predicted 2.8".

Brightness for saturated stars is measured in a ring outside the core. That shows changes but not the total
brightness, and it is rough: for Barnard's Star, which is steady, it still differs by about 20% between visits.

## How it works

1. Names are resolved with CDS Sesame (SIMBAD) and moved from epoch 2000 to 2026 along their proper motion.
2. The IRSA TAP service lists the SPHEREx spectral images that cover the position (`spherex.plane`,
   `spherex.artifact`).
3. Cutouts are downloaded from IRSA (with retries and a disk cache).
4. Zodiacal light (the ZODI plane) and the remaining background are removed, and broken pixels (NONFUNC,
   MISSING_DATA, HOT, COLD) are left out.
5. Images are grouped into visits and reprojected onto a 3" north-up grid; each visit is the median of up to
   12 images, which also removes cosmic rays. Stacking within one detector keeps the wavelength range the same
   from visit to visit.
6. The target is measured in every image (aperture photometry, or the ring outside the core when it is
   saturated) and each visit's centre of light is compared with the predicted position.

## What is in this repository

| Path | What it is |
|---|---|
| `spherex/` | The Python library: archive access, name resolution, stacking, photometry, Gaia, JSON for the web |
| `docs/` | The web viewer: one HTML page, one stylesheet and one script, with no build step. `docs/data/` holds the five test targets (all six detectors), so they play without any server |
| `api/` | A small service (FastAPI) that computes any other position for the web viewer and reports progress |
| `app.py` | The first version of the viewer, written with Streamlit. It computes any position live |
| `scripts/` | `build_showcase.py` computes the test targets; `export_web.py` writes them as JSON for `docs/data/` |
| `tests/` | Tests for the library and the service |

## Run it locally

```bash
pip install -r requirements.txt
streamlit run app.py
```

The web viewer needs no installation, only a web server for the files:

```bash
python -m http.server 8502 --directory docs
```

The live-query service for the web viewer:

```bash
pip install -r api/requirements.txt
uvicorn api.main:app --port 8000
```

Then open `http://localhost:8502/?api=http://localhost:8000` and enter any object name or coordinates.

Tests: `pip install pytest httpx` and `pytest`. To refresh the saved test targets:
`python scripts/build_showcase.py --rebuild` and then `python scripts/export_web.py`.

## Data and references

- SPHEREx spectral images (QR and DR1), NASA/IPAC Infrared Science Archive (IRSA): https://irsa.ipac.caltech.edu/Missions/spherex.html
- Gaia DR3 (ESA), queried through IRSA.
- 2MASS, AllWISE and DSS2 sky images, served as HiPS by IRSA (https://irsa.ipac.caltech.edu/data/hips/list).
- CDS Sesame name resolver and SIMBAD.
- Aladin Lite (CDS, Strasbourg Observatory; LGPL-3.0), loaded from jsDelivr, draws the other surveys.
- Python libraries: Streamlit, FastAPI, Uvicorn, Astropy, reproject, NumPy, SciPy, Pillow, Requests.
- Typefaces: Instrument Serif and IBM Plex Sans (SIL Open Font License), from Google Fonts.
- Plan and status: [docs/PLAN.md](docs/PLAN.md).

## Use of AI tools

The source code in this repository was generated with Claude (Anthropic), running in Claude Code, at
the direction of the team. Every AI-generated file starts with a comment that says so, and commits made
with the AI carry a `Co-Authored-By: Claude` trailer. A dated record is kept in
[docs/ai-usage-log.md](docs/ai-usage-log.md).

## License

MIT. See [LICENSE](LICENSE).
