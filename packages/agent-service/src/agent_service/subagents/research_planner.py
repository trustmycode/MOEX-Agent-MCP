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
            system_prompt = self._build_system_prompt()
            user_prompt = self._build_user_prompt(user_query)

            raw_response = await self.llm_client.generate(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                temperature=0.2,
                max_tokens=900,
            )

            plan = self._parse_llm_response(raw_response)
            if not plan.steps:
                return SubagentResult.create_error(
                    error="LLM не вернул ни одного шага плана",
                    data={"raw_response": raw_response},
                )

            # Постобработка: удаляем дубли, добавляем финальный explainer и ограничиваем длину
            plan.steps = self._finalize_steps(plan.steps)

            plan_dict = self._to_plan_dict(plan, raw_response)
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
        return (
            "Ты — ResearchPlannerSubagent в мультиагентной системе moex-market-analyst.\n"
            "Твоя задача — составить до 5 шагов из доступных сабагентов, чтобы ответить на запрос.\n"
            "Доступные сабагенты и их возможности:\n"
            "- market_data: снимки котировок, OHLCV, состав индекса, фундаментальные данные.\n"
            "- risk_analytics: базовый портфельный риск, матрица корреляций, ребалансировка, CFO-ликвидность, сравнение эмитента с пирами.\n"
            "- dashboard: сбор метрик и формирование JSON-дашборда риска (RiskDashboardSpec).\n"
            "- knowledge: запросы к базе знаний/новостям через RAG, выдаёт snippets и ссылки.\n"
            "- explainer: формирует человекочитаемый текстовый ответ и рекомендации.\n\n"
            "Правила:\n"
            "1) Не делай циклов, максимум 5 шагов.\n"
            "2) Если нужны данные или расчёты — добавь market_data и/или risk_analytics.\n"
            "3) Для текстового ответа всегда добавляй explainer как финальный шаг.\n"
            "4) Для пояснений/регламентов используй knowledge (опционально).\n"
            "5) Строго выводи JSON без Markdown и комментариев.\n"
        )

    def _build_user_prompt(self, user_query: str) -> str:
        """Пользовательский промпт с запросом и требованиями к JSON."""
        return (
            "Построй компактный план сабагентов, которые нужно вызвать, чтобы ответить на запрос.\n"
            "Строгий формат JSON:\n"
            '{\n'
            '  "reasoning": "<кратко почему такой план>",\n'
            '  "steps": [\n'
            '    {"subagent": "market_data", "description": "что делает шаг", "required": true}\n'
            "  ]\n"
            "}\n"
            "Гарантируй парсибельный JSON без лишнего текста. Макс 5 шагов.\n\n"
            f"Запрос пользователя: {user_query}"
        )

    # ------------------------------------------------------------------ #
    # Парсинг/валидация ответа LLM
    # ------------------------------------------------------------------ #

    def _parse_llm_response(self, raw_response: str) -> PlannerOutput:
        """Распарсить и провалидировать ответ LLM в PlannerOutput."""
        payload = self._extract_json(raw_response)

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

            try:
                steps.append(PlannedStep(**normalized))
            except ValidationError as exc:
                logger.warning("Planner step validation failed: %s", exc)
                invalid_steps.append(str(normalized))

        if invalid_steps:
            logger.info("Planner dropped invalid steps: %s", invalid_steps)

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

        description = (
            raw_step.get("description")
            or raw_step.get("reason")
            or raw_step.get("why")
            or ""
        )

        return {
            "subagent": str(subagent_name).strip() if subagent_name else None,
            "subagent_name": str(subagent_name).strip() if subagent_name else None,
            "description": str(description).strip(),
            "required": bool(raw_step.get("required", True)),
        }

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

    def _to_plan_dict(self, plan: PlannerOutput, raw_response: str) -> dict[str, Any]:
        """Сконвертировать PlannerOutput в дикт для SubagentResult.data."""
        steps_payload = [
            {
                "subagent": step.subagent_name,
                "reason": step.description,
                "required": step.required,
            }
            for step in plan.steps
        ]

        return {
            "plan": {
                "reasoning": plan.reasoning,
                "steps": steps_payload,
            },
            "raw_llm_response": raw_response,
        }

    # ------------------------------------------------------------------ #
    # Постобработка плана
    # ------------------------------------------------------------------ #

    def _finalize_steps(self, steps: list[PlannedStep]) -> list[PlannedStep]:
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
                )
            )

        return unique_steps[: self.MAX_STEPS]


