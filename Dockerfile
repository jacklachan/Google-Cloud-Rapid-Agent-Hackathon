# Faultline server image (the agent + FastAPI + static web console).
#
# Deploy with:
#   bash deploy_server_cloudrun.sh
#
# We need Node.js available at runtime because the GitLab MCP server runs as
# a child process via `npx -y @zereight/mcp-gitlab` (see agent/tools_gitlab.py).
# Slim Python base + NodeSource setup keeps the image small (~250 MB).

FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PORT=8080 \
    NPM_CONFIG_UPDATE_NOTIFIER=false \
    NPM_CONFIG_FUND=false

WORKDIR /app

# Node.js 22.x via NodeSource.
RUN apt-get update \
 && apt-get install -y --no-install-recommends curl ca-certificates gnupg \
 && curl -fsSL https://deb.nodesource.com/setup_22.x | bash - \
 && apt-get install -y --no-install-recommends nodejs \
 && apt-get clean \
 && rm -rf /var/lib/apt/lists/*

# Pre-warm the GitLab MCP server in the image so the first request does not
# pay the npm-install cost. `--help` exits cleanly without needing a token.
RUN npx -y @zereight/mcp-gitlab --help >/dev/null 2>&1 || true

COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

COPY agent /app/agent
COPY server /app/server
COPY web /app/web

EXPOSE 8080

# Single-worker uvicorn — SSE fan-out + in-memory rollback registry are
# per-process.
CMD ["sh", "-c", "uvicorn server.main:app --host 0.0.0.0 --port ${PORT} --workers 1"]
