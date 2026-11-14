# Dokdo Gull (독도괭이갈매기)

A public web tool that shows how a patch of sky changes over time in images from NASA's SPHEREx mission.
Built for the 2026 NASA Space Apps Challenge, ["Planet X and SPHEREx"](https://www.spaceappschallenge.org/2026/challenges/planet-x-and-spherex/).

Enter a sky position (Right Ascension and declination) or an object name. The tool finds every SPHEREx
spectral image that covers that position, combines the images taken during each visit, and plays the
visits back like a short video so that moving or changing objects stand out.

## Run it locally

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Data

- SPHEREx spectral images (Level 2) from the NASA/IPAC Infrared Science Archive (IRSA), found through
  the IRSA TAP service and downloaded as cutouts. The query is not tied to one data release, so newly
  released images are picked up automatically.

## Plan

The project plan, build order and current status are in [docs/PLAN.md](docs/PLAN.md).

## Use of AI tools

The source code in this repository was generated with Claude (Anthropic), running in Claude Code, at
the direction of the team. Every AI-generated file starts with a comment that says so, and commits made
with the AI carry a `Co-Authored-By: Claude` trailer. A dated record is kept in
[docs/ai-usage-log.md](docs/ai-usage-log.md).

## License

MIT. See [LICENSE](LICENSE).
