FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/app

WORKDIR /app

COPY packages/agent-service/requirements.txt /app/requirements.txt
RUN pip install --upgrade pip && \
    pip install -r requirements.txt

# Копируем исходники агента без лишнего уровня вложенности
COPY packages/agent-service/src/agent_service /app/agent_service

ENV AGENT_PORT=8100 \
    LOG_LEVEL=INFO
EXPOSE 8100

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD ["python", "-c", "import os,sys,urllib.request;port=os.getenv('AGENT_PORT','8100');url='http://127.0.0.1:%s/health'%port; \
import urllib.error; \
try:\n resp=urllib.request.urlopen(url, timeout=3); sys.exit(0 if getattr(resp,'status',500)==200 else 1)\nexcept Exception:\n sys.exit(1)"]

CMD ["uvicorn", "agent_service.server:app", "--host", "0.0.0.0", "--port", "8100"]
