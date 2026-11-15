# AI-generated code: written with Claude (Anthropic) at the team's direction for NASA Space Apps 2026.
# Dockerfile for the Hugging Face Space that hosts the live-query service. The Space holds only this file and
# README.md; the code itself is fetched from GitHub when the image is built. To pick up new code, use
# "Factory rebuild" in the Space's settings.
FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends git && rm -rf /var/lib/apt/lists/*
RUN useradd -m -u 1000 user
USER user
ENV HOME=/home/user \
    PATH=/home/user/.local/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    DOKDO_GULL_CACHE=/tmp/dokdo-gull-cache

WORKDIR /home/user/app
RUN git clone --depth 1 https://github.com/cafe2913/dokdo-gull.git .
RUN pip install --no-cache-dir --user -r api/requirements.txt

EXPOSE 7860
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "7860"]
