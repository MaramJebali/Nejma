---
title: Dokdo Gull live queries
emoji: 🔭
colorFrom: indigo
colorTo: yellow
sdk: docker
app_port: 7860
pinned: false
license: mit
---

Live-query service for [Dokdo Gull](https://cafe2913.github.io/dokdo-gull/), a time-lapse viewer for NASA SPHEREx
images built for the 2026 NASA Space Apps Challenge ("Planet X and SPHEREx").

The viewer plays its saved test targets without any server. For any other sky position it asks this service,
which downloads the SPHEREx cutouts from the NASA/IPAC Infrared Science Archive (IRSA), stacks them and returns
the frames.

Code: https://github.com/cafe2913/dokdo-gull (`api/main.py`). The code was written with AI assistance (Claude,
Anthropic) at the team's direction.
