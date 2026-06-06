# Faultline server image (the agent + FastAPI + static web console).
#
# Deploy with:
#   bash deploy_server_cloudrun.sh
#
# Or test locally:
#   docker build -t faultline:dev .
#   docker run --rm -p 8080:8080 \
#     -e FAULTLINE_FAKE_AGENT=1 -e GITLAB_PROJECT_PATH=demo/x \
#     faultline:dev

FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PORT=8080

WORKDIR /app

COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

# Install the local source. We intentionally do not COPY the .env (which
# is gitignored and machine-local); Cloud Run injects env vars at deploy time.
COPY agent /app/agent
COPY server /app/server
COPY web /app/web

EXPOSE 8080

# Single-worker uvicorn is plenty for the demo and avoids SSE fan-out issues
# across workers (the in-memory rollback registry is per-process).
CMD ["sh", "-c", "uvicorn server.main:app --host 0.0.0.0 --port ${PORT} --workers 1"]
