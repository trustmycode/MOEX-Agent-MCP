"""
MarketDataSubagent — сабагент для получения рыночных данных через moex-iss-mcp.

Инкапсулирует взаимодействие с MCP-сервером moex-iss-mcp:
- get_security_snapshot — текущие данные по бумаге
- get_ohlcv_timeseries — исторические котировки
- get_index_constituents_metrics — состав и метрики индекса
- get_security_fundamentals — фундаментальные данные
"""

from __future__ import annotations

import logging
import os
from datetime import date, timedelta
from typing import Any, Optional

from ..core.base_subagent import BaseSubagent
from ..core.context import AgentContext
from ..core.result import SubagentResult
from ..mcp.client import McpClient
from ..mcp.types import McpConfig, ToolCallResult

logger = logging.getLogger(__name__)

# Константы и лимиты (согласно TASK-121)
MAX_TICKERS_PER_CALL = 10
MAX_LOOKBACK_DAYS = 365
DEFAULT_LOOKBACK_DAYS = 365
DEFAULT_BOARD = "TQBR"


class MarketDataSubagent(BaseSubagent):
    """
    Сабагент для получения рыночных данных через moex-iss-mcp.

    Отвечает за:
    - Получение снимков текущих данных (snapshot)
    - Получение исторических OHLCV данных
    - Получение состава и метрик индексов
    - Получение фундаментальных данных по бумагам

    Встроенные лимиты:
    - Не более MAX_TICKERS_PER_CALL тикеров за один вызов
    - Период данных ≤ MAX_LOOKBACK_DAYS дней
    - Обработка TOO_MANY_TICKERS с выбором top-N по весу

    Attributes:
        mcp_client: Клиент для взаимодействия с moex-iss-mcp.
    """

    # Имя сабагента для реестра
    SUBAGENT_NAME = "market_data"

    # MCP инструменты
    TOOL_SNAPSHOT = "get_security_snapshot"
    TOOL_OHLCV = "get_ohlcv_timeseries"
    TOOL_INDEX = "get_index_constituents_metrics"
    TOOL_FUNDAMENTALS = "get_security_fundamentals"

    def __init__(
        self,
        mcp_client: Optional[McpClient] = None,
        mcp_config: Optional[McpConfig] = None,
    ) -> None:
        """
        Инициализация MarketDataSubagent.

        Args:
            mcp_client: Предконфигурированный MCP-клиент (опционально).
            mcp_config: Конфигурация MCP-сервера (если mcp_client не передан).
        """
        super().__init__(
            name=self.SUBAGENT_NAME,
            description="Получение рыночных данных с Московской биржи через moex-iss-mcp",
            capabilities=[
                self.TOOL_SNAPSHOT,
                self.TOOL_OHLCV,
                self.TOOL_INDEX,
                self.TOOL_FUNDAMENTALS,
            ],
        )

        if mcp_client is not None:
            self._mcp_client = mcp_client
        elif mcp_config is not None:
            self._mcp_client = McpClient(mcp_config)
        else:
            # Используем ENV для конфигурации
            url = os.getenv("MOEX_ISS_MCP_URL", "http://localhost:8000")
            config = McpConfig(name="moex-iss-mcp", url=url)
            self._mcp_client = McpClient(config)

    @property
    def mcp_client(self) -> McpClient:
        """Получить MCP-клиент."""
        return self._mcp_client

    async def execute(self, context: AgentContext) -> SubagentResult:
        """
        Выполнить основную логику сабагента.

        Анализирует контекст и вызывает соответствующие MCP-инструменты
        для получения рыночных данных.

        Args:
            context: AgentContext с данными запроса и промежуточными результатами.

        Returns:
            SubagentResult с данными или ошибкой.
        """
        # Валидация контекста
        validation_error = self.validate_context(context)
        if validation_error:
            return SubagentResult.create_error(error=validation_error)

        # Определяем, какие данные нужны, из context
        scenario_type = context.scenario_type

        try:
            if scenario_type == "single_security_overview":
                return await self._handle_single_security(context)

            elif scenario_type == "compare_securities":
                return await self._handle_compare_securities(context)

            elif scenario_type == "index_risk_scan":
                return await self._handle_index_risk_scan(context)

            elif scenario_type in (
                "portfolio_risk_basic",
                "portfolio_risk",
                "cfo_liquidity_report",
            ):
                return await self._handle_portfolio_data(context)

            else:
                # Общий сценарий — пытаемся извлечь тикеры из запроса
                return await self._handle_generic_request(context)

        except Exception as e:
            error_msg = f"MarketDataSubagent error: {type(e).__name__}: {e}"
            logger.exception(error_msg)
            return SubagentResult.create_error(error=error_msg)

    async def _handle_single_security(
        self, context: AgentContext
    ) -> SubagentResult:
        """
        Обработка сценария single_security_overview.

        Получает snapshot и (опционально) OHLCV для одного тикера.
        """
        params = context.get_result("parsed_params", {})
        ticker = params.get("ticker") or self._extract_single_ticker(
            context.user_query
        )

        if not ticker:
            return SubagentResult.create_error(
                error="Не удалось определить тикер для анализа"
            )

        # Получаем snapshot
        snapshot_result = await self.get_security_snapshot(ticker)
        if not snapshot_result.success:
            return SubagentResult.create_error(
                error=f"Ошибка получения данных по {ticker}: "
                f"{snapshot_result.error.message if snapshot_result.error else 'Unknown'}",
            )

        # Получаем OHLCV если нужна история
        from_date = params.get("from_date") or self._default_from_date()
        to_date = params.get("to_date") or self._default_to_date()

        ohlcv_result = await self.get_ohlcv_timeseries(
            ticker=ticker,
            from_date=from_date,
            to_date=to_date,
        )

        data = {
            "ticker": ticker,
            "snapshot": snapshot_result.data,
            "ohlcv": ohlcv_result.data if ohlcv_result.success else None,
        }

        if ohlcv_result.success:
            return SubagentResult.success(
                data=data,
                next_agent_hint="risk_analytics",
            )
        else:
            # Частичный результат — есть snapshot, нет истории
            return SubagentResult.partial(
                data=data,
                error=f"История по {ticker} недоступна: "
                f"{ohlcv_result.error.message if ohlcv_result.error else 'Unknown'}",
                next_agent_hint="risk_analytics",
            )

    async def _handle_compare_securities(
        self, context: AgentContext
    ) -> SubagentResult:
        """
        Обработка сценария compare_securities.

        Получает данные по нескольким тикерам для сравнения.
        """
        params = context.get_result("parsed_params", {})
        tickers = params.get("tickers") or self._extract_tickers(
            context.user_query
        )

        if not tickers:
            return SubagentResult.create_error(
                error="Не удалось определить тикеры для сравнения"
            )

        # Применяем лимит
        if len(tickers) > MAX_TICKERS_PER_CALL:
            logger.warning(
                "Too many tickers (%d), limiting to %d",
                len(tickers),
                MAX_TICKERS_PER_CALL,
            )
            tickers = tickers[:MAX_TICKERS_PER_CALL]

        from_date = params.get("from_date") or self._default_from_date()
        to_date = params.get("to_date") or self._default_to_date()

        results = {}
        errors = []

        for ticker in tickers:
            # Snapshot
            snapshot = await self.get_security_snapshot(ticker)
            # OHLCV
            ohlcv = await self.get_ohlcv_timeseries(
                ticker=ticker,
                from_date=from_date,
                to_date=to_date,
            )

            snapshot_payload = snapshot.data if snapshot.success else None
            ohlcv_payload = ohlcv.data if ohlcv.success else None

            # Нормализуем snapshot в плоский dict, чтобы Explainer построил таблицу
            normalized_snapshot = self._normalize_snapshot(snapshot_payload)

            # Если данные пустые, считаем как ошибку для явности
            if snapshot.success and not snapshot_payload:
                errors.append(f"{ticker}: snapshot empty")
            if ohlcv.success and not ohlcv_payload:
                errors.append(f"{ticker}: ohlcv empty")

            results[ticker] = {
                "snapshot": normalized_snapshot or snapshot_payload,
                "ohlcv": ohlcv_payload,
            }

            if not snapshot.success:
                errors.append(
                    f"{ticker}: {snapshot.error.message if snapshot.error else 'snapshot error'}"
                )
            if not ohlcv.success:
                errors.append(
                    f"{ticker}: {ohlcv.error.message if ohlcv.error else 'ohlcv error'}"
                )
            if (not snapshot_payload) and (not ohlcv_payload):
                errors.append(f"{ticker}: данные недоступны")

        data = {
            "tickers": tickers,
            "securities": results,
            "from_date": from_date,
            "to_date": to_date,
        }

        if errors:
            return SubagentResult.partial(
                data=data,
                error="; ".join(errors),
                next_agent_hint="risk_analytics",
            )

        return SubagentResult.success(
            data=data,
            next_agent_hint="risk_analytics",
        )

    async def _handle_index_risk_scan(
        self, context: AgentContext
    ) -> SubagentResult:
        """
        Обработка сценария index_risk_scan.

        Получает состав индекса и метрики по бумагам.
        """
        params = context.get_result("parsed_params", {})
        index_ticker = params.get("index_ticker", "IMOEX")
        as_of_date = params.get("as_of_date") or self._default_to_date()

        # Получаем состав индекса
        index_result = await self.get_index_constituents_metrics(
            index_ticker=index_ticker,
            as_of_date=as_of_date,
        )

        if not index_result.success:
            return SubagentResult.create_error(
                error=f"Ошибка получения состава индекса {index_ticker}: "
                f"{index_result.error.message if index_result.error else 'Unknown'}",
            )

        return SubagentResult.success(
            data={
                "index_ticker": index_ticker,
                "as_of_date": as_of_date,
                "index_data": index_result.data,
            },
            next_agent_hint="risk_analytics",
        )

    async def _handle_portfolio_data(
        self, context: AgentContext
    ) -> SubagentResult:
        """
        Обработка сценариев с портфелем (portfolio_risk, cfo_liquidity).

        Получает OHLCV данные для всех позиций портфеля.
        """
        params = context.get_result("parsed_params", {})
        positions = params.get("positions", [])

        if not positions:
            return SubagentResult.create_error(
                error="Не указаны позиции портфеля"
            )

        # Извлекаем тикеры
        tickers = [p.get("ticker") for p in positions if p.get("ticker")]

        if len(tickers) > MAX_TICKERS_PER_CALL:
            # Выбираем top-N по весу
            sorted_positions = sorted(
                positions,
                key=lambda x: x.get("weight", 0),
                reverse=True,
            )
            tickers = [
                p.get("ticker")
                for p in sorted_positions[:MAX_TICKERS_PER_CALL]
                if p.get("ticker")
            ]
            logger.warning(
                "Portfolio has %d positions, using top %d by weight",
                len(positions),
                MAX_TICKERS_PER_CALL,
            )

        from_date = params.get("from_date") or self._default_from_date()
        to_date = params.get("to_date") or self._default_to_date()

        ohlcv_data = {}
        errors = []

        for ticker in tickers:
            result = await self.get_ohlcv_timeseries(
                ticker=ticker,
                from_date=from_date,
                to_date=to_date,
            )

            if result.success:
                ohlcv_data[ticker] = result.data
            else:
                errors.append(
                    f"{ticker}: {result.error.message if result.error else 'error'}"
                )

        data = {
            "tickers": tickers,
            "ohlcv": ohlcv_data,
            "from_date": from_date,
            "to_date": to_date,
            "positions_count": len(positions),
        }

        if errors and not ohlcv_data:
            return SubagentResult.create_error(
                error=f"Не удалось получить данные: {'; '.join(errors)}"
            )

        if errors:
            return SubagentResult.partial(
                data=data,
                error=f"Частичные данные: {'; '.join(errors)}",
                next_agent_hint="risk_analytics",
            )

        return SubagentResult.success(
            data=data,
            next_agent_hint="risk_analytics",
        )

    async def _handle_generic_request(
        self, context: AgentContext
    ) -> SubagentResult:
        """
        Обработка общего запроса.

        Пытается извлечь тикеры из запроса и получить по ним данные.
        """
        tickers = self._extract_tickers(context.user_query)

        if not tickers:
            return SubagentResult.create_error(
                error="Не удалось определить тикеры из запроса"
            )

        if len(tickers) == 1:
            # Один тикер — single security scenario
            context.scenario_type = "single_security_overview"
            return await self._handle_single_security(context)
        else:
            # Несколько тикеров — compare scenario
            context.scenario_type = "compare_securities"
            context.add_result("parsed_params", {"tickers": tickers})
            return await self._handle_compare_securities(context)

    # --- MCP Tool Wrappers ---

    async def get_security_snapshot(
        self,
        ticker: str,
        board: str = DEFAULT_BOARD,
    ) -> ToolCallResult:
        """
        Получить снимок текущих данных по бумаге.

        Args:
            ticker: Тикер бумаги (например, "SBER").
            board: Режим торгов (по умолчанию "TQBR").

        Returns:
            ToolCallResult с данными или ошибкой.
        """
        return await self._mcp_client.call_tool(
            tool_name=self.TOOL_SNAPSHOT,
            args={"ticker": ticker.upper(), "board": board},
        )

    async def get_ohlcv_timeseries(
        self,
        ticker: str,
        from_date: str,
        to_date: str,
        board: str = DEFAULT_BOARD,
        interval: str = "1d",
    ) -> ToolCallResult:
        """
        Получить исторические OHLCV данные.

        Args:
            ticker: Тикер бумаги.
            from_date: Начальная дата (YYYY-MM-DD).
            to_date: Конечная дата (YYYY-MM-DD).
            board: Режим торгов.
            interval: Интервал агрегации ("1d" или "1h").

        Returns:
            ToolCallResult с данными или ошибкой.
        """
        return await self._mcp_client.call_tool(
            tool_name=self.TOOL_OHLCV,
            args={
                "ticker": ticker.upper(),
                "board": board,
                "from_date": from_date,
                "to_date": to_date,
                "interval": interval,
            },
        )

    async def get_index_constituents_metrics(
        self,
        index_ticker: str,
        as_of_date: str,
    ) -> ToolCallResult:
        """
        Получить состав индекса и метрики по бумагам.

        Args:
            index_ticker: Тикер индекса (например, "IMOEX").
            as_of_date: Дата для получения состава (YYYY-MM-DD).

        Returns:
            ToolCallResult с данными или ошибкой.
        """
        return await self._mcp_client.call_tool(
            tool_name=self.TOOL_INDEX,
            args={
                "index_ticker": index_ticker.upper(),
                "as_of_date": as_of_date,
            },
        )

    async def get_security_fundamentals(
        self,
        ticker: str,
    ) -> ToolCallResult:
        """
        Получить фундаментальные данные по бумаге.

        Args:
            ticker: Тикер бумаги.

        Returns:
            ToolCallResult с данными или ошибкой.
        """
        return await self._mcp_client.call_tool(
            tool_name=self.TOOL_FUNDAMENTALS,
            args={"ticker": ticker.upper()},
        )

    # --- Helper Methods ---

    def _extract_single_ticker(self, query: str) -> Optional[str]:
        """
        Извлечь один тикер из запроса.

        Простая эвристика — ищем слова из 3-6 ЛАТИНСКИХ букв.
        """
        import re

        # Паттерн для тикера: 3-6 заглавных ЛАТИНСКИХ букв
        pattern = r"\b([A-Z]{3,6})\b"
        matches = re.findall(pattern, query.upper())

        # Фильтруем служебные слова и английские стоп-слова
        stopwords = {
            # Финансовые термины
            "CFO", "ROE", "ROI", "VAR", "HHI", "ETF", "OFZ", "MCP", "API",
            # Английские слова
            "GET", "SHOW", "THE", "FOR", "AND", "NOT", "WITH",
        }

        for match in matches:
            if match not in stopwords:
                return match

        return None

    def _extract_tickers(self, query: str) -> list[str]:
        """
        Извлечь список тикеров из запроса.
        """
        import re

        # Только ЛАТИНСКИЕ буквы для тикеров
        pattern = r"\b([A-Z]{3,6})\b"
        matches = re.findall(pattern, query.upper())

        stopwords = {"CFO", "ROE", "ROI", "VAR", "HHI", "ETF", "OFZ", "AND", "THE", "MCP", "API"}

        return [m for m in matches if m not in stopwords][:MAX_TICKERS_PER_CALL]

    def _default_from_date(self) -> str:
        """Получить дату начала по умолчанию (год назад)."""
        d = date.today() - timedelta(days=DEFAULT_LOOKBACK_DAYS)
        return d.isoformat()

    def _default_to_date(self) -> str:
        """Получить дату окончания по умолчанию (сегодня)."""
        return date.today().isoformat()

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #
    def _normalize_snapshot(self, snapshot_payload: Optional[dict[str, Any]]) -> Optional[dict[str, Any]]:
        """
        Привести snapshot MCP к плоскому виду, который ожидает Explainer/таблицы.
        """
        if not snapshot_payload or not isinstance(snapshot_payload, dict):
            return None

        # Возможные формы: {"structuredContent": {"data": {...}}} или сразу плоский dict
        data = snapshot_payload
        if "structuredContent" in snapshot_payload:
            sc = snapshot_payload.get("structuredContent") or {}
            data = sc.get("data") or sc

        # Метаданные (as_of) могут лежать в metadata или _meta
        meta = snapshot_payload.get("_meta") or {}
        sc_meta = snapshot_payload.get("structuredContent", {}).get("metadata", {})
        as_of = meta.get("as_of") or sc_meta.get("as_of")

        return {
            "last_price": data.get("last_price"),
            "price_change_pct": data.get("price_change_pct"),
            "value": data.get("value"),
            "intraday_volatility_estimate": data.get("intraday_volatility_estimate"),
            "as_of": as_of,
        }
