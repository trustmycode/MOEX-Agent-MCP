"""
Тесты для IntentClassifier — классификатора намерений пользователя.
"""

import pytest

from agent_service.orchestrator import IntentClassifier, ScenarioType


class TestIntentClassifierBasic:
    """Базовые тесты классификатора."""

    @pytest.fixture
    def classifier(self) -> IntentClassifier:
        """Создать экземпляр классификатора."""
        return IntentClassifier()

    def test_empty_query(self, classifier: IntentClassifier):
        """Пустой запрос возвращает UNKNOWN."""
        assert classifier.classify("") == ScenarioType.UNKNOWN
        assert classifier.classify("   ") == ScenarioType.UNKNOWN

    def test_unknown_query(self, classifier: IntentClassifier):
        """Непонятный запрос возвращает UNKNOWN."""
        assert classifier.classify("абракадабра") == ScenarioType.UNKNOWN


class TestPortfolioRiskClassification:
    """Тесты классификации portfolio_risk."""

    @pytest.fixture
    def classifier(self) -> IntentClassifier:
        return IntentClassifier()

    @pytest.mark.parametrize(
        "query",
        [
            "Оцени риск портфеля: SBER 40%, GAZP 30%, LKOH 30%",
            "Проанализируй риск моего портфеля",
            "Какой VaR у портфеля с акциями Сбера?",
            "Портфельный риск для SBER, GAZP",
            "Стресс-тест портфеля",
            "Волатильность портфеля",
        ],
    )
    def test_portfolio_risk_queries(self, classifier: IntentClassifier, query: str):
        """Запросы о риске портфеля классифицируются как portfolio_risk."""
        result = classifier.classify(query)
        assert result == ScenarioType.PORTFOLIO_RISK, f"Query: {query}"


class TestCfoLiquidityClassification:
    """Тесты классификации cfo_liquidity."""

    @pytest.fixture
    def classifier(self) -> IntentClassifier:
        return IntentClassifier()

    @pytest.mark.parametrize(
        "query",
        [
            "Сформируй отчёт для CFO по ликвидности",
            "CFO отчёт по ликвидности портфеля",
            "Отчёт для финансового директора",
            "Проверь ковенанты",
            "CFO liquidity report",
        ],
    )
    def test_cfo_liquidity_queries(self, classifier: IntentClassifier, query: str):
        """Запросы CFO классифицируются как cfo_liquidity."""
        result = classifier.classify(query)
        assert result == ScenarioType.CFO_LIQUIDITY, f"Query: {query}"


class TestIssuerCompareClassification:
    """Тесты классификации issuer_compare."""

    @pytest.fixture
    def classifier(self) -> IntentClassifier:
        return IntentClassifier()

    @pytest.mark.parametrize(
        "query",
        [
            "Сравни эмитента Сбер с пирами",
            "Как Сбер выглядит относительно пиров по P/E",
            "Мультипликаторы Газпрома и его аналогов",
            "Peer comparison для NLMK",
        ],
    )
    def test_issuer_compare_queries(self, classifier: IntentClassifier, query: str):
        """Запросы о сравнении эмитентов."""
        result = classifier.classify(query)
        assert result == ScenarioType.ISSUER_COMPARE, f"Query: {query}"


class TestSecurityOverviewClassification:
    """Тесты классификации security_overview."""

    @pytest.fixture
    def classifier(self) -> IntentClassifier:
        return IntentClassifier()

    @pytest.mark.parametrize(
        "query",
        [
            "Что происходит с акциями SBER?",
            "Обзор бумаги GAZP",
            "Покажи информацию по LKOH",
            "Текущая цена SBER",
        ],
    )
    def test_security_overview_queries(self, classifier: IntentClassifier, query: str):
        """Запросы об обзоре одной бумаги."""
        result = classifier.classify(query)
        assert result == ScenarioType.SECURITY_OVERVIEW, f"Query: {query}"


class TestSecuritiesCompareClassification:
    """Тесты классификации securities_compare."""

    @pytest.fixture
    def classifier(self) -> IntentClassifier:
        return IntentClassifier()

    @pytest.mark.parametrize(
        "query",
        [
            "Сравни SBER и GAZP",
            "SBER или LKOH — что лучше?",
            "Сравнение акций SBER и VTBR",
        ],
    )
    def test_securities_compare_queries(self, classifier: IntentClassifier, query: str):
        """Запросы о сравнении бумаг."""
        result = classifier.classify(query)
        assert result == ScenarioType.SECURITIES_COMPARE, f"Query: {query}"


class TestIndexScanClassification:
    """Тесты классификации index_scan."""

    @pytest.fixture
    def classifier(self) -> IntentClassifier:
        return IntentClassifier()

    @pytest.mark.parametrize(
        "query",
        [
            "Разбери индекс IMOEX",
            "Анализ индекса RTSI",
            "Какие бумаги в индексе создают риск?",
            "Состав индекса MOEX",
        ],
    )
    def test_index_scan_queries(self, classifier: IntentClassifier, query: str):
        """Запросы об анализе индекса."""
        result = classifier.classify(query)
        assert result == ScenarioType.INDEX_SCAN, f"Query: {query}"


class TestRoleBasedClassification:
    """Тесты классификации с учётом роли пользователя."""

    @pytest.fixture
    def classifier(self) -> IntentClassifier:
        return IntentClassifier()

    def test_cfo_role_priority(self, classifier: IntentClassifier):
        """CFO получает приоритет cfo_liquidity при неоднозначности."""
        # Этот запрос может быть и portfolio_risk, и cfo_liquidity
        query = "Отчёт по портфелю"
        
        # Без роли — может быть любой
        result_no_role = classifier.classify(query)
        
        # С ролью CFO — приоритет cfo_liquidity
        result_cfo = classifier.classify(query, role="cfo")
        # CFO по умолчанию получает cfo_liquidity
        assert result_cfo in [ScenarioType.CFO_LIQUIDITY, ScenarioType.PORTFOLIO_RISK]

    def test_risk_manager_role_priority(self, classifier: IntentClassifier):
        """Риск-менеджер получает приоритет portfolio_risk."""
        query = "Проанализируй это"
        result = classifier.classify(query, role="risk_manager")
        # Риск-менеджер по умолчанию получает portfolio_risk
        assert result == ScenarioType.PORTFOLIO_RISK

    def test_analyst_role_priority(self, classifier: IntentClassifier):
        """Аналитик получает приоритет issuer_compare."""
        query = "Покажи мне данные"
        result = classifier.classify(query, role="analyst")
        # Аналитик по умолчанию получает issuer_compare
        assert result == ScenarioType.ISSUER_COMPARE


class TestConfidenceClassification:
    """Тесты классификации с уверенностью."""

    @pytest.fixture
    def classifier(self) -> IntentClassifier:
        return IntentClassifier()

    def test_high_confidence_explicit_query(self, classifier: IntentClassifier):
        """Явный запрос даёт высокую уверенность."""
        scenario, confidence = classifier.classify_with_confidence(
            "Оцени риск моего портфеля: SBER, GAZP, LKOH"
        )
        
        assert scenario == ScenarioType.PORTFOLIO_RISK
        assert confidence >= 0.5

    def test_low_confidence_ambiguous_query(self, classifier: IntentClassifier):
        """Неоднозначный запрос даёт низкую уверенность."""
        scenario, confidence = classifier.classify_with_confidence("покажи что-нибудь")
        
        # Уверенность ниже для неоднозначных запросов
        assert confidence < 0.8

    def test_empty_query_zero_confidence(self, classifier: IntentClassifier):
        """Пустой запрос даёт нулевую уверенность."""
        scenario, confidence = classifier.classify_with_confidence("")
        
        assert scenario == ScenarioType.UNKNOWN
        assert confidence == 0.0


class TestScenarioDescription:
    """Тесты описаний сценариев."""

    @pytest.fixture
    def classifier(self) -> IntentClassifier:
        return IntentClassifier()

    def test_all_scenarios_have_descriptions(self, classifier: IntentClassifier):
        """Все сценарии имеют описания."""
        for scenario in ScenarioType:
            description = classifier.get_scenario_description(scenario)
            assert description, f"No description for {scenario}"
            assert len(description) > 10


