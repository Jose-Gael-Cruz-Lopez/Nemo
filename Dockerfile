# Native Linux deployment: one public Next server and one loopback-only API.
# Build only from a clean, reviewed checkout; no credentials are build arguments.
FROM node:22-bookworm-slim AS dashboard-build
WORKDIR /build/dashboard
ENV NEXT_TELEMETRY_DISABLED=1 \
    NEXT_PUBLIC_API_BASE_URL="" \
    TIDEWARD_PUBLIC_SHOWCASE=false
COPY dashboard/package.json dashboard/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY dashboard/ ./
RUN npm run build

FROM python:3.12-slim-bookworm AS python-build
WORKDIR /build
COPY pyproject.toml ./
# Resolve native dependencies independently of frequently changing application
# sources. No private pip configuration or provider credentials enter this stage.
RUN python -c 'import pathlib,tomllib; project=tomllib.loads(pathlib.Path("pyproject.toml").read_text())["project"]; dependencies=project["dependencies"]+project["optional-dependencies"]["ocean"]+project["optional-dependencies"]["sponsors"]; pathlib.Path("/tmp/nemo-runtime-requirements.txt").write_text("\n".join(dependencies)+"\n")' \
    && python -m venv /opt/venv \
    && /opt/venv/bin/pip install --no-cache-dir -r /tmp/nemo-runtime-requirements.txt
COPY README.md ./
COPY apps/ ./apps/
COPY adapters/ ./adapters/
RUN /opt/venv/bin/pip install --no-cache-dir --no-deps .

FROM python:3.12-slim-bookworm AS runtime
ARG SOURCE_REVISION=unknown
LABEL org.opencontainers.image.title="Nemo software demo" \
    org.opencontainers.image.revision="${SOURCE_REVISION}"
RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates git libglib2.0-0 libgomp1 libstdc++6 \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --gid 10001 nemo \
    && useradd --uid 10001 --gid 10001 --no-create-home nemo \
    && mkdir -p /app /data/nemo /opt/nemo-public-seed \
    && chown nemo:nemo /app /data/nemo /opt/nemo-public-seed
COPY --from=dashboard-build /usr/local/bin/node /usr/local/bin/node
COPY --from=python-build /opt/venv /opt/venv
WORKDIR /app
# Readers verify exact source/test/provenance bytes; do not trim this to JSON alone.
COPY --chown=nemo:nemo pyproject.toml README.md ./
COPY --chown=nemo:nemo apps/ ./apps/
COPY --chown=nemo:nemo adapters/ ./adapters/
COPY --chown=nemo:nemo scripts/ ./scripts/
COPY --chown=nemo:nemo tests/ ./tests/
COPY --chown=nemo:nemo config/ ./config/
COPY --chown=nemo:nemo data/public/ ./data/public/
COPY --chown=nemo:nemo data/research/ ./data/research/
COPY --chown=nemo:nemo data/current_fields/ ./data/current_fields/
COPY --chown=nemo:nemo data/sample_runs/ ./data/sample_runs/
COPY --chown=nemo:nemo docs/research-evidence/matched-current-metadata/ ./docs/research-evidence/matched-current-metadata/
COPY --chown=nemo:nemo docs/research-evidence/matched-current-v1-compatibility-diagnosis.json ./docs/research-evidence/
COPY --chown=nemo:nemo docs/matched-current-v2-amendment.md ./docs/
COPY --chown=nemo:nemo deploy/ ./deploy/
# Standalone server avoids loading/transpiling next.config.ts during startup.
# Next intentionally omits public/static from this output; ship both explicitly.
COPY --from=dashboard-build --chown=nemo:nemo /build/dashboard/.next/standalone/ ./dashboard/
COPY --from=dashboard-build --chown=nemo:nemo /build/dashboard/public/ ./dashboard/public/
COPY --from=dashboard-build --chown=nemo:nemo /build/dashboard/.next/static/ ./dashboard/.next/static/
ENV PATH="/opt/venv/bin:/usr/local/bin:/usr/bin:/bin" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    GIT_CONFIG_NOSYSTEM=1 \
    GIT_CONFIG_GLOBAL=/dev/null \
    GIT_CONFIG_COUNT=1 \
    GIT_CONFIG_KEY_0=safe.directory \
    GIT_CONFIG_VALUE_0=/app \
    REEFTRACE_DATA_DIR=/data/nemo \
    REEFTRACE_CLOUD_SEED_DIR=/opt/nemo-public-seed \
    PHOTON_ENABLED=false \
    GROK_VOICE_ENABLED=false \
    PORT=8080
USER nemo
# Compute only the existing three PUBLIC SYNTHETIC source fixtures once at build
# time, never ocean first-score. No build/runtime credentials reach this process.
RUN timeout --signal=TERM --kill-after=5s 300s env -i \
    PATH="/opt/venv/bin:/usr/local/bin:/usr/bin:/bin" \
    PYTHONPATH="/app/apps/api:/app" PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 \
    PYTHON_DOTENV_DISABLED=1 CHALK_ENABLED=false PHOTON_ENABLED=false GROK_VOICE_ENABLED=false \
    python -m deploy.seed_demo --output-dir /opt/nemo-public-seed
# A frozen saved-result reader indirectly resolves git HEAD. This NEW checkpoint
# contains only the allowlisted deployed bytes; it is not the historical protocol
# checkpoint. Never copy the developer's .git, remotes, config, or old history.
RUN git init --quiet --initial-branch=runtime \
    && git add pyproject.toml README.md apps adapters scripts tests config data docs deploy \
    && git -c user.name="Nemo image checkpoint" -c user.email="runtime@invalid" \
       commit --quiet -m "Sanitized image source checkpoint; historical research provenance unchanged"
# COPY may create root-owned parent directories. Lock sources as root, then drop
# privileges again; the app user cannot undo their ownership or replace /app.
USER root
RUN chown -R root:root apps adapters scripts tests config data docs deploy .git /opt/nemo-public-seed \
    && chown root:root /app pyproject.toml README.md \
    && chmod -R a-w apps adapters scripts tests config data docs deploy .git /opt/nemo-public-seed \
    && chmod a-w pyproject.toml README.md
RUN chmod a-w /app
USER nemo
EXPOSE 8080
# The hosting platform probes /api/v1/health externally. A second Python process
# is unnecessary and can exceed a 512 MB budget under CPU emulation.
HEALTHCHECK NONE
CMD ["python", "deploy/start.py"]
