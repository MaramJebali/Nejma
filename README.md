# Dokdo Gull (독도괭이갈매기)

A public web tool that shows how a patch of sky changes over time in images from NASA's SPHEREx mission.
Built for the 2026 NASA Space Apps Challenge, ["Planet X and SPHEREx"](https://www.spaceappschallenge.org/2026/challenges/planet-x-and-spherex/).

**Try it: https://dokdo-gull.streamlit.app** (for example [Barnard's Star, difference view](https://dokdo-gull.streamlit.app/?target=Barnard%27s%20Star&fov=0.1&band=2&mode=difference)).

Enter a sky position (Right Ascension and declination) or an object name. The tool finds every SPHEREx
spectral image that covers that position, stacks the images taken during each visit, and plays the visits
back like a short video so that moving or changing objects stand out.

## What it does

- **Time-lapse:** one frame per SPHEREx visit (about every six months), all on the same north-up grid and
  brightness scale.
- **Difference view:** each visit minus the first. A moving star leaves a black and white pair.
- **All visits stacked:** a deeper image in which moving objects fade.
- **Expected position:** for named objects, orange ticks show where the object should be on each date,
  using its proper motion from SIMBAD.
- **Gaia DR3 overlay:** Gaia stars moved to each visit's date; stars faster than 0.1"/yr are highlighted.
  A SPHEREx source without a Gaia circle is worth a closer look.
- **Spectrum on the fly:** every SPHEREx image sees the target at its own wavelength, so measuring the target
  in each image gives a spectrum, coloured by visit. One detector by default, all six on request.
- **Contamination flags:** the flags SPHEREx sets near the target (saturation, ghosts, persistence and so on)
  are listed for each visit.
- **Shareable links:** `?target=R%20Dra&fov=0.1&band=2&mode=difference`, or `?ra=248.167&dec=66.755`.
  Add `&embed=true` to embed the page in another site.
- **Always current:** the archive query names no data release, so new SPHEREx images appear automatically.

## Test targets (checked on November 14, 2026)

| Target | Detector | What we saw |
|---|---|---|
| Barnard's Star | D2 | Moves north between Aug 2025 and Aug 2026; the difference view shows a black and white pair, and the measured shift matches the SIMBAD proper motion to within about 5". Saturated core |
| Epsilon Indi B | D5 | Black and white pair in the difference view, moving south-east as expected |
| WISE 0855-0714 | D6 | Faint source next to the expected position in all four visits |
| RW Aurigae | D2 | Brighter in 2026 than in Sep 2025, in both the images and the spectrum. Saturated |
| R Draconis | D2 | Bright and saturated in every visit |

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
6. Frames are written as an animated GIF.

The five test targets are precomputed in `data/showcase/` so they open instantly; any other position is
computed live (about one to three minutes the first time).

## Run it locally

```bash
pip install -r requirements.txt
streamlit run app.py
```

Tests: `pip install pytest` and `pytest`. To refresh the saved test targets: `python scripts/build_showcase.py`.

## Data and references

- SPHEREx spectral images (QR and DR1), NASA/IPAC Infrared Science Archive (IRSA): https://irsa.ipac.caltech.edu/Missions/spherex.html
- Gaia DR3 (ESA), queried through IRSA.
- CDS Sesame name resolver and SIMBAD.
- Python libraries: Streamlit, Astropy, reproject, NumPy, SciPy, Pillow, Requests.
- Plan and status: [docs/PLAN.md](docs/PLAN.md).

## Use of AI tools

The source code in this repository was generated with Claude (Anthropic), running in Claude Code, at
the direction of the team. Every AI-generated file starts with a comment that says so, and commits made
with the AI carry a `Co-Authored-By: Claude` trailer. A dated record is kept in
[docs/ai-usage-log.md](docs/ai-usage-log.md).

## License

MIT. See [LICENSE](LICENSE).
