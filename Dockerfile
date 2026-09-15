FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    QUERYWEAVER_WEB_ROOT=/app/web \
    PORT=8000

WORKDIR /app

RUN addgroup --system queryweaver \
    && adduser --system --ingroup queryweaver --home /app queryweaver

COPY pyproject.toml README.md LICENSE ./
COPY src ./src
COPY web ./web
COPY scripts/container_entrypoint.py ./scripts/container_entrypoint.py

RUN python -m pip install --no-cache-dir ".[api]" \
    && chown -R queryweaver:queryweaver /app

USER queryweaver

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
  CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:' + __import__('os').environ.get('PORT', '8000') + '/health', timeout=2)"]

CMD ["python", "scripts/container_entrypoint.py"]
