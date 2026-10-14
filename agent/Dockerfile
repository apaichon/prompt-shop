ARG PYTHON_IMAGE
ARG UV_IMAGE
FROM ${UV_IMAGE} AS uv
FROM ${PYTHON_IMAGE} AS runtime
COPY --from=uv /uv /usr/local/bin/uv
WORKDIR /app/agent
ENV UV_PYTHON_DOWNLOADS=never UV_LINK_MODE=copy PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
COPY agent/pyproject.toml agent/uv.lock ./
RUN uv sync --frozen --no-dev --no-cache --no-install-project
COPY agent/ ./
# Missing TASK-0010 adapter is a build failure, not a mock classifier.
RUN test -s tools/intent.py && .venv/bin/python -c "import prompt_shop_live.app; import tools.intent"
USER 65532:65532
EXPOSE 8001
STOPSIGNAL SIGTERM
ENTRYPOINT ["/app/agent/.venv/bin/uvicorn", "prompt_shop_live.app:app", "--host", "0.0.0.0", "--port", "8001", "--no-access-log", "--ws-max-size", "65536", "--ws-max-queue", "1", "--timeout-graceful-shutdown", "7"]
