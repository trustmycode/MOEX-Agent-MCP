"""
ExplainerSubagent — сабагент для генерации текстового отчёта через LLM.

Генерирует человекочитаемый текстовый отчёт (`output.text`) на основе:
- данных от MarketDataSubagent и RiskAnalyticsSubagent
- роли пользователя (CFO, риск-менеджер, аналитик)
- языка (ru/en)

**Важно**: НЕ выдумывает числа — только форматирует и объясняет данные из MCP.

Соответствует:
- TASK-2025-123 (Explainer & Dashboard Subagents)
- FR-A-ARCH-2 (Обязательные сабагенты)
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any, Optional, Protocol

from ..core.base_subagent import BaseSubagent
from ..core.context import AgentContext
from ..core.result import SubagentResult

logger = logging.getLogger(__name__)


# Типы ролей пользователя
USER_ROLE_CFO = "CFO"
USER_ROLE_RISK_MANAGER = "risk_manager"
USER_ROLE_ANALYST = "analyst"
USER_ROLE_INVESTOR = "investor"

DEFAULT_LOCALE = "ru"


class LLMClient(Protocol):
    """
    Протокол для LLM-клиента.

    Определяет интерфейс для инъекции зависимости LLM.
    """

    async def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.3,
        max_tokens: int = 2000,
    ) -> str:
        """Сгенерировать текст через LLM."""
        ...


class MockLLMClient:
    """
    Mock-клиент LLM для тестирования и отладки.

    Генерирует детерминированный текст на основе шаблонов,
    без реального вызова LLM API.
    """

    async def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.3,
        max_tokens: int = 2000,
    ) -> str:
        """Сгенерировать текст по шаблону (без LLM)."""
        # Извлекаем ключевые данные из промпта для формирования ответа
        return self._generate_template_response(user_prompt)

    def _generate_template_response(self, user_prompt: str) -> str:
        """Генерирует шаблонный ответ на основе промпта."""
        return (
            "## Отчёт по портфелю\n\n"
            "На основе предоставленных данных сформирован анализ портфеля.\n\n"
            "### Ключевые выводы\n\n"
            "Подробный анализ метрик и рекомендации доступны в структурированном дашборде.\n"
        )


class ExplainerSubagent(BaseSubagent):
    """
    Сабагент для генерации текстового отчёта через LLM.

    Создаёт человекочитаемый отчёт для `output.text` на основе:
    - результатов от MarketData/RiskAnalytics сабагентов
    - роли пользователя (адаптация стиля и фокуса)
    - локали (русский приоритет)

    **Ограничения**:
    - НЕ выдумывает числа — использует только данные из context
    - Промпт явно запрещает галлюцинации
    - Все метрики берутся из intermediate_results

    Attributes:
        llm_client: Клиент для генерации текста (LLM или mock).
    """

    def __init__(self, llm_client: Optional[LLMClient] = None) -> None:
        """
        Инициализация ExplainerSubagent.

        Args:
            llm_client: Клиент LLM для генерации текста.
                        Если не передан, используется MockLLMClient.
        """
        super().__init__(
            name="explainer",
            description="Генерирует текстовый отчёт для CFO/риск-менеджера через LLM",
            capabilities=[
                "generate_portfolio_report",
                "explain_risk_metrics",
                "adapt_to_user_role",
                "generate_recommendations",
            ],
        )
        self.llm_client: LLMClient = llm_client or MockLLMClient()

    # ------------------------------------------------------------------ #
    # Helpers: безопасное форматирование чисел (без падения на None)
    # ------------------------------------------------------------------ #

    @staticmethod
    def _fmt(value: Any, digits: int = 2, suffix: str = "%", fallback: str = "данные недоступны") -> str:
        """Безопасно форматировать число с суффиксом. Возвращает fallback при None/ошибке."""
        try:
            if value is None:
                return fallback
            num = float(value)
            return f"{num:.{digits}f}{suffix}"
        except Exception:
            return fallback

    @staticmethod
    def _fmt_plain(value: Any, digits: int = 2, fallback: str = "данные недоступны") -> str:
        """Формат без суффикса."""
        return ExplainerSubagent._fmt(value, digits=digits, suffix="", fallback=fallback)

    async def execute(self, context: AgentContext) -> SubagentResult:
        """
        Сгенерировать текстовый отчёт на основе данных из context.

        Args:
            context: AgentContext с intermediate_results от других сабагентов.

        Returns:
            SubagentResult с data={"text": str} или ошибка.
        """
        logger.info(
            "ExplainerSubagent: generating report for session %s, role=%s",
            context.session_id,
            context.user_role,
        )

        try:
            # Собираем данные из контекста
            risk_data = context.get_result("risk_analytics", {})
            market_data = context.get_result("market_data", {})
            dashboard = context.get_result("dashboard", {})

            # Определяем локаль и роль
            locale = context.get_metadata("locale", DEFAULT_LOCALE)
            user_role = context.user_role or USER_ROLE_ANALYST

            # Проверяем наличие данных
            has_risk = bool(risk_data)
            has_market_numeric = self._has_market_numeric(market_data)
            has_history = self._has_ohlcv(market_data)
            if not has_risk and not has_market_numeric:
                logger.warning("No numeric data available for report generation")
                return SubagentResult.partial(
                    data={
                        "text": self._generate_no_data_report(context, locale)
                    },
                    error="Данные для отчёта недоступны",
                )

            if not has_history and not has_risk:
                # Нет исторических данных — предупредим и вернём partial
                context.add_error(
                    "Исторические данные отсутствуют: расчёт доходностей/волатильности недоступен"
                )
                return SubagentResult.partial(
                    data={"text": self._generate_no_data_report(context, locale)},
                    error="Нет исторических данных, доступны только snapshot-показатели",
                )

            # Формируем промпты
            system_prompt = self._build_system_prompt(user_role, locale, has_history, has_risk)
            user_prompt = self._build_user_prompt(
                context=context,
                risk_data=risk_data,
                market_data=market_data,
                dashboard=dashboard,
                locale=locale,
                has_history=has_history,
            )

            # Генерируем текст через LLM
            report_text = await self.llm_client.generate(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                temperature=0.3,  # Низкая температура для точности (см. тесты)
                max_tokens=2000,
            )

            logger.info(
                "ExplainerSubagent: report generated, length=%d chars",
                len(report_text),
            )

            return SubagentResult.success(
                data={"text": report_text},
            )

        except Exception as e:
            logger.exception("ExplainerSubagent failed: %s", e)
            # В случае ошибки LLM — генерируем fallback-отчёт
            fallback_text = self._generate_fallback_report(context, str(e))
            return SubagentResult.partial(
                data={"text": fallback_text},
                error=f"Ошибка генерации отчёта: {e}",
            )

    def _build_system_prompt(self, user_role: str, locale: str, has_history: bool, has_risk: bool) -> str:
        """
        Построить системный промпт для LLM.

        Args:
            user_role: Роль пользователя (CFO, risk_manager, analyst).
            locale: Локаль (ru, en).
            has_history: Есть ли исторические данные (OHLCV).
            has_risk: Есть ли расчётные риск-метрики.

        Returns:
            Системный промпт с инструкциями для LLM.
        """
        role_instructions = self._get_role_instructions(user_role)
        language = "русском" if locale == "ru" else "English"

        history_clause = (
            "- Исторические данные ОТСУТСТВУЮТ: не выводи доходности/волатильность/корреляции, напиши 'данные недоступны'.\n"
            if not has_history and not has_risk
            else "- Исторические данные доступны: выводи метрики только из предоставленных данных.\n"
        )

        return f"""Ты — финансовый аналитик, который помогает {role_instructions['audience']} 
понять риски и характеристики инвестиционного портфеля.

## Твоя задача

Сформировать детерминированный, структурированный отчёт на {language} языке по данным risk_analytics/market_data/dashboard.

## КРИТИЧЕСКИ ВАЖНЫЕ ОГРАНИЧЕНИЯ

1. **НЕ ВЫДУМЫВАЙ ЧИСЛА** — используй ТОЛЬКО данные, которые тебе предоставлены.
2. Если данные отсутствуют — пиши "нет данных", НЕ придумывай значения.
3. Все проценты, волатильность, drawdown, ковенанты, метрики ликвидности — строго из входных данных.
4. Не добавляй числа, которых нет в предоставленных метриках.
5. {history_clause}

## Стиль отчёта для {role_instructions['role_name']}

{role_instructions['style']}

## Структура (обязательный порядок)

1. **Резюме** — 1-2 предложения, без буллетов.
2. **Ключевые метрики** — таблица или краткие пункты; если метрика отсутствует, ставь "нет данных".
3. **Риски** — 3-5 пунктов.
4. **Рекомендации** — 3-5 пунктов, без новых чисел; опирайся на данные.
5. **Итог** — 1 предложение о соответствии/несоответствии ключевым ограничениям (если применимо).

## Форматирование

- Заголовки Markdown (##, ###)
- Важные числа выделяй **жирным**
- Один язык ответа: locale
- Соблюдай порядок секций
"""

    def _get_role_instructions(self, user_role: str) -> dict[str, str]:
        """Получить инструкции по стилю для конкретной роли."""
        role_configs = {
            USER_ROLE_CFO: {
                "role_name": "CFO/Финансовый директор",
                "audience": "финансовому директору",
                "style": """
- Фокус на бизнес-импликациях, а не на технических деталях
- Акцент на рисках, которые влияют на бизнес
- Использовать понятный бизнес-язык
- Минимум технических терминов без объяснений
- Рекомендации должны быть actionable""",
            },
            USER_ROLE_RISK_MANAGER: {
                "role_name": "Риск-менеджер",
                "audience": "риск-менеджеру",
                "style": """
- Детальное описание метрик риска (VaR, волатильность, концентрация)
- Акцент на превышениях лимитов и потенциальных проблемах
- Технические термины допустимы
- Ссылки на стресс-сценарии и их результаты
- Конкретные рекомендации по снижению рисков""",
            },
            USER_ROLE_ANALYST: {
                "role_name": "Инвестиционный аналитик",
                "audience": "инвестиционному аналитику",
                "style": """
- Баланс между бизнес-взглядом и техническими деталями
- Объяснение причин изменений метрик
- Сравнение с бенчмарками (если есть)
- Рекомендации для инвесткомитета""",
            },
            USER_ROLE_INVESTOR: {
                "role_name": "Частный инвестор",
                "audience": "частному инвестору",
                "style": """
- Максимально простой язык
- Объяснение всех терминов
- Практические рекомендации
- Акцент на понятных рисках (просадка, волатильность)""",
            },
        }

        return role_configs.get(
            user_role,
            role_configs[USER_ROLE_ANALYST],  # Default
        )

    def _build_user_prompt(
        self,
        context: AgentContext,
        risk_data: dict[str, Any],
        market_data: dict[str, Any],
        dashboard: dict[str, Any],
        locale: str,
        has_history: bool,
    ) -> str:
        """
        Построить пользовательский промпт с данными.

        Args:
            context: AgentContext с метаданными.
            risk_data: Данные от RiskAnalyticsSubagent.
            market_data: Данные от MarketDataSubagent.
            dashboard: Данные дашборда.
            locale: Локаль.

        Returns:
            Промпт с данными для генерации отчёта.
        """
        sections = []

        # Исходный запрос пользователя
        sections.append(f"## Запрос пользователя\n\n{context.user_query}")

        # Сценарий
        if context.scenario_type:
            sections.append(f"## Сценарий\n\n{context.scenario_type}")

        # Ограничения по данным
        if not has_history and not risk_data:
            sections.append(
                "## Ограничения данных\n\n"
                "- Исторические данные отсутствуют (нет OHLCV)\n"
                "- Запрещено выводить доходность, волатильность, корреляции, дивиденды\n"
                "- Разрешено использовать только snapshot-показатели (last_price, оборот)\n"
            )

        # Метрики портфеля
        if risk_data:
            sections.append(self._format_risk_data(risk_data))

        # Рыночные данные
        if market_data:
            sections.append(self._format_market_data(market_data))

        # Алерты из дашборда
        if dashboard and isinstance(dashboard, dict):
            alerts = dashboard.get("alerts", [])
            if alerts:
                sections.append(self._format_alerts(alerts))

        # Ошибки (для graceful degradation)
        if context.has_errors():
            sections.append(
                "## Ограничения\n\n"
                "При формировании отчёта возникли следующие проблемы:\n"
                + "\n".join(f"- {err}" for err in context.errors)
            )

        return "\n\n".join(sections)

    def _format_risk_data(self, risk_data: dict[str, Any]) -> str:
        """Форматировать данные риск-аналитики для промпта."""
        lines = ["## Данные риск-аналитики\n"]

        # Portfolio metrics
        portfolio_metrics = risk_data.get("portfolio_metrics", {})
        if portfolio_metrics:
            lines.append("### Метрики портфеля\n")
            if "total_return_pct" in portfolio_metrics:
                lines.append(
                    f"- Доходность за период: **{self._fmt(portfolio_metrics.get('total_return_pct'))}**"
                )
            if "annualized_volatility_pct" in portfolio_metrics:
                lines.append(
                    f"- Годовая волатильность: **{self._fmt(portfolio_metrics.get('annualized_volatility_pct'))}**"
                )
            if "max_drawdown_pct" in portfolio_metrics:
                lines.append(
                    f"- Максимальная просадка: **{self._fmt(portfolio_metrics.get('max_drawdown_pct'))}**"
                )

        # Concentration metrics
        concentration = risk_data.get("concentration_metrics", {})
        if concentration:
            lines.append("\n### Метрики концентрации\n")
            if "top1_weight_pct" in concentration:
                lines.append(
                    f"- Концентрация Top-1: **{self._fmt(concentration.get('top1_weight_pct'), digits=1)}**"
                )
            if "top3_weight_pct" in concentration:
                lines.append(
                    f"- Концентрация Top-3: **{self._fmt(concentration.get('top3_weight_pct'), digits=1)}**"
                )
            if "portfolio_hhi" in concentration:
                lines.append(f"- HHI: **{self._fmt_plain(concentration.get('portfolio_hhi'), digits=0)}**")

        # VaR
        var_light = risk_data.get("var_light", {})
        if var_light:
            lines.append("\n### Value at Risk\n")
            if "var_pct" in var_light:
                confidence = var_light.get("confidence_level", 0.95)
                horizon = var_light.get("horizon_days", 1)
                lines.append(
                    f"- VaR ({int(confidence * 100)}%, {horizon}д): **{self._fmt(var_light.get('var_pct'))}**"
                )

        # Stress results
        stress_results = risk_data.get("stress_results", [])
        if stress_results:
            lines.append("\n### Стресс-сценарии\n")
            for stress in stress_results:
                lines.append(
                    f"- {stress.get('description', stress.get('id'))}: "
                    f"**{self._fmt(stress.get('pnl_pct'))}**"
                )

        # Per instrument (краткое)
        per_instrument = risk_data.get("per_instrument", [])
        if per_instrument:
            lines.append("\n### Позиции портфеля\n")
            for instr in per_instrument[:5]:  # Показываем top-5
                weight_pct = instr.get("weight", 0) * 100
                lines.append(
                    f"- {instr.get('ticker')}: вес {self._fmt(weight_pct, digits=1)}, "
                    f"доходность {self._fmt(instr.get('total_return_pct'))}"
                )

        return "\n".join(lines)

    def _format_market_data(self, market_data: dict[str, Any]) -> str:
        """Форматировать рыночные данные для промпта."""
        lines = ["## Рыночные данные\n"]

        # Обрабатываем различные форматы market_data
        if isinstance(market_data, dict):
            payload = market_data.get("securities") if "securities" in market_data else market_data
            if isinstance(payload, dict):
                iterator = payload.items()
            else:
                iterator = []

            for ticker, data in iterator:
                if isinstance(data, dict):
                    snap = data.get("snapshot") if "snapshot" in data else data
                    ohlcv = data.get("ohlcv")
                    if not isinstance(snap, dict):
                        continue
                    lines.append(f"### {ticker}\n")

                    price = snap.get("last_price")
                    change_pct = snap.get("price_change_pct") or snap.get("change_pct")
                    value = snap.get("value")
                    intraday_vol = snap.get("intraday_volatility_estimate")

                    if price is not None:
                        lines.append(f"- Последняя цена: **{self._fmt_plain(price, digits=2)}**")
                    if change_pct is not None:
                        lines.append(f"- Изменение: **{self._fmt(change_pct)}**")
                    if value is not None:
                        lines.append(f"- Оборот: **{self._fmt_plain(value, digits=0)}**")
                    if intraday_vol is not None:
                        lines.append(f"- Интрадей волатильность: **{self._fmt_plain(intraday_vol)}**")

                    if price is None and change_pct is None and value is None and intraday_vol is None:
                        lines.append("- Данные недоступны")

                    # Отметка об истории
                    if ohlcv:
                        lines.append("- Исторические данные: получены (OHLCV)")
                    else:
                        lines.append("- Исторические данные: недоступны")

        return "\n".join(lines) if len(lines) > 1 else ""

    def _has_market_numeric(self, market_data: dict[str, Any]) -> bool:
        """Проверить, есть ли числовые данные в market_data."""
        if not market_data or not isinstance(market_data, dict):
            return False

        payload = market_data.get("securities", market_data)
        if not isinstance(payload, dict):
            return False

        for data in payload.values():
            if not isinstance(data, dict):
                continue
            snap = data.get("snapshot") if "snapshot" in data else data
            if not isinstance(snap, dict):
                continue
            if any(
                snap.get(key) is not None
                for key in ("last_price", "price_change_pct", "change_pct", "value", "intraday_volatility_estimate")
            ):
                return True
        return False

    def _has_ohlcv(self, market_data: dict[str, Any]) -> bool:
        """Проверить, есть ли исторические данные OHLCV."""
        if not market_data or not isinstance(market_data, dict):
            return False
        payload = market_data.get("securities", market_data)
        if not isinstance(payload, dict):
            return False
        for data in payload.values():
            if not isinstance(data, dict):
                continue
            ohlcv = data.get("ohlcv")
            if ohlcv:
                return True
        return False

    def _format_alerts(self, alerts: list[dict[str, Any]]) -> str:
        """Форматировать алерты для промпта."""
        lines = ["## Алерты и предупреждения\n"]

        severity_emoji = {
            "critical": "🔴",
            "warning": "🟡",
            "info": "🔵",
        }

        for alert in alerts:
            severity = alert.get("severity", "info")
            emoji = severity_emoji.get(severity, "ℹ️")
            message = alert.get("message", "")
            lines.append(f"- {emoji} {message}")

        return "\n".join(lines)

    def _generate_no_data_report(self, context: AgentContext, locale: str) -> str:
        """Сгенерировать отчёт при отсутствии данных."""
        if locale == "ru":
            return f"""## Отчёт недоступен

К сожалению, данные для формирования отчёта по запросу "{context.user_query}" недоступны.

### Возможные причины

- Сервисы рыночных данных временно недоступны
- Некорректные параметры запроса (тикеры, даты)
- Превышение лимитов API

### Рекомендации

Попробуйте повторить запрос позже или уточните параметры.
"""
        else:
            return f"""## Report Unavailable

Unfortunately, data for the query "{context.user_query}" is not available.

Please try again later or refine your request parameters.
"""

    def _generate_fallback_report(self, context: AgentContext, error: str) -> str:
        """Сгенерировать fallback-отчёт при ошибке LLM."""
        # Пытаемся сформировать базовый отчёт без LLM
        risk_data = context.get_result("risk_analytics", {})
        portfolio_metrics = risk_data.get("portfolio_metrics", {})

        sections = [
            "## Краткий отчёт по портфелю",
            "",
            "*Отчёт сформирован в упрощённом режиме из-за технических ограничений.*",
            "",
        ]

        if portfolio_metrics:
            sections.append("### Ключевые метрики")
            sections.append("")

            if "total_return_pct" in portfolio_metrics:
                sections.append(
                    f"- **Доходность**: {self._fmt(portfolio_metrics.get('total_return_pct'))}"
                )
            if "annualized_volatility_pct" in portfolio_metrics:
                sections.append(
                    f"- **Волатильность**: {self._fmt(portfolio_metrics.get('annualized_volatility_pct'))}"
                )
            if "max_drawdown_pct" in portfolio_metrics:
                sections.append(
                    f"- **Max Drawdown**: {self._fmt(portfolio_metrics.get('max_drawdown_pct'))}"
                )

        # Алерты
        dashboard = context.get_result("dashboard", {})
        if isinstance(dashboard, dict):
            alerts = dashboard.get("alerts", [])
            if alerts:
                sections.append("")
                sections.append("### Предупреждения")
                sections.append("")
                for alert in alerts:
                    sections.append(f"- {alert.get('message', '')}")

        sections.append("")
        sections.append(
            "*Для полного анализа рекомендуется использовать структурированный дашборд.*"
        )

        return "\n".join(sections)
