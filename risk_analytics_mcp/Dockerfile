# Base image
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1
WORKDIR /app

# Install dependencies
COPY pyproject.toml README.md /app/
COPY moex_iss_mcp /app/moex_iss_mcp
COPY risk_analytics_mcp /app/risk_analytics_mcp
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir .

# Default environment
ENV RISK_MCP_PORT=8010
EXPOSE 8010

CMD ["python", "-m", "risk_analytics_mcp.main"]
