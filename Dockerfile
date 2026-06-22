FROM python:3.13-slim-bookworm

RUN pip install uv

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv sync --no-dev --frozen

COPY src/ src/
COPY frontend/ frontend/
COPY .chainlit/ .chainlit/
COPY supervisord.conf ./

EXPOSE 8000 8001

CMD ["supervisord", "-c", "/app/supervisord.conf"]
