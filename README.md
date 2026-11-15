<p align="center">
  <img src="assets/nejma-logo.jpg" alt="Nejma logo" width="140">
</p>

# Nejma

**Nejma — a public-facing time-domain viewer for NASA's SPHEREx mission.**

Enter a sky position — an object name, or Right Ascension and declination — and Nejma finds every SPHEREx spectral image that covers it, stacks the images taken during each visit, and plays the visits back like a short video, so that anything that moved or changed in the infrared sky stands out.

## What it does

- **Time-lapse:** one frame per SPHEREx visit (about every six months), all on the same north-up grid and brightness scale. Play, pause, step, zoom and pan.
- **Blink and difference views:** flip between any two visits, or subtract one from another — a moving object shows up half black, half white, and a changing one glows all over. A sum of all six detectors (0.75–5.0 µm) is available for the saved targets.
- **Spectrum on the fly:** every image sees the target at its own wavelength, so measuring the target in each image gives a spectrum from 0.75 to 5 µm, plus a brightness-over-time light curve.
- **Context around the image:** expected position from catalogue proper motion, a Gaia DR3 overlay moved to each visit's date, contamination and saturation flags per visit, and the same sky from 2MASS, WISE and DSS via Aladin Lite.

## Test targets

The viewer ships with pre-computed data for the five challenge test targets — they play instantly, in any of the six wavelength bands, and can be opened from the gallery or by deep link:

| Target | Notes |
|---|---|
| Barnard's Star | Fast-moving nearby star |
| Epsilon Indi B | Brown dwarf in a nearby system |
| WISE 0855−0714 | The coldest known brown dwarf |
| RW Aurigae | Variable young star |
| R Draconis | Variable star |

Any other position is computed on demand by the live-query service.

## Run it locally

Static viewer (no installation, any web server):

```bash
python -m http.server 8502 --directory docs
# then open http://localhost:8502
```

Live-query backend for other sky positions:

```bash
pip install -r api/requirements.txt
uvicorn api.main:app --port 8000
# the viewer calls it at /api; for local testing open the viewer as
# http://localhost:8502 and serve the API behind the same origin,
# or point CONFIG.api in docs/app.js at your local service
```

The Streamlit fallback viewer:

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Deployment

Deployed on Vercel: the static viewer is served from `docs/`, and the FastAPI live-query service runs as a serverless function from `api/main.py` (see `vercel.json`).

## Credits & Acknowledgements

This publication makes use of data products from the Spectro-Photometer for the History of the Universe, Epoch of Reionization and Ices Explorer (SPHEREx), which is a joint project of the Jet Propulsion Laboratory and the California Institute of Technology, and is funded by the National Aeronautics and Space Administration. Spectral images are served by the NASA/IPAC Infrared Science Archive (IRSA).

This work has made use of data from the European Space Agency (ESA) mission Gaia (https://www.cosmos.esa.int/gaia), processed by the Gaia Data Processing and Analysis Consortium (DPAC, https://www.cosmos.esa.int/web/gaia/dpac/consortium). Funding for the DPAC has been provided by national institutions, in particular the institutions participating in the Gaia Multilateral Agreement.

This software uses source code created at the Centre de Données astronomiques de Strasbourg, France. Names and motions come from SIMBAD through the CDS Sesame name resolver.

See [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) for third-party license information.

## License

MIT — see [LICENSE](LICENSE).
