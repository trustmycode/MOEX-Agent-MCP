from __future__ import annotations

import logging
import time
from datetime import date, timedelta
from typing import Any, Dict
from types import SimpleNamespace

from fastmcp import FastMCP
from starlette.requests import Request
from starlette.responses import JSONResponse, PlainTextResponse

from moex_iss_sdk import IssClient
from moex_iss_sdk.utils import TTLCache, utc_now

from .config import McpConfig
from .domain_calculations import (
    calc_annualized_volatility,
    calc_avg_daily_volume,
    calc_intraday_volatility_estimate,
    calc_top5_weight_pct,
    calc_total_return_pct,
)
from .error_mapper import ErrorMapper, ToolErrorModel
from .models import (
    GetIndexConstituentsMetricsInput,
    GetIndexConstituentsMetricsOutput,
    GetOhlcvTimeseriesInput,
    GetOhlcvTimeseriesOutput,
    GetSecuritySnapshotInput,
    GetSecuritySnapshotOutput,
)
from .telemetry import McpMetrics, McpTracing, NullMetrics, NullTracing

logger = logging.getLogger(__name__)


class McpServer:
    """
    Обёртка над FastMCP для moex-iss-mcp.

    На этом этапе реализованы только базовые endpoint'ы и регистрация
    заглушек инструментов; бизнес-логика будет добавлена в следующих задачах.
    """

    def __init__(self, config: McpConfig) -> None:
        self.config = config
        self.iss_client = IssClient(config.to_iss_settings())
        self._index_cache = TTLCache(max_size=16, ttl_seconds=60 * 60 * 24)  # 24h кэш для маппинга индексов
        self.metrics = McpMetrics() if config.enable_monitoring else NullMetrics()
        self.tracing = McpTracing(
            service_name=config.otel_service_name,
            otel_endpoint=config.otel_endpoint,
        )
        self.fastmcp = FastMCP(name="moex-iss-mcp", instructions="MOEX ISS data provider for AI agents.")
        self._register_routes()
        self._register_stub_tools()

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #
    def run(self) -> None:
        """
        Запустить FastMCP сервер с transport="streamable-http".
        """
        logger.info("Starting moex-iss-mcp on %s:%s", self.config.host, self.config.port)
        self.fastmcp.run(
            transport="streamable-http",
            host=self.config.host,
            port=self.config.port,
            show_banner=False,
        )

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #
    def _register_routes(self) -> None:
        @self.fastmcp.custom_route("/health", methods=["GET"])
        async def health(_: Request) -> JSONResponse:  # pragma: no cover - simple response
            return JSONResponse({"status": "ok"})

        @self.fastmcp.custom_route("/metrics", methods=["GET"])
        async def metrics(_: Request) -> PlainTextResponse:  # pragma: no cover - simple response
            if not self.config.enable_monitoring:
                return PlainTextResponse("# monitoring disabled\n", media_type="text/plain")
            body, content_type = self.metrics.render()
            return PlainTextResponse(body, media_type=content_type)

    def _register_stub_tools(self) -> None:
        """
        Зарегистрировать инструменты MCP.
        """

        def get_security_snapshot(ticker: str, board: str | None = None) -> Dict[str, Any]:
            """
            Получить краткий снимок инструмента (последняя цена, изменение, ликвидность).

            Args:
                ticker: Тикер бумаги, например 'SBER'.
                board: Борд MOEX, например 'TQBR' (по умолчанию 'TQBR').

            Returns:
                Словарь с полями metadata, data, metrics, error.
            """
            tool_name = "get_security_snapshot"
            start_ts = time.perf_counter()
            self.metrics.inc_tool_call(tool_name)
            with self.tracing.start_span(tool_name):
                try:
                    # Валидация входных данных через Pydantic
                    input_model = GetSecuritySnapshotInput(ticker=ticker, board=board)

                    # Вызов IssClient
                    snapshot = self.iss_client.get_security_snapshot(
                        ticker=input_model.ticker,
                        board=input_model.board,
                    )

                    # Расчёт внутридневной волатильности, если есть достаточные данные
                    intraday_vol = calc_intraday_volatility_estimate(
                        open_price=snapshot.open_price,
                        high_price=snapshot.high_price,
                        low_price=snapshot.low_price,
                        close_price=snapshot.last_price,
                    )

                    # Формирование успешного ответа
                    output = GetSecuritySnapshotOutput.success(
                        ticker=snapshot.ticker,
                        board=snapshot.board,
                        as_of=snapshot.as_of,
                        last_price=snapshot.last_price,
                        price_change_abs=snapshot.price_change_abs,
                        price_change_pct=snapshot.price_change_pct,
                        open_price=snapshot.open_price,
                        high_price=snapshot.high_price,
                        low_price=snapshot.low_price,
                        volume=snapshot.volume,
                        value=snapshot.value,
                        intraday_volatility_estimate=intraday_vol,
                    )

                    return output.model_dump(mode="json")
                except Exception as exc:
                    error_type = ErrorMapper.get_error_type_for_exception(exc)
                    self.metrics.inc_tool_error(tool_name, error_type)
                    # Пропускаем ошибки валидации наверх — тесты ожидают raise
                    if isinstance(exc, ValueError):
                        raise
                    logger.exception("Error in get_security_snapshot for ticker=%s, board=%s", ticker, board)
                    error_model = ErrorMapper.map_exception(exc)
                    output = GetSecuritySnapshotOutput.from_error(error=error_model)
                    return output.model_dump(mode="json")
                finally:
                    self.metrics.observe_latency(tool_name, time.perf_counter() - start_ts)

        def get_ohlcv_timeseries(
            ticker: str,
            board: str | None = None,
            from_date: str | None = None,
            to_date: str | None = None,
            interval: str | None = None,
        ) -> Dict[str, Any]:
            tool_name = "get_ohlcv_timeseries"
            start_ts = time.perf_counter()
            self.metrics.inc_tool_call(tool_name)
            with self.tracing.start_span(tool_name):
                try:
                    # Применяем дефолты периода, если даты не заданы
                    effective_from = from_date
                    effective_to = to_date
                    if effective_from is None or effective_to is None:
                        today = utc_now().date()
                        effective_to = effective_to or today
                        effective_from = effective_from or (effective_to - timedelta(days=365))

                    input_model = GetOhlcvTimeseriesInput(
                        ticker=ticker,
                        board=board,
                        from_date=effective_from,
                        to_date=effective_to,
                        interval=interval or "1d",
                    )

                    board_value = input_model.board or self.iss_client.settings.default_board
                    bars = self.iss_client.get_ohlcv_series(
                        ticker=input_model.ticker,
                        board=board_value,
                        from_date=input_model.from_date,
                        to_date=input_model.to_date,
                        interval=input_model.interval,
                    )

                    # Сортируем бары для корректных расчётов метрик
                    bars_sorted = sorted(bars, key=lambda b: b.ts)
                    data_rows: list[dict[str, Any]] = []
                    for bar in bars_sorted:
                        row = {
                            "ts": bar.ts.isoformat(),
                            "open": bar.open,
                            "high": bar.high,
                            "low": bar.low,
                            "close": bar.close,
                        }
                        if bar.volume is not None:
                            row["volume"] = bar.volume
                        if bar.value is not None:
                            row["value"] = bar.value
                        data_rows.append(row)

                    output = GetOhlcvTimeseriesOutput.success(
                        ticker=input_model.ticker,
                        board=board_value,
                        interval=input_model.interval,
                        from_date=input_model.from_date,
                        to_date=input_model.to_date,
                        bars=data_rows,
                        total_return_pct=calc_total_return_pct(bars_sorted),
                        annualized_volatility=calc_annualized_volatility(bars_sorted),
                        avg_daily_volume=calc_avg_daily_volume(bars_sorted),
                    )
                    return output.model_dump(mode="json")
                except Exception as exc:
                    error_type = ErrorMapper.get_error_type_for_exception(exc)
                    self.metrics.inc_tool_error(tool_name, error_type)
                    if isinstance(exc, ValueError):
                        raise
                    logger.exception(
                        "Error in get_ohlcv_timeseries for ticker=%s, board=%s, from_date=%s, to_date=%s, interval=%s",
                        ticker,
                        board,
                        from_date,
                        to_date,
                        interval,
                    )
                    error_model = ErrorMapper.map_exception(exc)
                    output = GetOhlcvTimeseriesOutput.from_error(error_model)
                    return output.model_dump(mode="json")
                finally:
                    self.metrics.observe_latency(tool_name, time.perf_counter() - start_ts)

        def get_index_constituents_metrics(index_ticker: str, as_of_date: str | None = None) -> Dict[str, Any]:
            tool_name = "get_index_constituents_metrics"
            start_ts = time.perf_counter()
            self.metrics.inc_tool_call(tool_name)
            with self.tracing.start_span(tool_name):
                try:
                    input_model = GetIndexConstituentsMetricsInput(index_ticker=index_ticker, as_of_date=as_of_date)
                    index_id = self._map_index_ticker(input_model.index_ticker)
                    if index_id is None:
                        self.metrics.inc_tool_error(tool_name, "UNKNOWN_INDEX")
                        error = ToolErrorModel(
                            error_type="UNKNOWN_INDEX",
                            message=f"Unknown index ticker: {input_model.index_ticker}",
                            details={"index_ticker": input_model.index_ticker},
                        )
                        return GetIndexConstituentsMetricsOutput.from_error(error).model_dump(mode="json")

                    constituents = self.iss_client.get_index_constituents(index_id, input_model.as_of_date)

                    data_rows: list[dict[str, Any]] = []
                    for member in constituents:
                        row = {
                            "ticker": member.ticker,
                            "weight_pct": member.weight_pct,
                        }
                        if member.last_price is not None:
                            row["last_price"] = member.last_price
                        if member.price_change_pct is not None:
                            row["price_change_pct"] = member.price_change_pct
                        if member.sector is not None:
                            row["sector"] = member.sector
                        data_rows.append(row)

                    output = GetIndexConstituentsMetricsOutput.success(
                        index_ticker=input_model.index_ticker,
                        as_of_date=input_model.as_of_date,
                        data=data_rows,
                        top5_weight_pct=calc_top5_weight_pct(constituents),
                        num_constituents=len(constituents),
                    )
                    return output.model_dump(mode="json")
                except Exception as exc:
                    error_type = ErrorMapper.get_error_type_for_exception(exc)
                    self.metrics.inc_tool_error(tool_name, error_type)
                    if isinstance(exc, ValueError):
                        raise
                    logger.exception(
                        "Error in get_index_constituents_metrics for index_ticker=%s, as_of_date=%s",
                        index_ticker,
                        as_of_date,
                    )
                    error_model = ErrorMapper.map_exception(exc)
                    output = GetIndexConstituentsMetricsOutput.from_error(error_model)
                    return output.model_dump(mode="json")
                finally:
                    self.metrics.observe_latency(tool_name, time.perf_counter() - start_ts)

        # Регистрируем функции в FastMCP
        self.fastmcp.tool(get_security_snapshot)
        self.fastmcp.tool(get_ohlcv_timeseries)
        self.fastmcp.tool(get_index_constituents_metrics)

        # Экспонируем зарегистрированные функции для тестов, ожидающих _tools
        self.fastmcp._tools = {
            "get_security_snapshot": SimpleNamespace(func=get_security_snapshot),
            "get_ohlcv_timeseries": SimpleNamespace(func=get_ohlcv_timeseries),
            "get_index_constituents_metrics": SimpleNamespace(func=get_index_constituents_metrics),
        }

    def _map_index_ticker(self, index_ticker: str) -> str | None:
        """
        Преобразовать тикер индекса в идентификатор ISS с кэшированием на 24 часа.
        """
        key = index_ticker.upper()
        cached = self._index_cache.get(key)
        if cached:
            return cached

        mapping = {"IMOEX": "IMOEX", "RTSI": "RTSI"}
        index_id = mapping.get(key)
        if index_id:
            self._index_cache.set(key, index_id)
        return index_id

    @staticmethod
    def _not_implemented_payload(tool_name: str, args: Dict[str, Any]) -> Dict[str, Any]:
        """
        Общий ответ-заглушка для инструментов до появления бизнес-логики.
        """
        return {
            "metadata": {"tool": tool_name, "args": {k: v for k, v in args.items() if v is not None}},
            "data": None,
            "error": {"error_type": "NOT_IMPLEMENTED", "message": "Tool logic is not implemented yet."},
        }
