# Project submission worksheet (draft answers below)

Everything on the project page and in linked material must be in English.
Deadline: Sunday, November 15, 11:59 p.m. Seoul time ("Submit for Judging"). Re-submitting is allowed until then.
The draft text below was written with AI assistance (Claude) from what the team built and measured. Read it,
change what is not right, and say so in the "Use of SI" field.

## Project Name

Dokdo Gull: a SPHEREx time-lapse viewer

## High-Level Project Summary

Dokdo Gull is a public web tool that plays NASA SPHEREx images of one patch of sky in time order, so that anything
that moved or changed brightness stands out. You enter an object name or a Right Ascension and declination; the
tool finds every SPHEREx spectral image of that position, combines the images of each visit, and shows the visits
as a time-lapse that you can play, blink between two dates, subtract, or stack. It marks where a catalogued object
should be on each date and measures how far it actually moved, overlays Gaia stars, builds a spectrum from 0.75 to
5 micrometres on the fly, and shows the same field in 2MASS, WISE and DSS. On the challenge's test targets it
measured Barnard's Star moving 9.9 arcseconds in 360 days (catalogue prediction: 10.3), Epsilon Indi B moving 6.6
(6.7) and WISE 0855 moving 3.5 (3.6), and it shows the variable stars RW Aurigae and R Draconis changing brightness.
SPHEREx returns far more images than any one person can look through; a tool that needs only a web browser lets
anyone help look for moving and changing objects.

## Link to Project Demo

(public link to the slide deck, at most 7 slides)

## Link to Final Project

https://cafe2913.github.io/dokdo-gull/

## Detailed Project Description

**What it does**

- Time-lapse of a sky position: one frame per SPHEREx visit (about every six months), all on the same north-up
  grid and brightness scale. Play, pause, step, zoom and pan.
- Blink two visits, subtract one visit from another, or stack all visits. In the difference view an object that
  moved is half black and half white, and one that changed brightness is white or black all over.
- Expected position: for a named object, ticks show where its catalogue proper motion puts it on each date, and
  the measured shift is shown next to the predicted one.
- Gaia DR3 overlay: Gaia stars moved to each visit's date. A SPHEREx source with no Gaia circle (such as the cold
  brown dwarf WISE 0855) is worth a closer look.
- Spectrum on the fly: every SPHEREx image sees the target at its own wavelength, so measuring the target in each
  image gives a spectrum across the six detectors, plus a chart of brightness over time.
- Contamination flags near the target for every visit, and saturated pixels painted on the image.
- The same field in 2MASS, WISE and DSS, with the SPHEREx position marked.
- Coordinates in the URL (`?ra=248.167&dec=66.755`, `?target=R%20Dra&band=2&mode=diff`) and an embed mode.
- The archive query names no data release, so new SPHEREx images are included automatically.

**How it works**

1. A name is resolved with SIMBAD and moved from epoch 2000 to today along its proper motion.
2. The IRSA TAP service lists the SPHEREx spectral images that cover the position.
3. Cutouts are downloaded from IRSA. The zodiacal light model and the remaining background are subtracted and
   broken pixels are left out.
4. Images are grouped into visits, aligned on a 3-arcsecond north-up grid and combined with a median, one detector
   at a time.
5. The target is measured in every image. Stars that saturate the detector are measured in a ring outside the
   core, which shows changes but not the total brightness; the page says so.

The five test targets are precomputed for all six detectors, so they play immediately in the browser. Any other
position is computed on request by a small service, which takes a few minutes and depends on the IRSA archive
being reachable.

**What we checked**

| Target | Result |
|---|---|
| Barnard's Star | Measured 9.9" of motion in 360 days; catalogue prediction 10.3" |
| Epsilon Indi B | Measured 6.6" in 522 days; prediction 6.7" |
| WISE 0855-0714 | Faint source at the expected position at 4.4 to 5.0 micrometres, with no Gaia counterpart; 3.5" in 163 days against a predicted 3.6" |
| RW Aurigae | About 1.45 times brighter in 2026 than in September 2025 (measured outside the saturated core) |
| R Draconis | Fell to about 0.3 times its June 2025 brightness by June 2026 (measured outside the saturated core) |
| Luhman 16 (not a test target) | Measured 2.8" in a year; prediction 2.8" |

**Tools**

Python (Astropy, reproject, NumPy, SciPy, Requests, FastAPI, Streamlit), JavaScript, HTML and CSS without a
framework, Aladin Lite, GitHub Pages, Render, Streamlit Community Cloud. Code: https://github.com/cafe2913/dokdo-gull

## Use of Super Intelligence (SI)

Yes. The team chose the challenge, the features to build and the design decisions. The source code was generated
with Claude (Anthropic) in Claude Code at the team's direction; every AI-generated file starts with a comment that
says so, commits carry a `Co-Authored-By: Claude` trailer, and a dated record is kept in the repository
(docs/ai-usage-log.md). Claude was also used to draft and check the English text of this page. No AI-generated
images, video or audio are used; the images in the tool are NASA SPHEREx data.

## NASA Data

- SPHEREx spectral images (Level 2, quick releases and DR1) from the NASA/IPAC Infrared Science Archive (IRSA),
  found through the IRSA TAP service (`spherex.plane`, `spherex.artifact`) and downloaded with the IRSA cutout
  service: https://irsa.ipac.caltech.edu/Missions/spherex.html
- 2MASS and AllWISE sky images, served as HiPS by NASA/IPAC IRSA: https://irsa.ipac.caltech.edu/data/hips/list

## Space Agency Partner Data and Other References

- Gaia DR3 (ESA), queried through IRSA.
- SIMBAD and the Sesame name resolver (CDS, Strasbourg).
- Digitized Sky Survey (DSS2) images, served as HiPS by IRSA.
- Aladin Lite (CDS, Strasbourg Observatory), LGPL-3.0: https://github.com/cds-astro/aladin-lite
- Python libraries: Astropy, reproject, NumPy, SciPy, Pillow, Requests, Streamlit, FastAPI, Uvicorn.
- Typefaces: Instrument Serif and IBM Plex Sans (SIL Open Font License), from Google Fonts.
- Hosting: GitHub Pages, Render, Streamlit Community Cloud.
- AI tool: Claude (Anthropic), in Claude Code.
