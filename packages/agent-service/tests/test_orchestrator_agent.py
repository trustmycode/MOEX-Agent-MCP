"""
Тесты для OrchestratorAgent — центрального координатора.
"""

import asyncio
from typing import Any, Optional

import pytest

# Для всех async тестов в этом модуле
pytestmark = pytest.mark.anyio

from agent_service.core import AgentContext, BaseSubagent, SubagentRegistry, SubagentResult
from agent_service.orchestrator import (
    A2AInput,
    A2AMessage,
    A2AOutput,
    IntentClassifier,
    OrchestratorAgent,
    ScenarioType,
)


# =============================================================================
# Тестовые сабагенты (моки)
# =============================================================================


class MockMarketDataSubagent(BaseSubagent):
    """Мок для MarketDataSubagent."""

    def __init__(self, return_data: Optional[dict] = None, should_fail: bool = False):
        super().__init__(
            name="market_data",
            description="Mock market data subagent",
            capabilities=["get_ohlcv", "get_snapshot"],
        )
        self.return_data = return_data or {
            "prices": {"SBER": 290.5, "GAZP": 180.0},
            "weights": {"SBER": 0.4, "GAZP": 0.6},
        }
        self.should_fail = should_fail
        self.execute_count = 0

    async def execute(self, context: AgentContext) -> SubagentResult:
        self.execute_count += 1
        if self.should_fail:
            return SubagentResult.create_error("Market data unavailable")
        return SubagentResult.success(data=self.return_data)


class MockRiskAnalyticsSubagent(BaseSubagent):
    """Мок для RiskAnalyticsSubagent."""

    def __init__(self, return_data: Optional[dict] = None, should_fail: bool = False):
        super().__init__(
            name="risk_analytics",
            description="Mock risk analytics subagent",
            capabilities=["compute_risk", "compute_var"],
        )
        self.return_data = return_data or {
            "per_instrument": [
                {"ticker": "SBER", "weight": 0.4, "total_return_pct": 10.5, "annualized_volatility_pct": 25.0, "max_drawdown_pct": -15.0},
                {"ticker": "GAZP", "weight": 0.6, "total_return_pct": 5.2, "annualized_volatility_pct": 30.0, "max_drawdown_pct": -20.0},
            ],
            "portfolio_metrics": {"total_return_pct": 7.3, "volatility_pct": 22.0},
            "stress_results": [
                {"id": "equity_crash", "description": "Падение акций на 10%", "pnl_pct": -8.5},
            ],
        }
        self.should_fail = should_fail
        self.execute_count = 0

    async def execute(self, context: AgentContext) -> SubagentResult:
        self.execute_count += 1
        if self.should_fail:
            return SubagentResult.create_error("Risk analytics error")
        return SubagentResult.success(data=self.return_data)


class MockDashboardSubagent(BaseSubagent):
    """Мок для DashboardSubagent."""

    def __init__(self, return_data: Optional[dict] = None):
        super().__init__(
            name="dashboard",
            description="Mock dashboard subagent",
            capabilities=["build_dashboard"],
        )
        self.return_data = return_data or {
            "metadata": {"scenario_type": "portfolio_risk"},
            "metrics": [{"id": "return", "value": 7.3, "unit": "%"}],
            "charts": [],
            "tables": [],
            "alerts": [],
        }
        self.execute_count = 0

    async def execute(self, context: AgentContext) -> SubagentResult:
        self.execute_count += 1
        return SubagentResult.success(data=self.return_data)


class MockExplainerSubagent(BaseSubagent):
    """Мок для ExplainerSubagent."""

    def __init__(self, return_text: str = "Анализ портфеля показал..."):
        super().__init__(
            name="explainer",
            description="Mock explainer subagent",
            capabilities=["generate_text"],
        )
        self.return_text = return_text
        self.execute_count = 0

    async def execute(self, context: AgentContext) -> SubagentResult:
        self.execute_count += 1
        return SubagentResult.success(data={"text": self.return_text})


class MockKnowledgeSubagent(BaseSubagent):
    """Мок для KnowledgeSubagent (RAG)."""

    def __init__(self, should_fail: bool = False):
        super().__init__(
            name="knowledge",
            description="Mock knowledge subagent",
            capabilities=["rag_search"],
        )
        self.should_fail = should_fail
        self.execute_count = 0

    async def execute(self, context: AgentContext) -> SubagentResult:
        self.execute_count += 1
        if self.should_fail:
            return SubagentResult.create_error("RAG unavailable")
        return SubagentResult.success(data={"snippets": ["VaR — это..."]})


class SlowSubagent(BaseSubagent):
    """Сабагент с задержкой для тестирования таймаутов."""

    def __init__(self, delay_seconds: float = 5.0):
        super().__init__(
            name="slow_agent",
            description="Slow agent for timeout testing",
            capabilities=[],
        )
        self.delay_seconds = delay_seconds

    async def execute(self, context: AgentContext) -> SubagentResult:
        await asyncio.sleep(self.delay_seconds)
        return SubagentResult.success(data={})


# =============================================================================
# Фикстуры
# =============================================================================


@pytest.fixture
def registry() -> SubagentRegistry:
    """Создать реестр с моками."""
    reg = SubagentRegistry()
    reg.register(MockMarketDataSubagent())
    reg.register(MockRiskAnalyticsSubagent())
    reg.register(MockDashboardSubagent())
    reg.register(MockExplainerSubagent())
    reg.register(MockKnowledgeSubagent())
    return reg


@pytest.fixture
def orchestrator(registry: SubagentRegistry) -> OrchestratorAgent:
    """Создать оркестратор с реестром моков."""
    return OrchestratorAgent(registry=registry, enable_debug=True)


@pytest.fixture
def portfolio_risk_input() -> A2AInput:
    """Пример входа для portfolio_risk."""
    return A2AInput(
        messages=[
            A2AMessage(
                role="user",
                content="Оцени риск портфеля: SBER 40%, GAZP 60%",
            )
        ],
        user_role="risk_manager",
        session_id="test-session-001",
        locale="ru",
        metadata={
            "parsed_params": {
                "positions": [
                    {"ticker": "SBER", "weight": 0.4},
                    {"ticker": "GAZP", "weight": 0.6},
                ]
            }
        },
    )


# =============================================================================
# Тесты
# =============================================================================


class TestOrchestratorCreation:
    """Тесты создания оркестратора."""

    def test_create_with_defaults(self):
        """Создание с параметрами по умолчанию."""
        orchestrator = OrchestratorAgent()
        
        assert orchestrator.registry is not None
        assert orchestrator.classifier is not None
        assert orchestrator.default_timeout == 30.0
        assert orchestrator.enable_debug is True

    def test_create_with_custom_registry(self, registry: SubagentRegistry):
        """Создание с кастомным реестром."""
        orchestrator = OrchestratorAgent(registry=registry)
        
        assert orchestrator.registry is registry
        assert len(orchestrator.list_subagents()) == 5


class TestHandleRequestBasic:
    """Базовые тесты handle_request."""

    async def test_empty_query_returns_error(self, orchestrator: OrchestratorAgent):
        """Пустой запрос возвращает ошибку."""
        input_data = A2AInput(
            messages=[A2AMessage(role="user", content="")]
        )
        
        output = await orchestrator.handle_request(input_data)
        
        assert output.status == "error"
        assert "запрос" in output.text.lower()

    async def test_unknown_intent_returns_error(self, orchestrator: OrchestratorAgent):
        """Неопределённый intent возвращает ошибку."""
        input_data = A2AInput(
            messages=[A2AMessage(role="user", content="абракадабра фывапролд")]
        )
        
        output = await orchestrator.handle_request(input_data)
        
        assert output.status == "error"
        assert "переформулируйте" in output.text.lower() or "определить" in output.text.lower()

    async def test_portfolio_without_positions_returns_hint(self, orchestrator: OrchestratorAgent):
        """Портфельный сценарий без позиций возвращает понятную подсказку."""
        input_data = A2AInput(
            messages=[A2AMessage(role="user", content="Посчитай мой портфель")],
            user_role="CFO",
            session_id="no-positions-session",
        )

        output = await orchestrator.handle_request(input_data)

        assert output.status == "error"
        assert output.error_message is not None
        assert "позици" in output.error_message.lower()


class TestHandleRequestPortfolioRisk:
    """Тесты обработки portfolio_risk сценария."""

    async def test_successful_portfolio_risk(
        self,
        orchestrator: OrchestratorAgent,
        portfolio_risk_input: A2AInput,
    ):
        """Успешное выполнение portfolio_risk."""
        output = await orchestrator.handle_request(portfolio_risk_input)
        
        assert output.status == "success"
        assert output.text != ""
        assert output.debug is not None
        assert output.debug.scenario_type == "portfolio_risk"

    async def test_portfolio_risk_has_tables(
        self,
        orchestrator: OrchestratorAgent,
        portfolio_risk_input: A2AInput,
    ):
        """portfolio_risk возвращает таблицы."""
        output = await orchestrator.handle_request(portfolio_risk_input)
        
        # Должны быть таблицы позиций и стресс-сценариев
        assert len(output.tables) >= 1

    async def test_portfolio_risk_has_dashboard(
        self,
        orchestrator: OrchestratorAgent,
        portfolio_risk_input: A2AInput,
    ):
        """portfolio_risk возвращает dashboard."""
        output = await orchestrator.handle_request(portfolio_risk_input)
        
        assert output.dashboard is not None
        assert "metrics" in output.dashboard

    async def test_portfolio_uses_session_state(
        self,
        orchestrator: OrchestratorAgent,
        portfolio_risk_input: A2AInput,
    ):
        """Повторный запрос в той же сессии использует сохранённые позиции."""
        await orchestrator.handle_request(portfolio_risk_input)

        input_data = A2AInput(
            messages=[A2AMessage(role="user", content="Рассчитай мой портфель")],
            user_role=portfolio_risk_input.user_role,
            session_id=portfolio_risk_input.session_id,
            locale="ru",
        )

        output = await orchestrator.handle_request(input_data)

        assert output.status in ("success", "partial")


class TestHandleRequestWithErrors:
    """Тесты обработки ошибок."""

    async def test_required_subagent_fails(self):
        """Ошибка обязательного сабагента прерывает pipeline."""
        registry = SubagentRegistry()
        registry.register(MockMarketDataSubagent(should_fail=True))
        registry.register(MockRiskAnalyticsSubagent())
        registry.register(MockDashboardSubagent())
        registry.register(MockExplainerSubagent())
        
        orchestrator = OrchestratorAgent(registry=registry)
        
        input_data = A2AInput(
            messages=[A2AMessage(role="user", content="Оцени риск портфеля")],
            metadata={
                "parsed_params": {
                    "positions": [
                        {"ticker": "SBER", "weight": 0.5},
                        {"ticker": "GAZP", "weight": 0.5},
                    ]
                }
            },
        )
        
        output = await orchestrator.handle_request(input_data)
        
        # Ошибка market_data (required) приводит к ошибке всего запроса
        assert output.status in ["error", "partial"]
        assert output.error_message is not None

    async def test_optional_subagent_fails_gracefully(self):
        """Ошибка опционального сабагента не прерывает pipeline."""
        registry = SubagentRegistry()
        registry.register(MockMarketDataSubagent())
        registry.register(MockRiskAnalyticsSubagent())
        registry.register(MockDashboardSubagent())
        registry.register(MockExplainerSubagent())
        registry.register(MockKnowledgeSubagent(should_fail=True))  # RAG опционален
        
        orchestrator = OrchestratorAgent(registry=registry)
        
        input_data = A2AInput(
            messages=[A2AMessage(role="user", content="Оцени риск портфеля")],
            metadata={
                "parsed_params": {
                    "positions": [
                        {"ticker": "SBER", "weight": 0.5},
                        {"ticker": "GAZP", "weight": 0.5},
                    ]
                }
            },
        )
        
        output = await orchestrator.handle_request(input_data)
        
        # Запрос успешен, несмотря на ошибку knowledge
        assert output.status == "success"

    async def test_missing_required_subagent(self):
        """Отсутствующий обязательный сабагент приводит к ошибке."""
        registry = SubagentRegistry()
        # Не регистрируем market_data
        registry.register(MockRiskAnalyticsSubagent())
        registry.register(MockExplainerSubagent())
        
        orchestrator = OrchestratorAgent(registry=registry)
        
        input_data = A2AInput(
            messages=[A2AMessage(role="user", content="Оцени риск портфеля")],
            metadata={
                "parsed_params": {
                    "positions": [
                        {"ticker": "SBER", "weight": 0.5},
                        {"ticker": "GAZP", "weight": 0.5},
                    ]
                }
            },
        )
        
        output = await orchestrator.handle_request(input_data)
        
        assert output.status == "error"
        assert "market_data" in output.error_message.lower()


class TestDebugInfo:
    """Тесты отладочной информации."""

    async def test_debug_info_present(
        self,
        orchestrator: OrchestratorAgent,
        portfolio_risk_input: A2AInput,
    ):
        """Debug info присутствует в ответе."""
        output = await orchestrator.handle_request(portfolio_risk_input)
        
        assert output.debug is not None
        assert output.debug.scenario_type == "portfolio_risk"
        assert output.debug.scenario_confidence > 0
        assert output.debug.total_duration_ms > 0
        assert len(output.debug.subagent_traces) > 0

    async def test_subagent_traces_recorded(
        self,
        orchestrator: OrchestratorAgent,
        portfolio_risk_input: A2AInput,
    ):
        """Трейсы сабагентов записываются."""
        output = await orchestrator.handle_request(portfolio_risk_input)
        
        traces = output.debug.subagent_traces
        
        # Должны быть записи для выполненных шагов
        trace_names = [t.name for t in traces]
        assert "market_data" in trace_names
        assert "explainer" in trace_names
        
        # У каждого трейса есть статус и время
        for trace in traces:
            assert trace.status in ["success", "error", "partial", "skipped"]
            assert trace.duration_ms >= 0

    async def test_debug_disabled(self, registry: SubagentRegistry):
        """Debug можно отключить."""
        orchestrator = OrchestratorAgent(registry=registry, enable_debug=False)
        
        input_data = A2AInput(
            messages=[A2AMessage(role="user", content="Оцени риск портфеля")],
            metadata={
                "parsed_params": {
                    "positions": [
                        {"ticker": "SBER", "weight": 0.5},
                        {"ticker": "GAZP", "weight": 0.5},
                    ]
                }
            },
        )
        
        output = await orchestrator.handle_request(input_data)
        
        assert output.debug is None


class TestPipelineReadiness:
    """Тесты проверки готовности pipeline."""

    def test_check_pipeline_readiness_all_present(self, orchestrator: OrchestratorAgent):
        """Все сабагенты для pipeline присутствуют."""
        readiness = orchestrator.check_pipeline_readiness(ScenarioType.PORTFOLIO_RISK)
        
        assert readiness["market_data"] is True
        assert readiness["risk_analytics"] is True
        assert readiness["explainer"] is True

    def test_check_pipeline_readiness_missing(self):
        """Обнаружение отсутствующих сабагентов."""
        registry = SubagentRegistry()
        registry.register(MockExplainerSubagent())
        # Не регистрируем market_data и risk_analytics
        
        orchestrator = OrchestratorAgent(registry=registry)
        readiness = orchestrator.check_pipeline_readiness(ScenarioType.PORTFOLIO_RISK)
        
        assert readiness["market_data"] is False
        assert readiness["risk_analytics"] is False
        assert readiness["explainer"] is True


class TestSubagentRegistration:
    """Тесты регистрации сабагентов через оркестратор."""

    def test_register_subagent(self):
        """Регистрация сабагента через оркестратор."""
        orchestrator = OrchestratorAgent()
        
        subagent = MockExplainerSubagent()
        orchestrator.register_subagent(subagent)
        
        assert "explainer" in orchestrator.list_subagents()

    def test_list_subagents(self, orchestrator: OrchestratorAgent):
        """Получение списка сабагентов."""
        subagents = orchestrator.list_subagents()
        
        assert len(subagents) == 5
        assert "market_data" in subagents
        assert "explainer" in subagents


class TestA2AModels:
    """Тесты A2A моделей."""

    def test_a2a_input_user_query(self):
        """Извлечение user_query из A2AInput."""
        input_data = A2AInput(
            messages=[
                A2AMessage(role="system", content="You are an assistant"),
                A2AMessage(role="user", content="Первый вопрос"),
                A2AMessage(role="assistant", content="Ответ"),
                A2AMessage(role="user", content="Второй вопрос"),
            ]
        )
        
        # user_query — последнее сообщение пользователя
        assert input_data.user_query == "Второй вопрос"

    def test_a2a_output_success(self):
        """Создание успешного A2AOutput."""
        output = A2AOutput.success(
            text="Анализ выполнен",
            tables=[],
            dashboard={"metrics": []},
        )
        
        assert output.status == "success"
        assert output.text == "Анализ выполнен"
        assert output.dashboard is not None

    def test_a2a_output_error(self):
        """Создание A2AOutput с ошибкой."""
        output = A2AOutput.error(error_message="Что-то пошло не так")
        
        assert output.status == "error"
        assert "Что-то пошло не так" in output.text
        assert output.error_message == "Что-то пошло не так"

    def test_a2a_output_partial(self):
        """Создание частичного A2AOutput."""
        output = A2AOutput.partial(
            text="Частичные данные",
            error_message="Не все источники доступны",
        )
        
        assert output.status == "partial"
        assert output.error_message is not None
