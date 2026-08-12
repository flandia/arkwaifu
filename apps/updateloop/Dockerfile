FROM ghcr.io/astral-sh/uv:0.9.26 AS uv

FROM python:3.14.2-slim AS runtime

COPY --from=uv /uv /uvx /bin/

RUN apt-get update \
    && apt-get install --yes --no-install-recommends ca-certificates git \
    && rm -rf /var/lib/apt/lists/*

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

WORKDIR /app

COPY pyproject.toml uv.lock README.md ./
RUN uv sync --locked --no-dev --no-install-project

COPY src ./src
RUN uv sync --locked --no-dev

RUN useradd --create-home --uid 10001 updateloop
RUN install -d -o updateloop -g updateloop /app/.cache
USER 10001

ENTRYPOINT ["/app/.venv/bin/updateloop"]
CMD ["run"]
