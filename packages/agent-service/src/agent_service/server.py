"""
HTTP-адаптер для `moex-market-analyst-agent`.

Поднимает FastAPI-приложение с эндпоинтами:
- GET /health — проверка готовности контейнера;
- POST /a2a   — прием A2A-запроса и проксирование в OrchestratorAgent.

Запускается командой:
uvicorn agent_service.server:app --host 0.0.0.0 --port ${AGENT_PORT:-8100}
"""

from __future__ import annotations

import logging
import os

from fastapi import FastAPI, HTTPException

from agent_service.core import SubagentRegistry
from agent_service.orchestrator.models import A2AInput
from agent_service.orchestrator.orchestrator_agent import OrchestratorAgent
from agent_service.subagents.dashboard import DashboardSubagent
from agent_service.subagents.explainer import ExplainerSubagent
from agent_service.subagents.market_data import MarketDataSubagent
from agent_service.subagents.risk_analytics import RiskAnalyticsSubagent

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=LOG_LEVEL,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def _build_registry() -> SubagentRegistry:
    """Инициализировать реестр сабагентов с дефолтными зависимостями."""
    registry = SubagentRegistry()
    registry.register(MarketDataSubagent())
    registry.register(RiskAnalyticsSubagent())
    registry.register(DashboardSubagent())
    registry.register(ExplainerSubagent())
    return registry


def _build_orchestrator() -> OrchestratorAgent:
    """Создать экземпляр оркестратора с таймаутами из ENV."""
    default_timeout = float(os.getenv("AGENT_STEP_TIMEOUT_SECONDS", "30"))
    enable_debug = os.getenv("AGENT_ENABLE_DEBUG", "true").lower() in {"1", "true", "yes", "y"}
    registry = _build_registry()
    return OrchestratorAgent(
        registry=registry,
        default_timeout=default_timeout,
        enable_debug=enable_debug,
    )


app = FastAPI(
    title="moex-market-analyst-agent",
    version=os.getenv("AGENT_VERSION", "1.0.0"),
    description="A2A HTTP-адаптер мультиагентного оркестратора.",
)

# Ленивая инициализация, чтобы uvicorn reload не создавал дубликаты.
orchestrator_agent = _build_orchestrator()


@app.get("/health")
async def health() -> dict[str, str]:
    """Простой healthcheck для orchestrator-агента."""
    return {"status": "ok"}


@app.post("/a2a")
async def handle_a2a(a2a_input: A2AInput) -> dict[str, object]:
    """
    Обработать A2A-запрос в соответствии со спецификацией Evolution AI Agents.
    """
    try:
        output = await orchestrator_agent.handle_request(a2a_input)
        return {"output": output.model_dump()}
    except Exception as exc:  # pragma: no cover - внешняя защита
        logger.exception("A2A handler failed")
        raise HTTPException(
            status_code=500,
            detail=f"Internal error: {type(exc).__name__}: {exc}",
        ) from exc
