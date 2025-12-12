"""
Тесты для ExplainerSubagent.

Проверяет:
- Генерацию текстового отчёта через LLM (mock)
- Адаптацию отчёта под роль пользователя
- Форматирование данных для промпта
- Graceful degradation при ошибках
- Fallback-отчёт без LLM
"""

import pytest
from typing import Optional

from agent_service.core.context import AgentContext
from agent_service.core.result import SubagentResult
from agent_service.subagents.explainer import (
    ExplainerSubagent,
    LLMClient,
    MockLLMClient,
    USER_ROLE_CFO,
    USER_ROLE_RISK_MANAGER,
    USER_ROLE_ANALYST,
)


class RecordingLLMClient:
    """LLM-клиент, который записывает вызовы для тестирования."""

    def __init__(self, response: str = "Test response"):
        self.calls: list[dict] = []
        self.response = response

    async def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.3,
        max_tokens: int = 2000,
    ) -> str:
        self.calls.append(
            {
                "system_prompt": system_prompt,
                "user_prompt": user_prompt,
                "temperature": temperature,
                "max_tokens": max_tokens,
            }
        )
        return self.response


class FailingLLMClient:
    """LLM-клиент, который всегда падает."""

    async def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.3,
        max_tokens: int = 2000,
    ) -> str:
        raise ConnectionError("LLM service unavailable")


@pytest.fixture
def explainer_subagent() -> ExplainerSubagent:
    """Создать ExplainerSubagent с mock LLM."""
    return ExplainerSubagent(llm_client=MockLLMClient())


@pytest.fixture
def recording_llm() -> RecordingLLMClient:
    """Создать записывающий LLM-клиент."""
    return RecordingLLMClient(response="## Отчёт\n\nАнализ портфеля выполнен.")


@pytest.fixture
def sample_risk_data() -> dict:
    """Пример данных от RiskAnalyticsSubagent."""
    return {
        "portfolio_metrics": {
            "total_return_pct": 11.63,
            "annualized_volatility_pct": 22.5,
            "max_drawdown_pct": -8.7,
        },
        "concentration_metrics": {
            "top1_weight_pct": 18.5,
            "top3_weight_pct": 45.0,
            "portfolio_hhi": 1850,
        },
        "var_light": {
            "var_pct": 4.47,
            "confidence_level": 0.95,
            "horizon_days": 1,
        },
        "per_instrument": [
            {
                "ticker": "SBER",
                "weight": 0.185,
                "total_return_pct": 15.2,
            },
            {
                "ticker": "GAZP",
                "weight": 0.15,
                "total_return_pct": 8.5,
            },
        ],
        "stress_results": [
            {
                "id": "oil_crisis",
                "description": "Падение нефти на 30%",
                "pnl_pct": -18.5,
            },
        ],
    }


@pytest.fixture
def context_with_data(sample_risk_data: dict) -> AgentContext:
    """Создать AgentContext с данными."""
    context = AgentContext(
        user_query="Оцени риск портфеля и дай рекомендации",
        scenario_type="portfolio_risk_basic",
        user_role=USER_ROLE_CFO,
    )
    context.add_result("risk_analytics", sample_risk_data)
    context.set_metadata("locale", "ru")
    return context


@pytest.fixture
def context_without_data() -> AgentContext:
    """Создать AgentContext без данных."""
    return AgentContext(
        user_query="Оцени риск портфеля",
        scenario_type="portfolio_risk_basic",
    )


class TestExplainerSubagentBasic:
    """Базовые тесты ExplainerSubagent."""

    def test_subagent_name_and_capabilities(
        self, explainer_subagent: ExplainerSubagent
    ):
        """Проверить имя и возможности сабагента."""
        assert explainer_subagent.name == "explainer"
        assert "generate_report" in explainer_subagent.capabilities
        assert "adapt_to_user_role" in explainer_subagent.capabilities

    @pytest.mark.asyncio
    async def test_execute_with_valid_data(
        self,
        explainer_subagent: ExplainerSubagent,
        context_with_data: AgentContext,
    ):
        """Проверить успешное выполнение с валидными данными."""
        result = await explainer_subagent.execute(context_with_data)

        assert result.status == "success"
        assert result.data is not None
        assert "text" in result.data
        assert isinstance(result.data["text"], str)
        assert len(result.data["text"]) > 0

    @pytest.mark.asyncio
    async def test_execute_without_data(
        self,
        explainer_subagent: ExplainerSubagent,
        context_without_data: AgentContext,
    ):
        """Проверить graceful degradation без данных."""
        result = await explainer_subagent.execute(context_without_data)

        assert result.status == "partial"
        assert "text" in result.data
        assert "недоступн" in result.data["text"].lower()


class TestExplainerLLMIntegration:
    """Тесты интеграции с LLM."""

    @pytest.mark.asyncio
    async def test_llm_called_with_correct_prompts(
        self, recording_llm: RecordingLLMClient, context_with_data: AgentContext
    ):
        """Проверить, что LLM вызывается с корректными промптами."""
        subagent = ExplainerSubagent(llm_client=recording_llm)
        await subagent.execute(context_with_data)

        assert len(recording_llm.calls) == 1
        call = recording_llm.calls[0]

        # Проверяем системный промпт
        assert "финансовый аналитик" in call["system_prompt"].lower()
        assert "НЕ ВЫДУМЫВАЙ ЧИСЛА" in call["system_prompt"]

        # Проверяем пользовательский промпт с данными
        assert "Доходность за период" in call["user_prompt"]
        assert "11.63" in call["user_prompt"]

    @pytest.mark.asyncio
    async def test_llm_temperature(
        self, recording_llm: RecordingLLMClient, context_with_data: AgentContext
    ):
        """Проверить, что используется низкая температура для точности."""
        subagent = ExplainerSubagent(llm_client=recording_llm)
        await subagent.execute(context_with_data)

        call = recording_llm.calls[0]
        assert call["temperature"] == 0.3  # Низкая температура

    @pytest.mark.asyncio
    async def test_llm_failure_fallback(self, context_with_data: AgentContext):
        """Проверить fallback при ошибке LLM."""
        subagent = ExplainerSubagent(llm_client=FailingLLMClient())
        result = await subagent.execute(context_with_data)

        # Должен быть partial статус с fallback-отчётом
        assert result.status == "partial"
        assert "text" in result.data
        assert "ограничен" in result.data["text"].lower() or "упрощённ" in result.data["text"].lower()
        assert "Ошибка" in result.error_message


class TestExplainerRoleAdaptation:
    """Тесты адаптации под роль пользователя."""

    @pytest.mark.asyncio
    async def test_cfo_role_prompt(
        self, recording_llm: RecordingLLMClient, context_with_data: AgentContext
    ):
        """Проверить промпт для CFO."""
        context_with_data.user_role = USER_ROLE_CFO
        subagent = ExplainerSubagent(llm_client=recording_llm)
        await subagent.execute(context_with_data)

        system_prompt = recording_llm.calls[0]["system_prompt"]
        assert "финансов" in system_prompt.lower()
        assert "бизнес" in system_prompt.lower()

    @pytest.mark.asyncio
    async def test_risk_manager_role_prompt(
        self, recording_llm: RecordingLLMClient, context_with_data: AgentContext
    ):
        """Проверить промпт для риск-менеджера."""
        context_with_data.user_role = USER_ROLE_RISK_MANAGER
        subagent = ExplainerSubagent(llm_client=recording_llm)
        await subagent.execute(context_with_data)

        system_prompt = recording_llm.calls[0]["system_prompt"]
        assert "риск-менеджер" in system_prompt.lower()
        assert "VaR" in system_prompt or "метрик" in system_prompt.lower()

    @pytest.mark.asyncio
    async def test_analyst_role_prompt(
        self, recording_llm: RecordingLLMClient, context_with_data: AgentContext
    ):
        """Проверить промпт для аналитика."""
        context_with_data.user_role = USER_ROLE_ANALYST
        subagent = ExplainerSubagent(llm_client=recording_llm)
        await subagent.execute(context_with_data)

        system_prompt = recording_llm.calls[0]["system_prompt"]
        assert "аналитик" in system_prompt.lower()

    @pytest.mark.asyncio
    async def test_default_role(
        self, recording_llm: RecordingLLMClient, context_with_data: AgentContext
    ):
        """Проверить дефолтную роль при отсутствии."""
        context_with_data.user_role = None
        subagent = ExplainerSubagent(llm_client=recording_llm)
        await subagent.execute(context_with_data)

        # Должна использоваться роль analyst по умолчанию
        system_prompt = recording_llm.calls[0]["system_prompt"]
        assert len(system_prompt) > 0


class TestExplainerDataFormatting:
    """Тесты форматирования данных для промпта."""

    @pytest.mark.asyncio
    async def test_risk_data_formatting(
        self, recording_llm: RecordingLLMClient, context_with_data: AgentContext
    ):
        """Проверить форматирование данных риск-аналитики."""
        subagent = ExplainerSubagent(llm_client=recording_llm)
        await subagent.execute(context_with_data)

        user_prompt = recording_llm.calls[0]["user_prompt"]

        # Метрики портфеля
        assert "11.63" in user_prompt  # total_return_pct
        assert "22.5" in user_prompt  # volatility
        assert "8.7" in user_prompt  # max_drawdown (или -8.7)

        # Концентрация
        assert "18.5" in user_prompt  # top1_weight_pct

        # VaR
        assert "4.47" in user_prompt  # var_pct

    @pytest.mark.asyncio
    async def test_per_instrument_formatting(
        self, recording_llm: RecordingLLMClient, context_with_data: AgentContext
    ):
        """Проверить форматирование данных по инструментам."""
        subagent = ExplainerSubagent(llm_client=recording_llm)
        await subagent.execute(context_with_data)

        user_prompt = recording_llm.calls[0]["user_prompt"]

        assert "SBER" in user_prompt
        assert "GAZP" in user_prompt

    @pytest.mark.asyncio
    async def test_stress_results_formatting(
        self, recording_llm: RecordingLLMClient, context_with_data: AgentContext
    ):
        """Проверить форматирование стресс-сценариев."""
        subagent = ExplainerSubagent(llm_client=recording_llm)
        await subagent.execute(context_with_data)

        user_prompt = recording_llm.calls[0]["user_prompt"]

        assert "нефти" in user_prompt.lower() or "oil" in user_prompt.lower()
        assert "18.5" in user_prompt  # pnl_pct

    @pytest.mark.asyncio
    async def test_user_query_in_prompt(
        self, recording_llm: RecordingLLMClient, context_with_data: AgentContext
    ):
        """Проверить включение запроса пользователя в промпт."""
        subagent = ExplainerSubagent(llm_client=recording_llm)
        await subagent.execute(context_with_data)

        user_prompt = recording_llm.calls[0]["user_prompt"]
        assert context_with_data.user_query in user_prompt


class TestExplainerAlerts:
    """Тесты форматирования алертов."""

    @pytest.mark.asyncio
    async def test_alerts_in_prompt(
        self, recording_llm: RecordingLLMClient, context_with_data: AgentContext
    ):
        """Проверить включение алертов в промпт."""
        # Добавляем алерты от dashboard
        context_with_data.add_result(
            "dashboard",
            {
                "alerts": [
                    {
                        "id": "concentration_warning",
                        "severity": "warning",
                        "message": "Высокая концентрация по SBER",
                    }
                ]
            },
        )

        subagent = ExplainerSubagent(llm_client=recording_llm)
        await subagent.execute(context_with_data)

        user_prompt = recording_llm.calls[0]["user_prompt"]
        assert "концентрация" in user_prompt.lower() or "SBER" in user_prompt


class TestExplainerLocale:
    """Тесты локализации."""

    @pytest.mark.asyncio
    async def test_russian_locale(
        self, recording_llm: RecordingLLMClient, context_with_data: AgentContext
    ):
        """Проверить русскую локаль."""
        context_with_data.set_metadata("locale", "ru")
        subagent = ExplainerSubagent(llm_client=recording_llm)
        await subagent.execute(context_with_data)

        system_prompt = recording_llm.calls[0]["system_prompt"]
        assert "русском" in system_prompt.lower()

    @pytest.mark.asyncio
    async def test_english_locale(
        self, recording_llm: RecordingLLMClient, context_with_data: AgentContext
    ):
        """Проверить английскую локаль."""
        context_with_data.set_metadata("locale", "en")
        subagent = ExplainerSubagent(llm_client=recording_llm)
        await subagent.execute(context_with_data)

        system_prompt = recording_llm.calls[0]["system_prompt"]
        assert "English" in system_prompt


class TestExplainerErrors:
    """Тесты обработки ошибок."""

    @pytest.mark.asyncio
    async def test_errors_in_context(
        self, recording_llm: RecordingLLMClient, context_with_data: AgentContext
    ):
        """Проверить включение ошибок контекста в промпт."""
        context_with_data.add_error("Данные по GAZP недоступны")

        subagent = ExplainerSubagent(llm_client=recording_llm)
        await subagent.execute(context_with_data)

        user_prompt = recording_llm.calls[0]["user_prompt"]
        assert "GAZP недоступн" in user_prompt or "Ограничения" in user_prompt


class TestExplainerFallback:
    """Тесты fallback-логики."""

    @pytest.mark.asyncio
    async def test_fallback_includes_metrics(
        self, context_with_data: AgentContext
    ):
        """Проверить, что fallback-отчёт содержит метрики."""
        subagent = ExplainerSubagent(llm_client=FailingLLMClient())
        result = await subagent.execute(context_with_data)

        fallback_text = result.data["text"]

        # Должны быть ключевые метрики
        assert "11.63" in fallback_text or "Доходность" in fallback_text

    @pytest.mark.asyncio
    async def test_no_data_report_russian(
        self, explainer_subagent: ExplainerSubagent, context_without_data: AgentContext
    ):
        """Проверить отчёт на русском при отсутствии данных."""
        context_without_data.set_metadata("locale", "ru")
        result = await explainer_subagent.execute(context_without_data)

        text = result.data["text"]
        assert "недоступ" in text.lower()
        assert "рекоменд" in text.lower() or "повтор" in text.lower()


class TestMockLLMClient:
    """Тесты MockLLMClient."""

    @pytest.mark.asyncio
    async def test_mock_client_returns_template(self):
        """Проверить, что mock-клиент возвращает шаблон."""
        client = MockLLMClient()
        response = await client.generate(
            system_prompt="test",
            user_prompt="test",
        )

        assert "Отчёт" in response
        assert len(response) > 0

    @pytest.mark.asyncio
    async def test_mock_client_no_exceptions(self):
        """Проверить, что mock-клиент не бросает исключения."""
        client = MockLLMClient()

        # Должен работать с любыми входными данными
        response = await client.generate(
            system_prompt="",
            user_prompt="",
            temperature=0,
            max_tokens=1,
        )

        assert isinstance(response, str)


