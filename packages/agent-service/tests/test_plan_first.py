from __future__ import annotations

import pytest

from typing import Any

from agent_service.core import BaseSubagent, SubagentRegistry
from agent_service.core.context import AgentContext
from agent_service.core.result import SubagentResult
from agent_service.orchestrator.models import A2AInput
from agent_service.orchestrator.orchestrator_agent import OrchestratorAgent
from agent_service.mcp.types import ToolCallResult


class StubSubagent(BaseSubagent):
    def __init__(
        self,
        name: str,
        payload: dict | None = None,
        capabilities: list[str] | None = None,
    ) -> None:
        super().__init__(name=name, description=f"stub {name}", capabilities=capabilities or [])
        self.payload = payload or {}

    async def execute(self, context: AgentContext) -> SubagentResult:  # type: ignore[override]
        return SubagentResult.success(data=self.payload)


class PlannerStub(BaseSubagent):
    def __init__(self, plan: dict) -> None:
        super().__init__(name="research_planner", description="planner stub", capabilities=[])
        self.plan = plan

    async def execute(self, context: AgentContext) -> SubagentResult:  # type: ignore[override]
        return SubagentResult.success(data=self.plan)


@pytest.mark.asyncio
async def test_build_dynamic_pipeline_includes_tools() -> None:
    registry = SubagentRegistry()
    registry.register(StubSubagent("market_data", capabilities=["get_index_constituents_metrics"]))
    registry.register(StubSubagent("explainer", {"text": "ok"}))
    orchestrator = OrchestratorAgent(registry=registry, plan_first_enabled=True)
    context = AgentContext(user_query="test")

    planner_payload = {
        "plan": {
            "reasoning": "r",
            "steps": [
                {
                    "subagent": "market_data",
                    "tool": "get_index_constituents_metrics",
                    "args": {"index_ticker": "IMOEX"},
                    "required": True,
                },
                {"subagent": "explainer", "required": True},
            ],
        }
    }

    dynamic_plan = orchestrator._build_dynamic_pipeline(planner_payload, context)  # type: ignore[prop-access]
    assert dynamic_plan is not None
    assert [s.subagent_name for s in dynamic_plan["pipeline"].steps] == ["market_data", "explainer"]
    assert dynamic_plan["steps"][0]["tool"] == "get_index_constituents_metrics"


@pytest.mark.asyncio
async def test_dynamic_pipeline_injects_dashboard_for_portfolio_risk() -> None:
    registry = SubagentRegistry()
    registry.register(StubSubagent("market_data", capabilities=["get_security_snapshot"]))
    registry.register(StubSubagent("risk_analytics", capabilities=["compute_portfolio_risk_basic"]))
    registry.register(StubSubagent("dashboard", capabilities=["build_dashboard"]))
    registry.register(StubSubagent("explainer", {"text": "ok"}))

    orchestrator = OrchestratorAgent(registry=registry, plan_first_enabled=True)
    context = AgentContext(user_query="test", scenario_type="portfolio_risk")

    planner_payload = {
        "plan": {
            "reasoning": "r",
            "steps": [
                {
                    "subagent": "market_data",
                    "tool": "get_security_snapshot",
                    "args": {"ticker": "SBER"},
                    "required": True,
                },
                {
                    "subagent": "risk_analytics",
                    "tool": "compute_portfolio_risk_basic",
                    "args": {"positions": [{"ticker": "SBER", "weight": 1.0}]},
                    "depends_on": ["market_data"],
                    "required": True,
                },
            ],
        }
    }

    dynamic_plan = orchestrator._build_dynamic_pipeline(planner_payload, context)  # type: ignore[prop-access]
    assert dynamic_plan is not None
    names = [s.subagent_name for s in dynamic_plan["pipeline"].steps]
    assert "dashboard" in names
    assert names.index("dashboard") > names.index("risk_analytics")


@pytest.mark.asyncio
async def test_handle_request_prefers_planner_when_enabled() -> None:
    registry = SubagentRegistry()
    registry.register(PlannerStub({"plan": {"reasoning": "r", "steps": [{"subagent": "explainer", "required": True}]}}))
    registry.register(StubSubagent("explainer", {"text": "ok"}))
    orchestrator = OrchestratorAgent(registry=registry, plan_first_enabled=True, enable_debug=False)

    a2a_input = A2AInput(messages=[{"role": "user", "content": "hello"}], session_id="sess-1")
    output = await orchestrator.handle_request(a2a_input)

    assert output.text == "ok"
    assert output.debug is None or output.debug.plan_source in {"dynamic", "fallback", "static"}  # type: ignore[attr-defined]


@pytest.mark.asyncio
async def test_invalid_tool_rejected_by_planner_validation() -> None:
    registry = SubagentRegistry()
    registry.register(StubSubagent("market_data"))
    registry.register(StubSubagent("explainer", {"text": "ok"}))
    orchestrator = OrchestratorAgent(registry=registry, plan_first_enabled=True)
    context = AgentContext(user_query="test")

    planner_payload = {
        "plan": {
            "reasoning": "r",
            "steps": [
                {
                    "subagent": "market_data",
                    "tool": "unknown_tool",
                    "args": {},
                    "required": True,
                },
                {"subagent": "explainer", "required": True},
            ],
        }
    }

    dynamic_plan = orchestrator._build_dynamic_pipeline(planner_payload, context)  # type: ignore[prop-access]
    assert dynamic_plan is not None
    # unknown tool is dropped, explainer remains
    assert [s.subagent_name for s in dynamic_plan["pipeline"].steps] == ["explainer"]


@pytest.mark.asyncio
async def test_compute_tail_metrics_planned() -> None:
    registry = SubagentRegistry()

    # Stub planner not needed; we call _execute_planned_step directly
    analytics = StubRiskAnalytics()
    registry.register(analytics)

    context = AgentContext(user_query="test")

    ohlcv = {
        "AAA": [{"close": 100}, {"close": 105}, {"close": 103}],
        "BBB": [{"close": 50}, {"close": 52}, {"close": 55}],
    }
    constituents = [
        {"ticker": "AAA", "weight_pct": 1.0},
        {"ticker": "BBB", "weight_pct": 0.5},
    ]

    result = await analytics._compute_tail_metrics_planned(  # type: ignore[attr-access]
        {"ohlcv": ohlcv, "constituents": constituents},
        context,
    )

    assert result.is_success
    assert result.data
    assert "per_instrument" in result.data


class StubRiskAnalytics(StubSubagent):
    def __init__(self) -> None:
        super().__init__("risk_analytics")

    async def compute_tail_metrics(self, payload: dict[str, Any]) -> Any:
        return ToolCallResult.success_result(
            tool_name="compute_tail_metrics",
            data={
                "per_instrument": [
                    {"ticker": "AAA", "weight": 0.6, "total_return_pct": 5.0, "annualized_volatility_pct": 10.0, "max_drawdown_pct": -3.0},
                    {"ticker": "BBB", "weight": 0.4, "total_return_pct": 3.0, "annualized_volatility_pct": 12.0, "max_drawdown_pct": -4.0},
                ],
                "scenario": "index_tail_analysis",
            },
        )

    # Reuse logic from real subagent only for planned step execution
    from agent_service.subagents.risk_analytics import RiskAnalyticsSubagent

    _compute_tail_metrics_planned = RiskAnalyticsSubagent._compute_tail_metrics_planned  # type: ignore

