"""
ResearchPlannerSubagent — LLM‑планировщик цепочки сабагентов.

Назначение:
- Принять пользовательский запрос и составить план вызовов сабагентов
  (market_data, risk_analytics, dashboard, knowledge, explainer).
- Вернуть план в строгом JSON-формате, пригодном для адаптации в ScenarioPipeline.

Соответствие задачам:
- TASK-2025-125 — реализация LLM-based планировщика.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Optional, Protocol

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from ..core.base_subagent import BaseSubagent
from ..core.context import AgentContext
from ..core.result import SubagentResult
from ..llm.client import EvolutionLLMClient, build_evolution_llm_client_from_env

logger = logging.getLogger(__name__)


class LLMClient(Protocol):
    """Протокол LLM-клиента, совместимый с EvolutionLLMClient и моком."""

    async def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.3,
        max_tokens: int = 800,
        **kwargs: Any,
    ) -> str:
        ...


class MockPlannerLLMClient:
    """
    Запасной мок для планировщика.

    Используется, если переменная окружения LLM_API_KEY не задана.
    """

    async def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.3,
        max_tokens: int = 800,
        **kwargs: Any,
    ) -> str:
        """Возвращает детерминированный минимальный план."""
        fallback_plan = {
            "reasoning": "Default fallback plan без внешнего LLM",
            "steps": [
                {
                    "subagent": "market_data",
                    "description": "Получить базовые рыночные данные по тикерам из запроса (если есть)",
                    "required": True,
                },
                {
                    "subagent": "explainer",
                    "description": "Сформировать текстовый ответ пользователю",
                    "required": True,
                },
            ],
        }
        return json.dumps(fallback_plan)


class PlannedStep(BaseModel):
    """Шаг плана, возвращаемый LLM."""

    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    subagent_name: str = Field(..., alias="subagent")
    description: str = Field(..., alias="description")
    required: bool = Field(default=True)
    tool_name: Optional[str] = Field(default=None, alias="tool")
    args: dict[str, Any] = Field(default_factory=dict, alias="args")
    depends_on: list[str] = Field(default_factory=list, alias="depends_on")
    timeout_seconds: Optional[float] = Field(default=None, alias="timeout_seconds")


class PlannerOutput(BaseModel):
    """Структурированный ответ планировщика."""

    model_config = ConfigDict(extra="ignore")

    reasoning: str
    steps: list[PlannedStep]


class ResearchPlannerSubagent(BaseSubagent):
    """
    Сабагент-планировщик, формирующий ExecutionPlan через LLM.
    """

    SUBAGENT_NAME = "research_planner"
    SUPPORTED_SUBAGENTS = {"market_data", "risk_analytics", "dashboard", "explainer", "knowledge"}
    MAX_STEPS = 5
    TIMEOUT_CAP_SECONDS = 60.0
    DASHBOARD_SCENARIOS = {
        "portfolio_risk",
        "cfo_liquidity",
        "issuer_compare",
        "securities_compare",
        "index_scan",
    }
    DEFAULT_DASHBOARD_TIMEOUT = 15.0
    FEW_SHOTS: list[str] = [
        # Анализ индекса
        '{"reasoning": "Анализ индекса: берём состав и отвечаем текстом", "steps": ['
        '{"subagent": "market_data", "tool": "get_index_constituents_metrics", "args": {"index_ticker": "IMOEX", "as_of_date": "2024-12-01"}, "depends_on": [], "description": "состав индекса", "required": true},'
        '{"subagent": "explainer", "tool": "generate_report", "args": {}, "depends_on": ["market_data"], "description": "текстовый ответ", "required": true}'
        ']}',
        # Портфельный риск
        '{"reasoning": "Портфель: сначала данные, затем риск и отчёт", "steps": ['
        '{"subagent": "market_data", "tool": "get_ohlcv_timeseries", "args": {"ticker": "SBER", "from_date": "2024-10-01", "to_date": "2024-12-01"}, "depends_on": [], "description": "получить цены портфеля", "required": true},'
        '{"subagent": "risk_analytics", "tool": "compute_portfolio_risk_basic", "args": {"positions": [{"ticker": "SBER", "weight": 0.5}, {"ticker": "GAZP", "weight": 0.5}], "from_date": "2024-10-01", "to_date": "2024-12-01"}, "depends_on": ["market_data"], "description": "расчёт риска", "required": true},'
        '{"subagent": "dashboard", "tool": "build_dashboard", "args": {}, "depends_on": ["risk_analytics"], "description": "собрать дашборд", "required": false},'
        '{"subagent": "explainer", "tool": "generate_report", "args": {}, "depends_on": ["risk_analytics"], "description": "итоговый текст", "required": true}'
        ']}',
        '{"reasoning": "Один тикер: берём snapshot и объясняем", "steps": ['
        '{"subagent": "market_data", "tool": "get_security_snapshot", "args": {"ticker": "SBER", "board": "TQBR"}, "depends_on": [], "description": "snapshot тикера", "required": true},'
        '{"subagent": "explainer", "tool": "generate_report", "args": {}, "depends_on": ["market_data"], "description": "итоговый текст", "required": true}'
        ']}',
        # Сравнение тикеров
        '{"reasoning": "Сравнение тикеров: считаем корреляции и объясняем", "steps": ['
        '{"subagent": "risk_analytics", "tool": "compute_correlation_matrix", "args": {"tickers": ["SBER", "GAZP"], "from_date": "2024-11-01", "to_date": "2024-12-01"}, "depends_on": [], "description": "корреляции", "required": true},'
        '{"subagent": "explainer", "tool": "generate_report", "args": {}, "depends_on": ["risk_analytics"], "description": "текстовый ответ", "required": true}'
        ']}',
        # Индекс: хвост по весу
        '{"reasoning": "Индекс: взять хвост по весу, получить цены за месяц и объяснить", "steps": ['
        '{"subagent": "market_data", "tool": "get_index_constituents_metrics", "args": {"index_ticker": "IMOEX", "as_of_date": "2024-12-01", "bottom_n": 5, "window_days": 30}, "depends_on": [], "description": "состав индекса и хвост", "required": true},'
        '{"subagent": "risk_analytics", "tool": "compute_tail_metrics", "args": {"ohlcv": []}, "depends_on": ["market_data"], "description": "метрики хвоста", "required": true},'
        '{"subagent": "explainer", "tool": "generate_report", "args": {}, "depends_on": ["risk_analytics"], "description": "итоговый вывод", "required": true}'
        ']}',
    ]
    TOOL_CATALOG: dict[str, list[dict[str, Any]]] = {
        "market_data": [
            {"tool": "get_security_snapshot", "required_args": ["ticker"], "optional_args": ["board"]},
            {"tool": "get_ohlcv_timeseries", "required_args": ["ticker", "from_date", "to_date"], "optional_args": ["interval", "board"]},
            {"tool": "get_index_constituents_metrics", "required_args": ["index_ticker"], "optional_args": ["as_of_date"]},
            {"tool": "get_security_fundamentals", "required_args": ["ticker"], "optional_args": []},
        ],
        "risk_analytics": [
            {"tool": "compute_portfolio_risk_basic", "required_args": ["positions"], "optional_args": ["from_date", "to_date", "rebalance"]},
            {"tool": "compute_correlation_matrix", "required_args": ["tickers"], "optional_args": ["from_date", "to_date"]},
            {"tool": "suggest_rebalance", "required_args": ["positions"], "optional_args": ["total_portfolio_value", "risk_profile"]},
            {"tool": "cfo_liquidity_report", "required_args": ["positions"], "optional_args": ["from_date", "to_date", "total_portfolio_value", "horizon_months", "base_currency"]},
            {"tool": "issuer_peers_compare", "required_args": ["ticker"], "optional_args": ["index_ticker", "sector", "peer_tickers", "max_peers", "as_of_date"]},
            {"tool": "compute_tail_metrics", "required_args": ["ohlcv"], "optional_args": ["constituents"]},
        ],
        "dashboard": [
            {"tool": "build_dashboard", "required_args": [], "optional_args": []},
        ],
        "knowledge": [
            {"tool": "search_knowledge", "required_args": ["query"], "optional_args": ["limit"]},
        ],
        "explainer": [
            {"tool": "generate_report", "required_args": [], "optional_args": []},
        ],
    }
    PLAN_JSON_SCHEMA: dict[str, Any] = {
        "type": "object",
        "properties": {
            "reasoning": {"type": "string"},
            "steps": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "subagent": {"type": "string", "enum": list(SUPPORTED_SUBAGENTS)},
                        "tool": {"type": "string"},
                        "args": {"type": "object"},
                        "depends_on": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                        "required": {"type": "boolean"},
                        "timeout_seconds": {"type": "number"},
                        "description": {"type": "string"},
                    },
                    "required": ["subagent"],
                },
                "minItems": 1,
            },
        },
        "required": ["steps"],
    }
    TOOL_PLAN_SPEC: list[dict[str, Any]] = [
        {
            "type": "function",
            "function": {
                "name": "emit_plan",
                "description": "Верни валидный план сабагентов в строгом JSON.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "reasoning": {"type": "string"},
                        "steps": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "subagent": {"type": "string", "enum": list(SUPPORTED_SUBAGENTS)},
                                    "tool": {"type": "string"},
                                    "args": {"type": "object"},
                                    "depends_on": {"type": "array", "items": {"type": "string"}},
                                    "required": {"type": "boolean"},
                                    "timeout_seconds": {"type": "number"},
                                    "description": {"type": "string"},
                                },
                                "required": ["subagent"],
                            },
                            "minItems": 1,
                        },
                    },
                    "required": ["steps"],
                },
            },
        }
    ]

    def __init__(self, llm_client: Optional[LLMClient] = None) -> None:
        """
        Args:
            llm_client: Явно переданный LLM-клиент. Если не указан, пытаемся
                        инициализировать EvolutionLLMClient из ENV, иначе — мок.
        """
        super().__init__(
            name=self.SUBAGENT_NAME,
            description="LLM-планировщик цепочек сабагентов под произвольные запросы",
            capabilities=["plan_scenario", "compose_subagents_pipeline"],
        )

        self.llm_client: LLMClient = (
            llm_client
            or build_evolution_llm_client_from_env()
            or MockPlannerLLMClient()
        )

    async def execute(self, context: AgentContext) -> SubagentResult:
        """
        Построить план выполнения из запроса пользователя.
        """
        validation_error = self.validate_context(context)
        if validation_error:
            return SubagentResult.create_error(error=validation_error)

        user_query = context.user_query

        try:
            # Первая попытка
            system_prompt = self._build_system_prompt()
            user_prompt = self._build_user_prompt(user_query)

            raw_response: Optional[str] = None
            plan_source: str = "structured"
            plan_response_format = {
                "type": "json_schema",
                "json_schema": {
                    "name": "planner_plan",
                    "schema": self.PLAN_JSON_SCHEMA,
                },
            }

            try:
                raw_response = await self.llm_client.generate(
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    temperature=0.2,
                    max_tokens=900,
                    response_format=plan_response_format,
                )
            except Exception as exc_struct:
                logger.warning(
                    "Structured-tag plan failed: %s. Trying tool-calling fallback.",
                    exc_struct,
                )
                raw_response = None

            if raw_response is None:
                plan_source = "tool"
                raw_response = await self.llm_client.generate(
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    temperature=0.0,
                    max_tokens=900,
                    response_format={"type": "json_object"},
                    tools=self.TOOL_PLAN_SPEC,
                    allow_tool_call=True,
                )

            plan = self._parse_llm_response(raw_response)
            if not plan.steps:
                # Попытка ремонта
                repair_response = await self._repair_plan(raw_response, "empty or invalid plan")
                raw_response = repair_response
                plan_source = "structured_repair"
                plan = self._parse_llm_response(repair_response)

            if not plan.steps:
                return SubagentResult.create_error(
                    error="Ошибка: LLM не вернул ни одного шага плана",
                    data={"raw_response": raw_response[:4000] if raw_response else None, "plan_source": plan_source},
                )

            # Постобработка: удаляем дубли, добавляем финальный explainer и ограничиваем длину
            plan.steps = self._finalize_steps(plan.steps, context=context)

            plan_dict = self._to_plan_dict(plan, raw_response, plan_source=plan_source)
            return SubagentResult.success(data=plan_dict)

        except Exception as exc:
            logger.exception("ResearchPlannerSubagent failed: %s", exc)
            return SubagentResult.create_error(
                error=f"Ошибка построения плана: {type(exc).__name__}: {exc}"
            )

    # ------------------------------------------------------------------ #
    # Промпт-инжиниринг
    # ------------------------------------------------------------------ #

    def _build_system_prompt(self) -> str:
        """Системный промпт с описанием возможностей сабагентов."""
        catalog_lines = []
        for agent, tools in self.TOOL_CATALOG.items():
            catalog_lines.append(f"- {agent}:")
            for tool in tools:
                req = ", ".join(tool.get("required_args", [])) or "—"
                opt = ", ".join(tool.get("optional_args", [])) or "—"
                catalog_lines.append(f"  • {tool['tool']} (required: {req}; optional: {opt})")
        catalog_text = "\n".join(catalog_lines)

        return (
            "Ты — ResearchPlannerSubagent в мультиагентной системе moex-market-analyst.\n"
            "Задача: составить до 5 шагов из доступных сабагентов и MCP-тулов, чтобы ответить на запрос.\n"
            "Доступные сабагенты/тулы:\n"
            f"{catalog_text}\n\n"
            "Правила:\n"
            "1) Не делай циклов, максимум 5 шагов.\n"
            "2) Указывай конкретный tool и аргументы, если нужны данные/расчёты.\n"
            "3) Для портфельных запросов ОБЯЗАТЕЛЬНО добавляй market_data (ohlcv для всех тикеров) перед risk_analytics.\n"
            "4) Для текстового ответа всегда добавляй explainer как финальный шаг.\n"
            "5) Строго выводи JSON без Markdown/комментариев, только поля reasoning и steps.\n"
            "6) Не добавляй текст вне JSON, не используй code fences.\n"
        )

    def _build_user_prompt(self, user_query: str) -> str:
        """Пользовательский промпт с запросом и требованиями к JSON."""
        few_shots_text = "\n\n".join(self.FEW_SHOTS)
        return (
            "Построй компактный план сабагентов/тулов, которые нужно вызвать, чтобы ответить на запрос.\n"
            "Строгий формат JSON:\n"
            '{\n'
            '  "reasoning": "<кратко почему такой план>",\n'
            '  "steps": [\n'
            '    {\n'
            '      "subagent": "market_data",\n'
            '      "tool": "get_index_constituents_metrics",\n'
            '      "args": {"index_ticker": "IMOEX", "as_of_date": "2024-12-01"},\n'
            '      "depends_on": [],\n'
            '      "timeout_seconds": 30,\n'
            '      "description": "получить состав индекса",\n'
            '      "required": true\n'
            '    }\n'
            "  ]\n"
            "}\n"
            "Гарантируй парсибельный JSON без лишнего текста. Макс 5 шагов.\n"
            "Опирайся на примеры (не копируй дословно, соблюдай структуру):\n"
            f"{few_shots_text}\n\n"
            f"Запрос пользователя: {user_query}"
        )

    # ------------------------------------------------------------------ #
    # Парсинг/валидация ответа LLM
    # ------------------------------------------------------------------ #

    def _parse_llm_response(self, raw_response: str) -> PlannerOutput:
        """Распарсить и провалидировать ответ LLM в PlannerOutput."""
        try:
            payload = self._extract_json(raw_response)
        except ValueError:
            logger.warning("Planner returned non-JSON response: %s", raw_response)
            return PlannerOutput(reasoning="", steps=[])

        reasoning = payload.get("reasoning") or payload.get("analysis") or ""
        raw_steps = payload.get("steps") or []

        steps: list[PlannedStep] = []
        invalid_steps: list[str] = []

        for raw_step in raw_steps[: self.MAX_STEPS]:
            normalized = self._normalize_step(raw_step)
            if not normalized.get("subagent_name"):
                invalid_steps.append(str(raw_step))
                continue

            if normalized["subagent_name"] not in self.SUPPORTED_SUBAGENTS:
                invalid_steps.append(normalized["subagent_name"])
                continue

            # Валидируем tool/args против каталога
            if not self._validate_step_against_catalog(normalized):
                invalid_steps.append(str(normalized))
                continue

            try:
                steps.append(PlannedStep(**normalized))
            except ValidationError as exc:
                logger.warning("Planner step validation failed: %s", exc)
                invalid_steps.append(str(normalized))

        if invalid_steps:
            logger.warning("Planner dropped invalid steps: %s; raw_response=%s", invalid_steps, raw_response)

        return PlannerOutput(reasoning=reasoning, steps=steps)

    def _normalize_step(self, raw_step: Any) -> dict[str, Any]:
        """Привести сырой шаг к единой схеме."""
        if not isinstance(raw_step, dict):
            return {}

        subagent_name = (
            raw_step.get("subagent")
            or raw_step.get("subagent_name")
            or raw_step.get("agent")
        )
        tool_name = raw_step.get("tool") or raw_step.get("tool_name")

        # Нормализация вида "explainer:generate_report"
        if subagent_name and ":" in str(subagent_name):
            parts = str(subagent_name).split(":", 1)
            subagent_name = parts[0]
            if not tool_name and len(parts) > 1:
                tool_name = parts[1]

        description = (
            raw_step.get("description")
            or raw_step.get("reason")
            or raw_step.get("why")
            or ""
        )

        args = raw_step.get("args") if isinstance(raw_step.get("args"), dict) else {}
        depends_on = raw_step.get("depends_on") or raw_step.get("depends") or []
        if not isinstance(depends_on, list):
            depends_on = []

        timeout_val = raw_step.get("timeout_seconds") or raw_step.get("timeout")
        try:
            if timeout_val is not None:
                timeout_val = min(float(timeout_val), self.TIMEOUT_CAP_SECONDS)
        except Exception:
            timeout_val = None

        return {
            "subagent": str(subagent_name).strip() if subagent_name else None,
            "subagent_name": str(subagent_name).strip() if subagent_name else None,
            "description": str(description).strip(),
            "required": bool(raw_step.get("required", True)),
            "tool": tool_name,
            "tool_name": tool_name,
            "args": args,
            "depends_on": depends_on,
            "timeout_seconds": timeout_val,
        }

    def _validate_step_against_catalog(self, step: dict[str, Any]) -> bool:
        """
        Проверить, что tool и аргументы соответствуют каталогу тулов сабагента.
        """
        subagent = step.get("subagent_name")
        tool = step.get("tool") or step.get("tool_name")

        # Без tool допускаем шаг, но он будет исполнен сабагентом по умолчанию
        if not tool:
            return True

        catalog = self.TOOL_CATALOG.get(subagent, [])
        matched = None
        for item in catalog:
            if item.get("tool") == tool:
                matched = item
                break

        if matched is None:
            logger.info("Planner step rejected: unknown tool %s for subagent %s", tool, subagent)
            return False

        required_args = matched.get("required_args") or []
        args = step.get("args") or {}
        missing = [arg for arg in required_args if arg not in args or args.get(arg) in (None, "")]
        if missing:
            logger.info("Planner step rejected: missing required args %s for tool %s", missing, tool)
            return False

        return True

    async def _repair_plan(self, raw_response: str, error_msg: str) -> str:
        """
        Попробовать запросить у LLM исправленную версию плана с учётом ошибки.
        """
        repair_prompt = (
            "Предыдущий ответ не соответствует требованиям JSON плана.\n"
            f"Ошибка: {error_msg}\n"
            "Верни только валидный JSON по той же задаче (поля reasoning и steps).\n"
            "Не добавляй текст вне JSON."
        )
        try:
            return await self.llm_client.generate(
                system_prompt="Исправь план в валидный JSON.",
                user_prompt=(
                    repair_prompt
                    + "\n\nТребуемая схема:\n"
                    + str(self.PLAN_JSON_SCHEMA)
                    + "\n\nПример валидного ответа:\n"
                    '{"reasoning":"...","steps":[{"subagent":"market_data","tool":"get_ohlcv_timeseries","args":{"ticker":"SBER","from_date":"2024-11-01","to_date":"2024-12-01"},"depends_on":[],"required":true}]}\n'
                    "\nОригинальный ответ:\n"
                    + raw_response
                ),
                temperature=0.0,
                max_tokens=600,
                response_format={
                    "type": "json_schema",
                    "json_schema": {"name": "planner_plan", "schema": self.PLAN_JSON_SCHEMA},
                },
            )
        except Exception:
            # Fallback на tool-calling
            return await self.llm_client.generate(
                system_prompt="Исправь план в валидный JSON.",
                user_prompt=(
                    repair_prompt
                    + "\n\nТребуемая схема:\n"
                    + str(self.PLAN_JSON_SCHEMA)
                    + "\n\nПример валидного ответа:\n"
                    '{"reasoning":"...","steps":[{"subagent":"market_data","tool":"get_ohlcv_timeseries","args":{"ticker":"SBER","from_date":"2024-11-01","to_date":"2024-12-01"},"depends_on":[],"required":true}]}\n'
                    "\nОригинальный ответ:\n"
                    + raw_response
                ),
                temperature=0.0,
                max_tokens=600,
                response_format={"type": "json_object"},
                tools=self.TOOL_PLAN_SPEC,
                allow_tool_call=True,
            )

    def _extract_json(self, raw_response: str) -> dict[str, Any]:
        """Извлечь JSON из ответа (учитывая возможные Markdown-кодовые блоки)."""
        try:
            return json.loads(raw_response)
        except json.JSONDecodeError:
            pass

        # Пытаемся вытащить JSON из code fence
        match = re.search(r"\{.*\}", raw_response, re.DOTALL)
        if match:
            return json.loads(match.group(0))

        raise ValueError("LLM response is not valid JSON")

    def _to_plan_dict(self, plan: PlannerOutput, raw_response: str, plan_source: str = "structured") -> dict[str, Any]:
        """Сконвертировать PlannerOutput в дикт для SubagentResult.data."""
        steps_payload = [
            {
                "subagent": step.subagent_name,
                "reason": step.description,
                "required": step.required,
                "tool": step.tool_name,
                "args": step.args,
                "depends_on": step.depends_on,
                "timeout_seconds": step.timeout_seconds,
            }
            for step in plan.steps
        ]

        return {
            "plan": {
                "reasoning": plan.reasoning,
                "steps": steps_payload,
            },
            "raw_llm_response": raw_response,
            "plan_source": plan_source,
        }

    # ------------------------------------------------------------------ #
    # Постобработка плана
    # ------------------------------------------------------------------ #

    def _finalize_steps(self, steps: list[PlannedStep], context: AgentContext) -> list[PlannedStep]:
        """
        Удалить дубли, обеспечить финальный explainer и ограничить длину.
        """
        unique_steps: list[PlannedStep] = []
        seen: set[str] = set()

        for step in steps:
            name = step.subagent_name
            if name in seen:
                continue
            if name not in self.SUPPORTED_SUBAGENTS:
                continue
            seen.add(name)
            unique_steps.append(step)

            if len(unique_steps) >= self.MAX_STEPS:
                break

        # Добавляем explainer в конец, если его нет
        if "explainer" not in seen:
            if len(unique_steps) >= self.MAX_STEPS:
                # Убираем последний не-required шаг, чтобы освободить место
                for idx in range(len(unique_steps) - 1, -1, -1):
                    if not unique_steps[idx].required:
                        unique_steps.pop(idx)
                        break
                # Если все шаги обязательные, обрезаем список
                if len(unique_steps) >= self.MAX_STEPS:
                    unique_steps = unique_steps[: self.MAX_STEPS - 1]

            unique_steps.append(
                PlannedStep(
                    subagent="explainer",
                    description="Сформировать текстовый ответ",
                    required=True,
                    tool="generate_report",
                    args={},
                    depends_on=[],
                    timeout_seconds=None,
                )
            )

        # Авто-инъекция dashboard для портфельных/связанных сценариев, если есть место
        scenario_str = (context.scenario_type or "").lower()
        need_dashboard = scenario_str in self.DASHBOARD_SCENARIOS
        has_dashboard = "dashboard" in seen
        if need_dashboard and not has_dashboard:
            if len(unique_steps) >= self.MAX_STEPS:
                for idx in range(len(unique_steps) - 1, -1, -1):
                    if not unique_steps[idx].required:
                        unique_steps.pop(idx)
                        break
            if len(unique_steps) < self.MAX_STEPS:
                unique_steps.append(
                    PlannedStep(
                        subagent="dashboard",
                        description="Собрать дашборд",
                        required=True,
                        tool="build_dashboard",
                        args={},
                        depends_on=["risk_analytics"] if "risk_analytics" in seen else [],
                        timeout_seconds=min(15.0, self.TIMEOUT_CAP_SECONDS),
                    )
                )
                seen.add("dashboard")

        # Требуем market_data для портфельных сценариев, если отсутствует
        need_market = scenario_str in {"portfolio_risk", "portfolio_risk_basic", "cfo_liquidity", "dynamic_plan"}
        if need_market and "market_data" not in seen:
            if len(unique_steps) >= self.MAX_STEPS:
                for idx in range(len(unique_steps) - 1, -1, -1):
                    if not unique_steps[idx].required:
                        unique_steps.pop(idx)
                        break
            if len(unique_steps) < self.MAX_STEPS:
                unique_steps.insert(
                    0,
                    PlannedStep(
                        subagent="market_data",
                        description="Получить рыночные данные",
                        required=True,
                        tool=None,
                        args={},
                        depends_on=[],
                        timeout_seconds=min(30.0, self.TIMEOUT_CAP_SECONDS),
                    ),
                )
                seen.add("market_data")

        return unique_steps[: self.MAX_STEPS]



