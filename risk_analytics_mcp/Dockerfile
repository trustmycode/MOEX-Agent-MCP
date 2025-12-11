FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Копируем только нужные пакеты
COPY pyproject.toml /app/
COPY moex_iss_sdk /app/moex_iss_sdk
COPY risk_analytics_mcp /app/risk_analytics_mcp

RUN pip install --upgrade pip && \
    pip install .

ENV RISK_MCP_PORT=8010 \
    HOST=0.0.0.0
EXPOSE 8010

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD ["python", "-c", "import os,sys,urllib.request; port=os.getenv('RISK_MCP_PORT') or os.getenv('PORT','8010'); url=f'http://127.0.0.1:{port}/health'; sys.exit(0 if urllib.request.urlopen(url, timeout=3).status == 200 else 1)"]

CMD ["python", "-m", "risk_analytics_mcp.main"]
