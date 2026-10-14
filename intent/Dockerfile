# TASK-0010 supplies the package, lock, entrypoint and verified model bundle.
ARG PYTHON_IMAGE
ARG UV_IMAGE
FROM ${UV_IMAGE} AS uv
FROM ${PYTHON_IMAGE} AS runtime
COPY --from=uv /uv /usr/local/bin/uv
WORKDIR /app/intent
# TOKENIZERS_PARALLELISM is a boolean; no credentials are baked into this image.
# hadolint ignore=DL3064
ENV UV_PYTHON_DOWNLOADS=never UV_LINK_MODE=copy PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 \
    HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 HF_HUB_DISABLE_TELEMETRY=1 \
    OMP_NUM_THREADS=2 TOKENIZERS_PARALLELISM=false LAYA_MODEL_PATH=/app/intent/model
COPY intent/pyproject.toml intent/uv.lock ./
RUN uv sync --frozen --no-dev --no-cache --no-install-project
COPY intent/ ./
COPY deploy/verify_model.py /app/verify_model.py
RUN python /app/verify_model.py /app/intent/model \
 && .venv/bin/python -c "import intent_service.app"
USER 65532:65532
EXPOSE 8003
STOPSIGNAL SIGTERM
ENTRYPOINT ["/app/intent/.venv/bin/uvicorn", "intent_service.app:app", "--host", "0.0.0.0", "--port", "8003", "--no-access-log", "--workers", "1", "--timeout-graceful-shutdown", "7"]
