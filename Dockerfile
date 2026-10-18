# One image, two apps: the API (app.asgi:app) and the relay (relay.asgi:app).
# docker-compose.yml picks which one each container runs via APP_MODULE.
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    APP_MODULE=app.asgi:app \
    PORT=8002 \
    HEALTH_PATH=/api/health \
    WS_MAX_SIZE=16777216

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY app ./app
COPY relay ./relay
COPY scripts ./scripts
RUN useradd --system --uid 10001 linkium && chown -R linkium /app
USER linkium

EXPOSE 8002 8003
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
  CMD python -c "import os,urllib.request; urllib.request.urlopen(f'http://127.0.0.1:{os.environ[\"PORT\"]}{os.environ[\"HEALTH_PATH\"]}', timeout=4)"

# One worker on purpose: WebSocket pairing state lives in process memory.
# --no-proxy-headers: both apps read the client IP from the X-Forwarded-For entry
# nginx appended (TRUSTED_PROXY_HOPS); uvicorn's own handling would trust the spoofable first entry.
CMD ["sh", "-c", "exec uvicorn ${APP_MODULE} --host 0.0.0.0 --port ${PORT} --workers 1 --no-proxy-headers --ws-ping-interval 30 --ws-ping-timeout 30 --ws-max-size ${WS_MAX_SIZE} --no-server-header"]
