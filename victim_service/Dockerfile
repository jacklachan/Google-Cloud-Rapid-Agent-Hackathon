# Victim service Dockerfile. Phase 1 fills CMD with the chosen entrypoint.
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Install only what the victim service needs (subset of repo requirements.txt).
COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

COPY victim_service /app/victim_service

# Cloud Run injects PORT at runtime.
ENV PORT=8080
EXPOSE 8080

# Phase 1 sets the real CMD once the service entrypoint exists.
CMD ["python", "-c", "raise SystemExit('victim_service entrypoint: implemented in phase 1')"]
