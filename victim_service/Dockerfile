# Victim service Dockerfile. One image, three roles (SERVICE_NAME env switches).
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PORT=8080

WORKDIR /app

# Install only the runtime deps the victim needs. Subset of the repo's
# top-level requirements.txt to keep the image small.
COPY victim_service/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

COPY victim_service /app/victim_service

EXPOSE 8080

# Single CMD; SERVICE_NAME (frontend|auth|data) picks which app gets served.
CMD ["sh", "-c", "uvicorn victim_service.main:app --host 0.0.0.0 --port ${PORT}"]
