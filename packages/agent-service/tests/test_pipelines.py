"""
Тесты для Pipelines — определений pipeline'ов сценариев.
"""

import pytest

from agent_service.orchestrator import (
    PipelineStep,
    ScenarioPipeline,
    ScenarioType,
    get_pipeline,
)
from agent_service.orchestrator.pipelines import (
    CFO_LIQUIDITY_PIPELINE,
    INDEX_SCAN_PIPELINE,
    ISSUER_COMPARE_PIPELINE,
    PORTFOLIO_RISK_PIPELINE,
    SECURITIES_COMPARE_PIPELINE,
    SECURITY_OVERVIEW_PIPELINE,
    UNKNOWN_PIPELINE,
    get_pipeline_summary,
    list_pipelines,
)


class TestPipelineStep:
    """Тесты для PipelineStep."""

    def test_minimal_step(self):
        """Создание шага с минимальными параметрами."""
        step = PipelineStep(subagent_name="market_data")
        
        assert step.subagent_name == "market_data"
        assert step.required is True
        assert step.timeout_seconds == 30.0
        assert step.depends_on == []
        assert step.result_key == "market_data"  # Авто-установлено

    def test_full_step(self):
        """Создание шага со всеми параметрами."""
        step = PipelineStep(
            subagent_name="risk_analytics",
            required=False,
            timeout_seconds=60.0,
            depends_on=["market_data"],
            result_key="risk_result",
        )
        
        assert step.subagent_name == "risk_analytics"
        assert step.required is False
        assert step.timeout_seconds == 60.0
        assert step.depends_on == ["market_data"]
        assert step.result_key == "risk_result"


class TestScenarioPipeline:
    """Тесты для ScenarioPipeline."""

    def test_required_steps(self):
        """Получение обязательных шагов."""
        pipeline = PORTFOLIO_RISK_PIPELINE
        
        required = pipeline.required_steps
        
        # Все обязательные шаги
        assert len(required) >= 3
        assert all(step.required for step in required)

    def test_optional_steps(self):
        """Получение опциональных шагов."""
        pipeline = PORTFOLIO_RISK_PIPELINE
        
        optional = pipeline.optional_steps
        
        # Knowledge опционален
        assert any(step.subagent_name == "knowledge" for step in optional)
        assert all(not step.required for step in optional)

    def test_subagent_names(self):
        """Получение списка имён сабагентов."""
        pipeline = PORTFOLIO_RISK_PIPELINE
        
        names = pipeline.subagent_names
        
        assert "market_data" in names
        assert "risk_analytics" in names
        assert "explainer" in names


class TestGetPipeline:
    """Тесты для get_pipeline."""

    @pytest.mark.parametrize(
        "scenario_type,expected_has",
        [
            (ScenarioType.PORTFOLIO_RISK, ["market_data", "risk_analytics"]),
            (ScenarioType.CFO_LIQUIDITY, ["risk_analytics", "explainer"]),
            (ScenarioType.ISSUER_COMPARE, ["market_data", "risk_analytics"]),
            (ScenarioType.SECURITY_OVERVIEW, ["market_data", "explainer"]),
            (ScenarioType.SECURITIES_COMPARE, ["market_data", "explainer"]),
            (ScenarioType.INDEX_SCAN, ["market_data", "explainer"]),
            (ScenarioType.UNKNOWN, ["explainer"]),
        ],
    )
    def test_pipeline_for_scenario(
        self,
        scenario_type: ScenarioType,
        expected_has: list[str],
    ):
        """Проверка наличия нужных сабагентов в pipeline."""
        pipeline = get_pipeline(scenario_type)
        
        assert pipeline.scenario_type == scenario_type
        
        names = pipeline.subagent_names
        for expected in expected_has:
            assert expected in names, f"{expected} not in {names}"


class TestPipelineProperties:
    """Тесты свойств конкретных pipeline'ов."""

    def test_portfolio_risk_pipeline(self):
        """Проверка portfolio_risk pipeline."""
        pipeline = PORTFOLIO_RISK_PIPELINE
        
        assert pipeline.scenario_type == ScenarioType.PORTFOLIO_RISK
        assert len(pipeline.steps) >= 4
        
        # Проверяем порядок зависимостей
        step_names = [s.subagent_name for s in pipeline.steps]
        assert step_names.index("market_data") < step_names.index("risk_analytics")
        assert step_names.index("risk_analytics") < step_names.index("dashboard")
        
        # risk_analytics зависит от market_data
        risk_step = next(s for s in pipeline.steps if s.subagent_name == "risk_analytics")
        assert "market_data" in risk_step.depends_on

    def test_cfo_liquidity_pipeline(self):
        """Проверка cfo_liquidity pipeline."""
        pipeline = CFO_LIQUIDITY_PIPELINE
        
        assert pipeline.scenario_type == ScenarioType.CFO_LIQUIDITY
        
        # Первый шаг — risk_analytics (не market_data)
        assert pipeline.steps[0].subagent_name == "risk_analytics"

    def test_security_overview_pipeline_minimal(self):
        """Проверка минимального pipeline для overview."""
        pipeline = SECURITY_OVERVIEW_PIPELINE
        
        # Простой сценарий — только market_data и explainer
        names = pipeline.subagent_names
        assert "market_data" in names
        assert "explainer" in names
        # Нет risk_analytics для простого обзора
        assert "risk_analytics" not in names

    def test_unknown_pipeline_fallback(self):
        """Проверка fallback pipeline для UNKNOWN."""
        pipeline = UNKNOWN_PIPELINE
        
        # Только explainer для попытки ответить
        assert len(pipeline.steps) == 1
        assert pipeline.steps[0].subagent_name == "explainer"


class TestListPipelines:
    """Тесты для list_pipelines."""

    def test_all_pipelines_listed(self):
        """Все pipeline'ы доступны через list_pipelines."""
        pipelines = list_pipelines()
        
        # Как минимум 7 pipeline'ов (6 сценариев + UNKNOWN)
        assert len(pipelines) >= 7
        
        # Все типы сценариев покрыты
        scenario_types = {p.scenario_type for p in pipelines}
        for st in ScenarioType:
            assert st in scenario_types


class TestPipelineSummary:
    """Тесты для get_pipeline_summary."""

    def test_summary_format(self):
        """Проверка формата summary."""
        summary = get_pipeline_summary(ScenarioType.PORTFOLIO_RISK)
        
        # Формат: "step1* → step2 → step3*"
        assert "→" in summary
        assert "market_data" in summary
        assert "risk_analytics" in summary
        
        # Обязательные шаги помечены *
        assert "*" in summary

    def test_summary_for_all_scenarios(self):
        """Summary доступен для всех сценариев."""
        for scenario_type in ScenarioType:
            summary = get_pipeline_summary(scenario_type)
            assert len(summary) > 0
            # Хотя бы один шаг
            assert any(name in summary for name in ["market_data", "explainer", "risk_analytics"])

