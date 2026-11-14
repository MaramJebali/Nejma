# Dokdo Gull: project plan

*This document was drafted with Claude (Anthropic) from the team's decisions and from measurements made on November 14, 2026.*

## What we are building

A public web tool for the NASA Space Apps 2026 challenge
["Planet X and SPHEREx"](https://www.spaceappschallenge.org/2026/challenges/planet-x-and-spherex/).
A user enters a sky position (Right Ascension and declination) or an object name, and the tool plays the
SPHEREx images of that patch of sky in time order, like a short video, so that moving or changing objects
stand out.

The challenge asks us to test it on Barnard's Star, Epsilon Indi B, WISE 0855, RW Aurigae and R Draconis.

## Current status (November 14)

- Done: public repository, a starter Streamlit app that runs locally, README, license, this plan.
- Not started: everything under "Build order" from step 3 onward. There is no data or image code yet.

## Team decisions

- Name: Dokdo Gull (독도괭이갈매기).
- Basic features: coordinate or name input, time-ordered animation, image subtraction, coordinates in the
  URL, choice of field of view.
- Extra features, in this order: contamination flags, Gaia star overlay, spectrum plot.
- Stack: Python with Streamlit, astropy and reproject.

## Submission rules we must follow

- Deadline: **Sunday, November 15, 11:59 p.m.** local time of the team's Local Event. Someone must click
  "Submit for Judging". Re-submitting before the deadline is allowed.
- The project page and everything linked from it must be **in English**.
- The demo is a video of **30 seconds or less** or a deck of **7 slides or fewer**. Going over makes the
  project ineligible for global judging.
- Links must open without a login. No faces or voices of anyone under 18.
- We must use NASA data (SPHEREx from IRSA) and list every dataset, tool and code source under References.
- AI rules: AI tools may be used to write code, but not to come up with the idea of how to solve the
  challenge. AI-generated code must be labelled in text and metadata. We label it in the README, in a
  comment at the top of each source file, in commit trailers and in `docs/ai-usage-log.md`.
- All team members must be registered for the same Local Event as the team. The team page currently shows
  "Team is Award Ineligible" because the owner's Local Event does not match the team's. This has to be
  fixed before we submit.

## What we measured in the SPHEREx archive

| Item | Result |
|---|---|
| Images per target | Barnard 363, WISE 0855 258, eps Indi 460, RW Aur 335, R Dra 2,493 |
| Observing pattern | 3 to 4 visits about six months apart, about 19 images per detector per visit. R Dra is observed almost continuously |
| Time span | May 2025 to October 2026 (13 to 17 months) |
| Size of the motion | Pixel scale 6.13". Barnard's Star moves about 2 pixels, eps Indi B and WISE 0855 about 1 pixel |
| Archive query (TAP) | 18 to 44 seconds per query |
| Cutout download | About 4 MB and 8 to 13 seconds per image, occasional HTTP 503. A larger field of view does not take longer |
| Four parallel downloads | 8 images in 40 seconds, no failures |
| Releases | `dr1` and `qr3` come back together with no duplicates |
| CORS | No CORS header, so a browser cannot fetch the images directly. A Python server has to |
| Flags | Bit names are in the FLAGS header (`MSKN####`, `MSKM####`). The `SOURCE` bit is set on almost every pixel, so "non-zero means bad" is wrong |
| Wavelength | Different in every image, even at the same sky position |
| Gaia DR3 | Available from the IRSA TAP table `gaia_dr3_source` (about 20 seconds) |
| Name lookup | Using year-2000 coordinates puts Barnard's Star 4.6' away from where it is now |

Because the motion is only 1 to 2 pixels, image subtraction is a basic feature, not an optional one.

## Files

```
app.py                     Streamlit page and URL parameters
spherex/archive.py         archive query, cutout download with retries, cache
spherex/resolve.py         name and coordinate parsing, proper motion
spherex/process.py         visit grouping, masking, background removal, reprojection, stacking
spherex/render.py          brightness scaling, frames, difference images, GIF
spherex/gaia.py            Gaia DR3 query and positions at each epoch
spherex/spectrum.py        photometry and wavelength at a position
scripts/build_showcase.py  precompute the five test targets
data/showcase/             precomputed frames (small files, kept in the repository)
tests/                     tests for the pure functions
docs/                      this plan, AI usage log, submission worksheet
```

## How the data is processed

1. **Resolve the position.** Coordinates are parsed directly. Names are looked up, and the proper motion
   is applied to move the position to 2026.0.
2. **Query.** IRSA TAP at `https://irsa.ipac.caltech.edu/TAP/sync`, results cached on disk.
   ```sql
   SELECT a.uri, p.energy_bandpassname, p.time_bounds_lower
   FROM spherex.artifact a JOIN spherex.plane p ON a.planeid = p.planeid
   WHERE 1 = CONTAINS(POINT('ICRS', {ra}, {dec}), p.poly)
   ORDER BY p.time_bounds_lower
   ```
   The query names no data release, so new releases are included automatically.
3. **Download.** `https://irsa.ipac.caltech.edu/{uri}?center={ra},{dec}d&size={deg}`, four at a time,
   up to four retries on 503 or timeout. The number of failures is shown to the user. We keep the IMAGE,
   FLAGS, VARIANCE and ZODI planes, the header and the wavelength, and drop the PSF table.
4. **Group into visits.** A gap of more than 20 days starts a new group. Groups longer than 60 days are
   split into bins of 30 days or less. A group with fewer than 3 images in a detector is skipped and
   reported. At most 24 images are used per group.
5. **Clean.** `IMAGE - ZODI`, then remove the remaining background of each image. Pixels with these flags
   are excluded at first: TRANSIENT, SUR_ERROR, NONFUNC, MISSING_DATA, HOT, COLD, OUTLIER, STREAK,
   SNOWBALL. The list will be adjusted after looking at real frames.
6. **Reproject.** Onto a grid centered on the target, north up, 3.0" per pixel (about twice the native
   sampling).
7. **Stack.** Median of each group, per detector. Stacking within one detector and one visit avoids
   comparing images taken at different wavelengths. Each frame records its date, image count and
   wavelength range.
8. **Display.** One brightness range for all frames, enlarged, with the date on each frame. Modes:
   animation, subtraction (each frame minus the first), and sum of everything. A GIF and a frame slider
   first; a player with play, speed and keyboard controls if time allows.

## Build order

Each step ends with a check, and is committed when it passes.

### Day 1 (November 14)
1. Skeleton: repository, starter app, local preview. **Done.**
2. Public GitHub repository. **Done.**
3. Deploy the empty app on Streamlit Community Cloud and confirm the public address opens.
4. Data layer: `archive.py`, `resolve.py`, tests. Check: 62 images of Barnard's Star (detector 2) are
   downloaded and cached. Then start pre-downloading the five test targets in the background.
5. Processing and display: `process.py`, `render.py`, tests. Check: a synthetic star that was shifted on
   purpose comes back with the same shift, and Barnard's Star gives three frames.
6. App: input, field of view, detector, the three modes, URL parameters (`?ra=&dec=&fov=&band=`), five
   presets. Check: Barnard's Star visibly moves, and subtraction shows a dark and bright pair.
   **This is the minimum finished product.**

### Day 2 (November 15)
7. Showcase: precomputed frames for the five targets, so they play instantly.
8. Contamination flags: names and fractions per frame, with an overlay.
9. Gaia overlay: predicted positions of Gaia DR3 stars at each epoch, high proper motion stars highlighted.
10. Spectrum plot: photometry at the target in all six detectors, by wavelength and by visit.
11. Finish: README, test record for the five targets, submission text.
12. Submit: first submission by 20:00, then updates until the deadline.

If time runs short we drop steps 10, 9 and 8, in that order. Steps 7, 11 and 12 stay.

## Open tasks for team members

- Write the submission text in English (`docs/submission.md`).
- Make the demo (30-second video or 7 slides).
- Test the five targets on the deployed site and take screenshots.
- Fix the Local Event mismatch on the team page.

To avoid edit conflicts, please tell the team before changing files under `spherex/` or
`app.py`.

## How we will check the result

| Target | Expected |
|---|---|
| Barnard's Star | Moves north by about 11" (2 pixels) between August 2025 and September 2026. The measured shift agrees with the Gaia prediction to within 0.5 pixel |
| Epsilon Indi B | Moves by about 1 pixel, visible in subtraction mode |
| WISE 0855 | Possibly visible only in detector 6 (4.4 to 5.0 µm). It may be too faint to see, and if so we will say so |
| RW Aurigae | Brightness differs between visits, seen in subtraction mode and in the spectrum |
| R Draconis | Brightness changes across the continuous coverage. Probably saturated, to be checked with the flags |

- Run `pytest` for visit grouping, flag masking, reprojection shift and coordinate parsing.
- Open the five presets and one arbitrary position, locally and on the deployed site.
- Open a URL with coordinates in a new tab and confirm the same view appears.
- Confirm that failed downloads and skipped visits are shown on the page.

## Risks

- **IRSA overload during the hackathon.** Retries, a disk cache, precomputed showcase data, and the AWS
  mirror of the same files as a fallback.
- **Arbitrary positions are slow (minutes).** Progress bar, one detector by default, a cap on images per
  visit.
- **Limits of the free hosting.** Test with the empty app first. Hugging Face Spaces is the fallback.
- **Motion of only 1 to 2 pixels.** Finer grid, subtraction mode, Gaia predicted positions.
