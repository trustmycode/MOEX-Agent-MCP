"""
Тесты для ResearchPlannerSubagent.
"""

import json

import pytest

from agent_service.core.context import AgentContext
from agent_service.subagents.research_planner import ResearchPlannerSubagent


class DummyLLM:
    """Детерминированный мок LLM для планировщика."""

    async def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.3,
        max_tokens: int = 800,
    ) -> str:
        return json.dumps(
            {
                "reasoning": "Нужны данные и финальное объяснение",
                "steps": [
                    {"subagent": "market_data", "description": "Получить котировки", "required": True},
                    {"subagent": "explainer", "description": "Сформировать ответ", "required": True},
                ],
            }
        )


class BadLLM:
    """LLM, возвращающий непарсибельный ответ."""

    async def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.3,
        max_tokens: int = 800,
    ) -> str:
        return "not-a-json"


@pytest.mark.anyio
async def test_research_planner_parses_valid_plan():
    planner = ResearchPlannerSubagent(llm_client=DummyLLM())
    context = AgentContext(user_query="Проанализируй SBER и дай вывод")

    result = await planner.execute(context)

    assert result.is_success
    assert "plan" in result.data
    steps = result.data["plan"]["steps"]
    assert len(steps) == 2
    assert steps[0]["subagent"] == "market_data"
    assert steps[-1]["subagent"] == "explainer"


@pytest.mark.anyio
async def test_research_planner_returns_error_on_bad_json():
    planner = ResearchPlannerSubagent(llm_client=BadLLM())
    context = AgentContext(user_query="Сделай что-нибудь необычное")

    result = await planner.execute(context)

    assert result.is_error
    assert "Ошибка" in (result.error_message or "Ошибка")


