# =============================================================================
# Stage 1: UI Build
# =============================================================================
FROM node:22-alpine AS ui-build
WORKDIR /app/ui
COPY ui/ .
RUN npm install
RUN npm run build


# =============================================================================
# Stage 2: Runtime
#
# Caching strategy — COPY files in order of how rarely they change:
#
#   1. requirements files  (change rarely)  → venv layer cached until req changes
#   2. torch install       (change never)   → separate RUN so only re-runs if
#                                             requirements layer invalidated
#   3. app source code     (changes often)  → always re-copies but fast
#
# This means: editing Python source = only the final COPY re-runs (~5 sec)
# Adding a requirement = venv re-installs but torch is in same layer
# First build: ~10 min. Subsequent code-only rebuilds: ~30 sec.
# =============================================================================
FROM python:3.11-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    APP_HOME=/app \
    PORT=8000

WORKDIR ${APP_HOME}/core

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential curl netcat-openbsd \
    && rm -rf /var/lib/apt/lists/*

# ── Layer 1: requirements files (rarely change) ──────────────────────────────
COPY core/requirements.server.txt core/requirements-mcp.txt ./

# ── Layer 2: install ALL Python packages including torch ─────────────────────
# Torch and requirements are in ONE layer so cache is only broken when
# requirements.server.txt actually changes — not on every code edit.
RUN python -m venv venv \
    && ./venv/bin/python -m pip install --upgrade pip \
    && ./venv/bin/python -m pip install \
        --extra-index-url https://download.pytorch.org/whl/cpu \
        torch==2.4.1+cpu \
    && ./venv/bin/python -m pip install -r requirements.server.txt \
    && echo "Main venv ready"

# ── Layer 3: MCP venv (rarely changes) ───────────────────────────────────────
RUN python -m venv venv-mcp \
    && ./venv-mcp/bin/python -m pip install --upgrade pip \
    && ./venv-mcp/bin/python -m pip install -r requirements-mcp.txt \
    || echo "MCP venv install had warnings, continuing..."

# ── Layer 4: app source (changes often — only this layer re-runs) ────────────
COPY core/ .
COPY --from=ui-build /app/ui/dist/ ./src/flood_prediction/www/

# ── Layer 5: install app as editable package (fast) ──────────────────────────
RUN ./venv/bin/python -m pip install -e . \
    && ./venv-mcp/bin/python -m pip install -e . \
    || echo "MCP pip install -e had conflicts, continuing..."

EXPOSE 8000

RUN chmod +x ./docker-entrypoint.sh

ENTRYPOINT ["./docker-entrypoint.sh"]
