"""
Инструмент get_ohlcv_timeseries для получения временного ряда OHLCV.

Возвращает исторические данные о ценах открытия, максимуме, минимуме, закрытии и объёмах.
"""

from __future__ import annotations

import asyncio
import time
from datetime import timedelta
from typing import Annotated, Any, Optional

from fastmcp import Context
from opentelemetry import trace
from pydantic import Field

from moex_iss_mcp.domain_calculations import (
    calc_annualized_volatility,
    calc_avg_daily_volume,
    calc_total_return_pct,
)
from moex_iss_mcp.error_mapper import ErrorMapper
from moex_iss_mcp.models import GetOhlcvTimeseriesInput, GetOhlcvTimeseriesOutput
from moex_iss_mcp.mcp_instance import mcp
from moex_iss_mcp.telemetry import NullTracing
from moex_iss_mcp.tools.utils import ToolResult
from moex_iss_sdk.utils import utc_now

# Глобальные зависимости (инициализируются при запуске сервера)
_iss_client = None
_metrics = None
_tracing = NullTracing()
_NOOP_SPAN = type("NoopSpan", (), {"set_attribute": lambda self, *args, **kwargs: None})()


def init_tool_dependencies(iss_client, metrics, tracing):
    """Инициализировать зависимости для инструментов."""
    global _iss_client, _metrics, _tracing
    _iss_client = iss_client
    _metrics = metrics
    _tracing = tracing or NullTracing()


tracer = trace.get_tracer(__name__)


@mcp.tool(
    name="get_ohlcv_timeseries",
    description="""📈 Получить временной ряд OHLCV (Open, High, Low, Close, Volume).

Инструмент возвращает исторические данные о ценах и объёмах торгов
для указанного инструмента за заданный период.

Примеры использования:
- Получить дневные данные за последний год
- Получить часовые данные за последний месяц
- Рассчитать метрики доходности и волатильности
""",
)
async def get_ohlcv_timeseries(
    ticker: Annotated[str, Field(description="Тикер бумаги, например 'SBER'")],
    board: Annotated[Optional[str], Field(description="Борд MOEX, например 'TQBR' (по умолчанию 'TQBR')")] = "TQBR",
    from_date: Annotated[
        Optional[str],
        Field(description="Начальная дата периода в формате YYYY-MM-DD (включительно). Если не указана, используется дата год назад"),
    ] = None,
    to_date: Annotated[
        Optional[str],
        Field(description="Конечная дата периода в формате YYYY-MM-DD (включительно). Если не указана, используется сегодняшняя дата"),
    ] = None,
    interval: Annotated[
        Optional[str],
        Field(description="Интервал агрегации: '1d' (дневной) или '1h' (часовой). По умолчанию '1d'"),
    ] = "1d",
    ctx: Context = None,
) -> ToolResult:
    """
    Получить временной ряд OHLCV для указанного инструмента.

    Args:
        ticker: Тикер бумаги, например 'SBER'
        board: Борд MOEX, например 'TQBR' (по умолчанию 'TQBR')
        from_date: Начальная дата периода в формате YYYY-MM-DD (включительно)
        to_date: Конечная дата периода в формате YYYY-MM-DD (включительно)
        interval: Интервал агрегации: '1d' (дневной) или '1h' (часовой)
        ctx: Контекст для логирования и отслеживания прогресса

    Returns:
        ToolResult: Результат с временным рядом OHLCV и рассчитанными метриками

    Raises:
        McpError: При ошибках выполнения или валидации параметров
    """
    tool_name = "get_ohlcv_timeseries"
    start_ts = None

    if _metrics:
        start_ts = time.perf_counter()
        _metrics.inc_tool_call(tool_name)

    if _tracing:
        span_context = _tracing.start_span(tool_name)
    else:
        span_context = tracer.start_as_current_span(tool_name)

    with span_context as span:
        if span is None:
            span = _NOOP_SPAN
        try:
            if ctx:
                await ctx.info(f"🚀 Начинаем получение временного ряда для {ticker}")
                await ctx.report_progress(progress=0, total=100)

            # Настройка атрибутов спана
            span.set_attribute("ticker", ticker)
            span.set_attribute("board", board or "TQBR")
            span.set_attribute("interval", interval or "1d")

            # Применяем дефолты периода, если даты не заданы
            if ctx:
                await ctx.info("🔍 Обработка параметров")
                await ctx.report_progress(progress=10, total=100)

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

            board_value = input_model.board or _iss_client.settings.default_board

            # Запрос данных
            if ctx:
                await ctx.info("📡 Запрос данных с MOEX ISS")
                await ctx.report_progress(progress=30, total=100)

            bars = await asyncio.to_thread(
                _iss_client.get_ohlcv_series,
                ticker=input_model.ticker,
                board=board_value,
                from_date=input_model.from_date,
                to_date=input_model.to_date,
                interval=input_model.interval,
            )

            if ctx:
                await ctx.info("📊 Обработка данных")
                await ctx.report_progress(progress=60, total=100)

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

            if ctx:
                await ctx.info("📈 Расчёт метрик")
                await ctx.report_progress(progress=80, total=100)

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

            if ctx:
                await ctx.info("✅ Временной ряд получен успешно")
                await ctx.report_progress(progress=100, total=100)

            span.set_attribute("success", True)
            span.set_attribute("bars_count", len(bars_sorted))

            return ToolResult.from_dict(output.model_dump(mode="json"))

        except ValueError as e:
            if ctx is None:
                raise
            error_type = ErrorMapper.get_error_type_for_exception(e)
            if _metrics:
                _metrics.inc_tool_error(tool_name, error_type)
            span.set_attribute("error", str(e))
            span.set_attribute("error_type", error_type)
            error_model = ErrorMapper.map_exception(e)
            output = GetOhlcvTimeseriesOutput.from_error(error_model)
            return ToolResult.from_dict(output.model_dump(mode="json"))

        except Exception as exc:
            error_type = ErrorMapper.get_error_type_for_exception(exc)
            if _metrics:
                _metrics.inc_tool_error(tool_name, error_type)
            span.set_attribute("error", str(exc))
            span.set_attribute("error_type", error_type)

            if ctx:
                await ctx.error(f"❌ Ошибка выполнения: {exc}")

            error_model = ErrorMapper.map_exception(exc)
            output = GetOhlcvTimeseriesOutput.from_error(error_model)
            return ToolResult.from_dict(output.model_dump(mode="json"))

        finally:
            if _metrics and start_ts:
                _metrics.observe_latency(tool_name, time.perf_counter() - start_ts)
