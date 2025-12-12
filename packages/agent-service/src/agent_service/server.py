"""
HTTP-адаптер для `moex-market-analyst-agent`.

Поднимает FastAPI-приложение с эндпоинтами:
- GET /health — проверка готовности контейнера;
- POST /a2a   — прием A2A-запроса и проксирование в OrchestratorAgent.

Запускается командой:
uvicorn agent_service.server:app --host 0.0.0.0 --port ${AGENT_PORT:-8100}
"""

from __future__ import annotations

import json
import logging
import os
import time
from pathlib import Path
from typing import Any, Optional
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from jsonschema import Draft7Validator
from pydantic import BaseModel, Field

from agent_service.core import SubagentRegistry
from agent_service.llm import build_evolution_llm_client_from_env
from agent_service.orchestrator.models import A2AInput
from agent_service.orchestrator.orchestrator_agent import OrchestratorAgent
from agent_service.subagents.dashboard import DashboardSubagent
from agent_service.subagents.explainer import ExplainerSubagent
from agent_service.subagents.market_data import MarketDataSubagent
from agent_service.subagents.research_planner import ResearchPlannerSubagent
from agent_service.subagents.risk_analytics import RiskAnalyticsSubagent

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=LOG_LEVEL,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)
def _resolve_root_dir() -> Path:
    """
    Найти корень репозитория, двигаясь вверх от текущего файла.

    Ориентиры:
    - docs/schemas/risk-dashboard.schema.json
    - директория docs/
    """
    current = Path(__file__).resolve()
    for parent in [current.parent, *current.parents]:
        if (parent / "docs" / "schemas" / "risk-dashboard.schema.json").exists():
            return parent
        if (parent / "docs").exists():
            return parent
    return current.parent


ROOT_DIR = _resolve_root_dir()
DASHBOARD_SCHEMA_PATH = ROOT_DIR / "docs" / "schemas" / "risk-dashboard.schema.json"

try:
    with DASHBOARD_SCHEMA_PATH.open("r", encoding="utf-8") as fp:
        DASHBOARD_SCHEMA = json.load(fp)
    DASHBOARD_VALIDATOR: Optional[Draft7Validator] = Draft7Validator(DASHBOARD_SCHEMA)
    logger.info("Risk dashboard schema loaded: %s", DASHBOARD_SCHEMA_PATH)
except Exception as exc:  # pragma: no cover - необязательная зависимость
    DASHBOARD_SCHEMA = None
    DASHBOARD_VALIDATOR = None
    logger.warning("Risk dashboard schema not loaded: %s", exc)


def _build_registry() -> SubagentRegistry:
    """Инициализировать реестр сабагентов с дефолтными зависимостями."""
    registry = SubagentRegistry()
    llm_client = build_evolution_llm_client_from_env()

    if llm_client:
        logger.info("ExplainerSubagent: EvolutionLLMClient включён")
    else:
        logger.info("ExplainerSubagent: LLM_API_KEY не задан, используется MockLLMClient")

    registry.register(ResearchPlannerSubagent(llm_client=llm_client))
    registry.register(MarketDataSubagent())
    registry.register(RiskAnalyticsSubagent())
    registry.register(DashboardSubagent())
    registry.register(ExplainerSubagent(llm_client=llm_client))
    return registry


def _build_orchestrator() -> OrchestratorAgent:
    """Создать экземпляр оркестратора с таймаутами из ENV."""
    default_timeout = float(os.getenv("AGENT_STEP_TIMEOUT_SECONDS", "30"))
    enable_debug = os.getenv("AGENT_ENABLE_DEBUG", "true").lower() in {"1", "true", "yes", "y"}
    plan_first_enabled = os.getenv("AGENT_PLAN_FIRST", "true").lower() in {"1", "true", "yes", "y"}
    planner_timeout = float(os.getenv("AGENT_PLANNER_TIMEOUT_SECONDS", "40"))
    registry = _build_registry()
    return OrchestratorAgent(
        registry=registry,
        default_timeout=default_timeout,
        enable_debug=enable_debug,
        plan_first_enabled=plan_first_enabled,
        planner_timeout_seconds=planner_timeout,
    )


app = FastAPI(
    title="moex-market-analyst-agent",
    version=os.getenv("AGENT_VERSION", "1.0.0"),
    description="A2A HTTP-адаптер мультиагентного оркестратора.",
)

# Ленивая инициализация, чтобы uvicorn reload не создавал дубликаты.
orchestrator_agent = _build_orchestrator()


class AguiMessage(BaseModel):
    id: Optional[str] = None
    role: str
    content: Any


class AguiRunInput(BaseModel):
    threadId: Optional[str] = None
    thread_id: Optional[str] = None
    runId: Optional[str] = None
    run_id: Optional[str] = None
    state: dict[str, Any] = Field(default_factory=dict)
    messages: list[AguiMessage] = Field(default_factory=list)
    tools: list[dict[str, Any]] = Field(default_factory=list)
    context: list[dict[str, Any]] = Field(default_factory=list)


def _sse(event: dict[str, Any], event_name: Optional[str] = None) -> str:
    # SSE: каждая запись отделяется пустой строкой
    prefix = f"event: {event_name}\n" if event_name else ""
    return f"{prefix}data: {json.dumps(event, ensure_ascii=False)}\n\n"


def _now_ms() -> int:
    return int(time.time() * 1000)


def _validate_dashboard(payload: Any) -> tuple[bool, list[str]]:
    """Проверить dashboard по JSON Schema (если доступна)."""
    if not DASHBOARD_VALIDATOR or payload is None:
        return True, []

    to_validate: Any = _filter_dashboard(payload)
    errors = sorted(DASHBOARD_VALIDATOR.iter_errors(to_validate), key=lambda e: e.path)
    messages = []
    for err in errors:
        path = "/".join(map(str, err.path)) or "<root>"
        messages.append(f"{path}: {err.message}")
    return len(messages) == 0, messages


def _filter_dashboard(payload: Any) -> Any:
    """Оставить только поля, разрешённые схемой."""
    if not isinstance(payload, dict):
        return payload
    allowed_keys = {
        "version",
        "metadata",
        "layout",
        "metrics",
        "charts",
        "tables",
        "alerts",
        "data",
        "time_series",
    }
    return {k: v for k, v in payload.items() if k in allowed_keys}


def _filter_dashboard(payload: Any) -> Any:
    """Оставить только поля, разрешённые схемой."""
    if not isinstance(payload, dict):
        return payload
    allowed_keys = {
        "version",
        "metadata",
        "layout",
        "metrics",
        "charts",
        "tables",
        "alerts",
        "data",
        "time_series",
    }
    return {k: v for k, v in payload.items() if k in allowed_keys}


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


@app.post("/agui")
async def handle_agui(run_input: AguiRunInput):
    """
    AG-UI endpoint: принимает RunAgentInput и возвращает stream BaseEvent (SSE).
    Минимальный набор: RUN_STARTED -> TEXT_MESSAGE_* -> STATE_SNAPSHOT -> RUN_FINISHED / RUN_ERROR.
    """
    thread_id = run_input.threadId or run_input.thread_id or str(uuid4())
    run_id = run_input.runId or run_input.run_id or str(uuid4())

    # Берём последний user message как user_query
    user_query = ""
    for m in reversed(run_input.messages or []):
        if (m.role or "").lower() == "user":
            user_query = m.content if isinstance(m.content, str) else json.dumps(m.content, ensure_ascii=False)
            break

    async def gen():
        terminal_sent = False

        def send(event_type: str, payload: dict[str, Any]) -> str:
            nonlocal terminal_sent
            base = {
                "type": event_type,
                "threadId": thread_id,
                "runId": run_id,
                "timestamp": _now_ms(),
                **payload,
            }
            if event_type in {"RUN_FINISHED", "RUN_ERROR"}:
                terminal_sent = True
            return _sse(base, event_name=event_type)

        # lifecycle start
        yield send("RUN_STARTED", {"input": run_input.model_dump(mode="json")})

        if not user_query.strip():
            yield send("RUN_ERROR", {"message": "Empty user query"})
            return

        try:
            # A2AInput требует поле messages — формируем его из user_query
            a2a = A2AInput(
                messages=[{"role": "user", "content": user_query}],
                session_id=thread_id,
                locale=(run_input.state.get("locale") if isinstance(run_input.state, dict) else None) or "ru",
                user_role=(run_input.state.get("user_role") if isinstance(run_input.state, dict) else None) or "analyst",
                metadata={
                    "agui": {
                        "threadId": thread_id,
                        "runId": run_id,
                        "context": run_input.context,
                        "tools": run_input.tools,
                    },
                    # прокидываем parsed_params, если фронт их хранит в state
                    "parsed_params": (run_input.state.get("parsed_params") if isinstance(run_input.state, dict) else {}) or {},
                },
            )

            output = await orchestrator_agent.handle_request(a2a)
            payload = output.model_dump(mode="json")

            # assistant text message events
            msg_id = str(uuid4())
            text = payload.get("text") or payload.get("error_message") or "Агент не вернул текст."

            yield send("TEXT_MESSAGE_START", {"messageId": msg_id, "role": "assistant"})
            yield send("TEXT_MESSAGE_CONTENT", {"messageId": msg_id, "delta": text})
            yield send("TEXT_MESSAGE_END", {"messageId": msg_id})

            # state snapshot: dashboard/tables/debug (если есть)
            dashboard_payload = _filter_dashboard(payload.get("dashboard"))
            valid_dashboard, validation_errors = _validate_dashboard(dashboard_payload)
            snapshot = {
                "dashboard": dashboard_payload,
                "tables": payload.get("tables"),
                "debug": payload.get("debug"),
                "status": payload.get("status"),
                "schema_valid": valid_dashboard,
            }
            if validation_errors:
                snapshot["schema_errors"] = validation_errors

            yield send("STATE_SNAPSHOT", {"snapshot": snapshot})

            # terminal success
            yield send("RUN_FINISHED", {})
        except Exception as exc:  # pragma: no cover - внешняя защита
            logger.exception("AG-UI handler failed")
            yield send("RUN_ERROR", {"message": f"{type(exc).__name__}: {exc}"})
        finally:
            if not terminal_sent:
                yield send("RUN_ERROR", {"message": "Stream closed without terminal event"})

    headers = {
        "Cache-Control": "no-cache, no-transform",
        "Connection": "keep-alive",
        "Content-Type": "text/event-stream; charset=utf-8",
    }
    return StreamingResponse(gen(), media_type="text/event-stream; charset=utf-8", headers=headers)
