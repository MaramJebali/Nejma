# CHANGELOG — nejma

## 2026-11-15 — public-release preparation (cleanup, README, deploy config)

- Scanned the tree for upstream branding/attribution strings; removed every
  public-facing reference (viewer footer, app config, API responses,
  User-Agent, Streamlit titles, project docs). Reasoning: the MIT license
  requires only the LICENSE file and per-file copyright notices — no
  promotional attribution.
- Kept `LICENSE` unmodified and all per-file headers intact. Reasoning:
  legally required.
- Added `THIRD_PARTY_NOTICES.md` with the MIT text and the SPHEREx / Gaia /
  CDS acknowledgements + Aladin Lite (LGPL-3.0) notice. Reasoning:
  data-provider requirements.
- Replaced the footer with a "Credits & acknowledgements" section carrying
  the required notices. Reasoning: same.
- Removed the original project's own docs (`docs/PLAN.md`,
  `docs/submission.md`, `docs/ai-usage-log.md`). Reasoning: they are the
  upstream team's internal documents, not part of Nejma.
- `docs/app.js`: `CONFIG.api` now points at the same-origin `/api` service;
  Streamlit fallback neutralised. Reasoning: deployment on Vercel.
- `api/main.py`: CORS opened (`*`) for the deployment domain, brand-neutral
  responses, added a `/health` endpoint. Reasoning: deployment verification.
- `spherex/archive.py`: neutral User-Agent. Reasoning: public release.
- Logo integration wired into the landing page and viewer header
  (`assets/nejma-logo.jpg` served from `docs/assets/`, with a graceful
  text-only fallback if the file is absent).
- Added `vercel.json` (static `docs/**` + Python function `api/main.py`,
  query-string-preserving routes). Reasoning: Vercel deployment.

## 2026-11-15 — initial build history

All dates 2026-11-15. The upstream viewer was received under the MIT license
(see LICENSE and THIRD_PARTY_NOTICES.md; the repository does not carry
promotional references to upstream projects).
"nejma" is the presentation identity; all functional ids of the original
viewer are preserved so `app.js` logic could be reused nearly unchanged.

## Presentation layer (Phase 3 — template integration)

- **`docs/index.html`** — rebuilt page:
  - Added `#landing` full-screen intro (eyebrow, title *nejma*, tagline,
    **Start exploring** button, deep-link hint) with the film-engine
    background of the landing page.
  - Added `#nejma-nav` glass capsule navbar (pinned
    top-right) with sections: Viewer / Spectrum / The sky / Targets / How,
    mapped to `#sec-viewer`, `#sec-data`, `#sec-sky`, `#sec-targets`,
    `#sec-about`. Scroll-based with IntersectionObserver active states.
  - Added `#universe-bg` fixed container for the living starfield backdrop
    (the film's ending frame).
  - Added an **import map** so the ES-module film engine
    (`three`, `gsap`, `lenis`, three.js postprocessing addons) loads from
    esm.sh without any build step — GitHub-Pages compatible.
  - Wordmark/title changed to *nejma*; every functional element id from the
    original viewer kept verbatim (search, plate, transport, ruler,
    overlays, charts, aladin, gallery, visits, notice…).
  - The Work/projects section design was deliberately NOT
    used (per instruction).
- **`docs/theme.css`** (new) — violet-glass cosmic skin over `style.css`:
  glass panels, violet primary buttons, capsule navbar, landing styles,
  glassy charts/tables. Detector tints and data-overlay colours
  (amber/gaia/fast/sat) left untouched because they carry meaning.
- **`docs/universe.js`** (new) — landing / navbar / backdrop orchestration:
  - Landing background = film's opening keyframe (warm lone star).
  - Start → fade into universe view, mount finale background, remember
    choice in `sessionStorage`.
  - Skips landing automatically for deep links (`?target=`/`?q=`/`?ra=`)
    and `?embed=1` so shared links land straight in the viewer.
  - Navbar brand returns to the landing screen.
- **`docs/long-way-home/lwh-main.js`** (new) — verbatim port of the
  film engine with:
  - import specifiers resolved via the page import map (was npm),
  - a new exported `mountStaticBackground(container, frame)` used by the
    landing screen (scene parked at one keyframe, animating in place,
    pointer parallax, visibility-aware, fully disposable).
- **`docs/app.js`** — one-line change: page title brand → "nejma". No other behaviour touched.

## Features added (Phase 4)

- **Detector summation (Σ all six detectors)** — the challenge's
  "summing detector arrays" consideration:
  - New checkbox "Sum all six detectors" in the detector control.
  - `buildSummedView()` in `app.js` loads the six saved detector JSONs,
    matches visits date-by-date (±5 days), averages pixels into a
    0.75–5.0 µm broadband composite on the shared 3″ grid, unions the
    saturation masks, merges per-visit flags, and averages markers/
    centroids.
  - Works in every mode (time-lapse / blink / difference / stack), is
    cached per target, and is deep-linkable: `?target=R%20Dra&band=sum`.
  - Captions, visits table note, ruler state and URL sync all handle the
    summed view.
  - **Limitation (documented in-UI):** live queries from the FastAPI
    service are per-detector, so summation is available for the five
    saved test targets. Extending it server-side would need multi-band
    stacking in `api/main.py`.
- **First-visit onboarding** — one dismissible tip explaining play/diff/
  detector selection (remembered in `sessionStorage`).
- Graceful fetch handling was already strong in the original (progress
  notices, retry/backoff in `spherex/archive.py`, Streamlit fallback link);
  unchanged.

## Kept as backup (per decision)

- `app.py` (Streamlit v1 viewer) is untouched and still works; remove it
  once the new UI is validated end-to-end.

## Known caveats

- The WebGL backdrops require WebGL; with `prefers-reduced-motion` the
  landing shows a static dark screen and the universe has no starfield —
  all functionality unaffected.
- Aladin Lite logging endpoint (alasky) may fail under some networks; the
  viewer already degrades gracefully without it.
- Detector "summation" is an average of surface brightness across bands
  (a broadband composite), not a physical spectrum sum.
