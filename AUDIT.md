# nejma — scored audit against the "Planet X and SPHEREx" rubric

Baseline = the upstream MIT-licensed viewer as originally received (2026-11-15);
see LICENSE and THIRD_PARTY_NOTICES.md.
After = the re-skinned "nejma" build in `docs/`.

| # | Criterion | Weight | Before | Evidence (before) | After | Evidence (after) |
|---|---|---|---|---|---|---|
| 1 | Coordinate input (RA/Dec), validation | High | 5 Met | `#q` accepts name / decimal / sexagesimal; `spherex/resolve.py` | 5 | unchanged |
| 2 | Time-series "video"/blink display | High | 5 Met | app.js play/blink + speed + transport | 5 | unchanged |
| 3 | Moving-object visibility (diff/add/contrast) | High | 5 Met | diff & stack modes, gain, blur-before-subtract | 5 | unchanged; summed mode strengthens detection |
| 4 | Five test targets supported | High | 5 Met | `docs/data/*` all 5 × 6 detectors (verified) | 5 | verified again in new UI, incl. summed mode |
| 5 | 102-band handling / detector summation | Medium | 3 Partial | detector ruler D1–D6 only, no summation | **4.5** | Σ all-six-detectors composite; live queries remain per-detector (documented) |
| 6 | On-the-fly spectra | Medium | 4 Met | `spherex/spectrum.py` + spectrum chart | 4 | unchanged |
| 7 | Adjustable field of view | Medium | 4 Met | 3–18 arcmin, cutout fov×1.5 | 4 | unchanged |
| 8 | External overlays (Gaia/WISE/2MASS/DSS) | Medium | 5 Met | Gaia DR3 overlay; HiPS surveys via Aladin | 5 | unchanged |
| 9 | URL-queryable coordinates | Low–Med | 4 Met | target/ra/dec/fov/band/mode/embed | **5** | `?band=sum` deep link added; deep links skip landing automatically |
| 10 | Metadata / contamination flags | Low–Med | 3 Partial | per-visit flags table, saturation overlay | 3.5 | summed view merges flags + union saturation; onboarding clarifies reading of flags |
| 11 | Data update strategy | Low | 4 Met | release-agnostic TAP query | 4 | unchanged |
| 12 | UI/UX quality | Medium | 3 Partial | plain but responsive; monolithic page | **4.5** | full visual re-skin, landing narrative, glass navbar sections, onboarding tip |
| 13 | Accessibility / public usability | Low | 3 Partial | good aria, reduced-motion; no onboarding | **4.5** | onboarding tip, section navbar, skip-landing deep links, reduced-motion fallbacks |
| | **Total** | | **48 / 65** | | **56 / 65** | |

## Honest gaps remaining

- **Detector summation for live queries** (score 4.5, not 5): the FastAPI
  service stacks per detector; summing all six server-side would require
  multi-band grouping in `api/main.py` + heavier downloads. Implemented
  client-side for the five saved targets only, and the UI says so.
- **Finer band granularity** (individual spectral channels within a
  detector) would require reprocessing cutouts server-side; out of scope.
- **Streamlit v1** retained untouched as a fallback, to be removed after
  validation (per project decision).
