# AI-generated code: written with Claude (Anthropic) at the team's direction for NASA Space Apps 2026.
# Image for the live-query service (api/main.py). The viewer itself is static and lives in docs/.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    DOKDO_GULL_CACHE=/tmp/dokdo-gull-cache

WORKDIR /app
COPY api/requirements.txt api/requirements.txt
RUN pip install --no-cache-dir -r api/requirements.txt
COPY spherex spherex
COPY api api

# Hugging Face Spaces expects port 7860; Render and similar hosts pass PORT.
EXPOSE 7860
CMD ["sh", "-c", "uvicorn api.main:app --host 0.0.0.0 --port ${PORT:-7860}"]
