FROM python:3.13-slim-bookworm

RUN apt-get update && apt-get install -y --no-install-recommends \
    supervisor \
    && rm -rf /var/lib/apt/lists/*

RUN pip install uv

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv sync --no-dev --frozen

COPY src/ src/
COPY app.py chainlit.md ./
COPY .chainlit/ .chainlit/
COPY supervisord.conf ./

EXPOSE 8000

CMD ["supervisord", "-c", "/app/supervisord.conf"]
