"""
IntentClassifier — классификатор намерений пользователя для определения типа сценария.

Анализирует запрос пользователя и роль, возвращает соответствующий ScenarioType.
Использует комбинацию ключевых слов и (опционально) LLM для классификации.
"""

from __future__ import annotations

import logging
import re
from enum import Enum
from typing import Optional

logger = logging.getLogger(__name__)


class ScenarioType(str, Enum):
    """
    Типы сценариев, поддерживаемые системой.

    Каждый тип соответствует определённому pipeline сабагентов
    и формату выходных данных.
    """

    # Портфельный анализ
    PORTFOLIO_RISK = "portfolio_risk"
    """Анализ риска портфеля — основной сценарий для риск-менеджера/PM."""

    # CFO-отчётность
    CFO_LIQUIDITY = "cfo_liquidity"
    """CFO-отчёт по ликвидности — стресс-сценарии, ковенанты."""

    # Сравнительный анализ
    ISSUER_COMPARE = "issuer_compare"
    """Сравнение эмитента с пирами по мультипликаторам."""

    # Обзоры инструментов
    SECURITY_OVERVIEW = "security_overview"
    """Обзор одной бумаги — цена, объёмы, метрики."""

    SECURITIES_COMPARE = "securities_compare"
    """Сравнение нескольких бумаг между собой."""

    # Индексы
    INDEX_SCAN = "index_scan"
    """Анализ индекса — состав, рискованные бумаги."""

    # Fallback
    UNKNOWN = "unknown"
    """Не удалось определить тип сценария."""


# Паттерны ключевых слов для каждого типа сценария
# Используются для быстрой rule-based классификации без LLM
SCENARIO_PATTERNS: dict[ScenarioType, list[str]] = {
    ScenarioType.PORTFOLIO_RISK: [
        r"риск.*портфел",
        r"портфель.*риск",
        r"оцен.*риск.*портфел",
        r"анализ.*риск.*портфел",
        r"портфельн.*риск",
        r"var.*портфел",
        r"волатильность.*портфел",
        r"стресс.*тест.*портфел",
        r"портфель.*(sber|gazp|lkoh)",  # Исправлено: требуется слово "портфель"
        r"мой.*портфель",
        r"portfolio.*risk",
        r"оцени.*портфель",
    ],
    ScenarioType.CFO_LIQUIDITY: [
        r"cfo.*отчёт",
        r"cfo.*ликвидност",
        r"отчёт.*cfo",
        r"ликвидност.*cfo",
        r"отчёт.*ликвидност",
        r"ликвидност.*отчёт",
        r"финансов.*директор",
        r"для.*cfo",
        r"ковенант",
        r"cfo.*report",
        r"liquidity.*report",
    ],
    ScenarioType.ISSUER_COMPARE: [
        r"сравн.*эмитент",
        r"эмитент.*пир",
        r"пир.*эмитент",
        r"относительно.*пир",
        r"по.*сравнению.*с.*пир",
        r"p/e.*roe",
        r"мультипликатор",
        r"compare.*issuer",
        r"peer.*comparison",
        r"сравни.*с.*аналог",
    ],
    ScenarioType.SECURITY_OVERVIEW: [
        r"обзор.*(акци|бумаг|тикер)",
        r"что.*происходит.*с.*(акци|sber|gazp|lkoh)",
        r"информаци.*по.*(акци|тикер)",
        r"покажи.*(акци|бумаг)",
        r"текущ.*цен.*(sber|gazp|lkoh)",
        r"security.*overview",
        r"ticker.*info",
        r"обзор.*\b(sber|gazp|lkoh|yndx|gmkn|nvtk|rosn|vtbr)\b",
        r"информаци.*\b(sber|gazp|lkoh|yndx|gmkn|nvtk|rosn|vtbr)\b",
    ],
    ScenarioType.SECURITIES_COMPARE: [
        r"сравни.*\b(sber|gazp|lkoh).*и.*\b(sber|gazp|lkoh)",  # Более точный паттерн
        r"сравни.*(акци|бумаг|тикер)",
        r"сравнение.*(акци|бумаг)",
        r"\b(sber|gazp|lkoh)\b.*и.*\b(sber|gazp|lkoh)\b",  # Два тикера с "и"
        r"compare.*(securit|stock)",
        r"выбор.*между",
        r"что.*лучше",
    ],
    ScenarioType.INDEX_SCAN: [
        r"индекс.*(imoex|rtsi|moex)",
        r"(imoex|rtsi|moex).*индекс",
        r"анализ.*индекс",
        r"состав.*индекс",
        r"разбери.*индекс",
        r"бумаги.*индекс",
        r"index.*(scan|analysis)",
        r"риск.*индекс",
    ],
}

# Приоритет ролей для определённых сценариев
ROLE_SCENARIO_PRIORITY: dict[str, list[ScenarioType]] = {
    "cfo": [
        ScenarioType.CFO_LIQUIDITY,
        ScenarioType.PORTFOLIO_RISK,
    ],
    "risk_manager": [
        ScenarioType.PORTFOLIO_RISK,
        ScenarioType.INDEX_SCAN,
    ],
    "analyst": [
        ScenarioType.ISSUER_COMPARE,
        ScenarioType.SECURITIES_COMPARE,
        ScenarioType.SECURITY_OVERVIEW,
    ],
    "investor": [
        ScenarioType.PORTFOLIO_RISK,
        ScenarioType.SECURITIES_COMPARE,
    ],
}


class IntentClassifier:
    """
    Классификатор намерений пользователя.

    Определяет тип сценария на основе:
    1. Ключевых слов в запросе (rule-based)
    2. Роли пользователя (для разрешения неоднозначностей)
    3. (Опционально) LLM для сложных случаев

    Attributes:
        use_llm: Использовать ли LLM для классификации (пока не реализовано).
    """

    def __init__(self, use_llm: bool = False) -> None:
        """
        Инициализация классификатора.

        Args:
            use_llm: Использовать ли LLM для классификации.
                     В MVP используется только rule-based подход.
        """
        self.use_llm = use_llm
        # Компилируем паттерны для производительности
        self._compiled_patterns: dict[ScenarioType, list[re.Pattern]] = {
            scenario_type: [re.compile(p, re.IGNORECASE) for p in patterns]
            for scenario_type, patterns in SCENARIO_PATTERNS.items()
        }

    def classify(
        self,
        query: str,
        role: Optional[str] = None,
    ) -> ScenarioType:
        """
        Классифицировать запрос пользователя.

        Args:
            query: Текст запроса на естественном языке.
            role: Роль пользователя (CFO, risk_manager, analyst, investor).

        Returns:
            ScenarioType — тип сценария для выполнения.
        """
        if not query or not query.strip():
            logger.warning("Empty query provided to classifier")
            return ScenarioType.UNKNOWN

        query_lower = query.lower()

        # Шаг 1: Rule-based классификация по ключевым словам
        matches: dict[ScenarioType, int] = {}
        for scenario_type, patterns in self._compiled_patterns.items():
            match_count = sum(1 for p in patterns if p.search(query_lower))
            if match_count > 0:
                matches[scenario_type] = match_count

        logger.debug("Pattern matches for query: %s", matches)

        # Шаг 2: Если есть совпадения, выбираем лучшее
        if matches:
            # Если роль задана, учитываем приоритет
            if role and role.lower() in ROLE_SCENARIO_PRIORITY:
                role_priority = ROLE_SCENARIO_PRIORITY[role.lower()]
                for priority_scenario in role_priority:
                    if priority_scenario in matches:
                        logger.info(
                            "Classified as %s (role priority for %s)",
                            priority_scenario.value,
                            role,
                        )
                        return priority_scenario

            # Иначе выбираем по количеству совпадений
            best_match = max(matches, key=lambda s: matches[s])
            logger.info(
                "Classified as %s (pattern match, count=%d)",
                best_match.value,
                matches[best_match],
            )
            return best_match

        # Шаг 3: Если нет явных совпадений, но есть роль — дефолт по роли
        if role and role.lower() in ROLE_SCENARIO_PRIORITY:
            default_for_role = ROLE_SCENARIO_PRIORITY[role.lower()][0]
            logger.info(
                "No pattern match, using default for role %s: %s",
                role,
                default_for_role.value,
            )
            return default_for_role

        # Шаг 4: Эвристика по упоминанию тикеров
        tickers_pattern = r"\b(sber|gazp|lkoh|yndx|gmkn|nvtk|rosn|vtbr|moex)\b"
        ticker_matches = re.findall(tickers_pattern, query_lower)

        if len(ticker_matches) >= 2:
            logger.info(
                "Multiple tickers found (%s), classifying as securities_compare",
                ticker_matches,
            )
            return ScenarioType.SECURITIES_COMPARE
        elif len(ticker_matches) == 1:
            logger.info(
                "Single ticker found (%s), classifying as security_overview",
                ticker_matches[0],
            )
            return ScenarioType.SECURITY_OVERVIEW

        # Шаг 5: Не удалось определить
        logger.warning("Could not classify query: %s", query[:100])
        return ScenarioType.UNKNOWN

    def classify_with_confidence(
        self,
        query: str,
        role: Optional[str] = None,
    ) -> tuple[ScenarioType, float]:
        """
        Классифицировать запрос с оценкой уверенности.

        Args:
            query: Текст запроса.
            role: Роль пользователя.

        Returns:
            Кортеж (ScenarioType, confidence) где confidence ∈ [0.0, 1.0].
        """
        if not query or not query.strip():
            return ScenarioType.UNKNOWN, 0.0

        query_lower = query.lower()

        # Считаем совпадения
        all_matches: dict[ScenarioType, int] = {}
        total_patterns = 0

        for scenario_type, patterns in self._compiled_patterns.items():
            match_count = sum(1 for p in patterns if p.search(query_lower))
            if match_count > 0:
                all_matches[scenario_type] = match_count
            total_patterns += len(patterns)

        if not all_matches:
            # Попробуем эвристики
            scenario = self.classify(query, role)
            confidence = 0.3 if scenario != ScenarioType.UNKNOWN else 0.0
            return scenario, confidence

        # Вычисляем уверенность на основе:
        # 1. Количества совпадений
        # 2. Разницы между лучшим и вторым результатом
        sorted_matches = sorted(all_matches.items(), key=lambda x: x[1], reverse=True)
        best_scenario, best_count = sorted_matches[0]

        # Базовая уверенность
        base_confidence = min(0.5 + best_count * 0.15, 0.95)

        # Бонус за отсутствие конкурентов
        if len(sorted_matches) == 1:
            base_confidence = min(base_confidence + 0.1, 0.95)
        elif len(sorted_matches) >= 2:
            second_count = sorted_matches[1][1]
            if best_count > second_count * 2:
                base_confidence = min(base_confidence + 0.1, 0.95)

        # Бонус за соответствие роли
        if role and role.lower() in ROLE_SCENARIO_PRIORITY:
            if best_scenario in ROLE_SCENARIO_PRIORITY[role.lower()]:
                base_confidence = min(base_confidence + 0.05, 0.98)

        return best_scenario, base_confidence

    def get_scenario_description(self, scenario_type: ScenarioType) -> str:
        """
        Получить человекочитаемое описание сценария.

        Args:
            scenario_type: Тип сценария.

        Returns:
            Описание на русском языке.
        """
        descriptions = {
            ScenarioType.PORTFOLIO_RISK: (
                "Анализ риска портфеля: концентрации, волатильность, "
                "стресс-тесты, VaR"
            ),
            ScenarioType.CFO_LIQUIDITY: (
                "Отчёт для CFO по ликвидности: стресс-сценарии, "
                "ковенанты, прогноз на горизонте"
            ),
            ScenarioType.ISSUER_COMPARE: (
                "Сравнение эмитента с пирами по мультипликаторам "
                "(P/E, EV/EBITDA, ROE и др.)"
            ),
            ScenarioType.SECURITY_OVERVIEW: (
                "Обзор инструмента: цена, объёмы, изменения, "
                "базовые метрики"
            ),
            ScenarioType.SECURITIES_COMPARE: (
                "Сравнение нескольких бумаг: доходность, волатильность, "
                "корреляции"
            ),
            ScenarioType.INDEX_SCAN: (
                "Анализ индекса: состав, веса, рискованные компоненты"
            ),
            ScenarioType.UNKNOWN: (
                "Тип сценария не определён"
            ),
        }
        return descriptions.get(scenario_type, "Неизвестный сценарий")

