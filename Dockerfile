FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN useradd --create-home --uid 10001 botuser

COPY pyproject.toml README.md ./
COPY bot ./bot

RUN pip install --upgrade pip && pip install .

RUN mkdir -p /app/data && chown -R botuser:botuser /app
USER botuser

CMD ["python", "-m", "bot"]
