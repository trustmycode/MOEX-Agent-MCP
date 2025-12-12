import json

import pytest

from agent_service.subagents.research_planner import (
    MockPlannerLLMClient,
    ResearchPlannerSubagent,
)
from agent_service.core.context import AgentContext


class RecordingLLM:
    def __init__(self):
        self.calls: list[dict] = []

    async def generate(self, **kwargs):
        self.calls.append(kwargs)
        # минимально валидный план, чтобы execute прошёл
        return json.dumps(
            {
                "reasoning": "demo",
                "steps": [
                    {"subagent": "market_data", "required": True},
                    {"subagent": "explainer", "required": True},
                ],
            }
        )


@pytest.mark.anyio
async def test_planner_uses_json_schema_response_format():
    llm = RecordingLLM()
    planner = ResearchPlannerSubagent(llm_client=llm)
    context = AgentContext(user_query="план")

    await planner.execute(context)

    assert len(llm.calls) >= 1
    call = llm.calls[0]
    fmt = call.get("response_format")
    assert fmt is not None
    assert fmt.get("type") == "json_schema"
    assert fmt.get("json_schema", {}).get("name") == "planner_plan"
    assert fmt["json_schema"]["schema"]["required"] == ["steps"]


def test_finalize_plan_adds_explainer():
    planner = ResearchPlannerSubagent(llm_client=MockPlannerLLMClient())
    raw = json.dumps(
        {
            "reasoning": "demo",
            "steps": [
                {
                    "subagent": "market_data",
                    "tool": "get_security_snapshot",
                    "args": {"ticker": "SBER"},
                    "required": True,
                    "description": "snapshot",
                }
            ],
        }
    )

    plan = planner._parse_llm_response(raw)
    plan.steps = planner._finalize_steps(plan.steps)
    names = [step.subagent_name for step in plan.steps]

    assert "market_data" in names
    assert "explainer" in names[-1]


def test_validate_step_against_catalog_checks_required_args():
    planner = ResearchPlannerSubagent(llm_client=MockPlannerLLMClient())
    bad_step = {
        "subagent_name": "risk_analytics",
        "tool": "compute_portfolio_risk_basic",
        "args": {},  # positions отсутствует
    }

    assert planner._validate_step_against_catalog(bad_step) is False

