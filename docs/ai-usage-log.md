# AI usage log

This log records how AI ("Super Intelligence") tools were used, for the project submission form.
Tool: Claude (Anthropic), running in Claude Code on a team member's PC.

| Date (KST) | What the AI did |
|---|---|
| 2026-10-30 to 10-31 | Before the hackathon: read the challenge page with the team, explained why Stellarium is not a suitable code base, suggested a Python + Streamlit stack and an outline of the image processing, installed Python tools on the PC. No project code or data work was done. |
| 2026-11-14 | Read the published resources and submission rules. Queried the SPHEREx archive to check data availability for the five test targets. Wrote the repository skeleton and the English project plan (docs/PLAN.md). |
| 2026-11-14 | Wrote the viewer code (spherex/archive.py, resolve.py, process.py, render.py, app.py) and its tests. Checked the result on real Barnard's Star data: on a first try the processing masked the saturated star core; the masking rule was changed after looking at the raw pixels. |

Decisions made by the team, not by the AI: taking on this challenge, the project name, which optional
features to build (Gaia overlay, spectrum plot, contamination flags), and the content of the submission.
