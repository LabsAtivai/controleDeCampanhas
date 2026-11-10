FROM ghcr.io/astral-sh/uv:0.8.22 AS uv
FROM python:3.12-slim
COPY --from=uv /uv /usr/local/bin/uv
ENV PYTHONUNBUFFERED=1 PYTHONIOENCODING=utf-8 TZ=America/Sao_Paulo UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv UV_NATIVE_TLS=true UV_HTTP_TIMEOUT=120 uv sync --frozen --no-dev --no-install-project
COPY . .
RUN groupadd --gid 10001 app && useradd --uid 10001 --gid app --create-home app
ENV PATH="/app/.venv/bin:$PATH"
USER app
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/ready', timeout=3)"
CMD ["python", "-m", "waitress", "--listen=0.0.0.0:8000", "--threads=8", "--call", "webapp:create_app"]
