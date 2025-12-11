"""
Инструмент get_security_snapshot для получения краткого снимка инструмента.

Возвращает последнюю цену, изменение, ликвидность и другие базовые метрики.
"""

from __future__ import annotations

import asyncio
import time
from typing import Annotated, Optional

from fastmcp import Context
from opentelemetry import trace
from pydantic import Field

from moex_iss_mcp.domain_calculations import calc_intraday_volatility_estimate
from moex_iss_mcp.error_mapper import ErrorMapper
from moex_iss_mcp.models import GetSecuritySnapshotInput, GetSecuritySnapshotOutput
from moex_iss_mcp.mcp_instance import mcp
from moex_iss_mcp.telemetry import NullTracing
from moex_iss_mcp.tools.utils import ToolResult

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
    name="get_security_snapshot",
    description="""📊 Получить краткий снимок инструмента (последняя цена, изменение, ликвидность).

Инструмент возвращает актуальные данные о цене, объёмах торгов и базовых метриках
финансового инструмента на Московской бирже.

Примеры использования:
- Получить текущую цену и изменение для SBER
- Проверить ликвидность инструмента
- Получить оценку внутридневной волатильности
""",
)
async def get_security_snapshot(
    ticker: Annotated[str, Field(description="Тикер бумаги, например 'SBER'")],
    board: Annotated[Optional[str], Field(description="Борд MOEX, например 'TQBR' (по умолчанию 'TQBR')")] = "TQBR",
    ctx: Context = None,
) -> ToolResult:
    """
    Получить краткий снимок инструмента (последняя цена, изменение, ликвидность).

    Args:
        ticker: Тикер бумаги, например 'SBER'
        board: Борд MOEX, например 'TQBR' (по умолчанию 'TQBR')
        ctx: Контекст для логирования и отслеживания прогресса

    Returns:
        ToolResult: Результат с данными снимка инструмента

    Raises:
        McpError: При ошибках выполнения или валидации параметров
    """
    tool_name = "get_security_snapshot"
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
                await ctx.info(f"🚀 Начинаем получение снимка для {ticker}")
                await ctx.report_progress(progress=0, total=100)

            # Настройка атрибутов спана
            span.set_attribute("ticker", ticker)
            span.set_attribute("board", board or "TQBR")

            # Валидация входных данных через Pydantic
            if ctx:
                await ctx.info("🔍 Валидация параметров")
                await ctx.report_progress(progress=10, total=100)

            input_model = GetSecuritySnapshotInput(ticker=ticker, board=board)

            # Вызов IssClient (синхронный, оборачиваем в asyncio.to_thread)
            if ctx:
                await ctx.info("📡 Запрос данных с MOEX ISS")
                await ctx.report_progress(progress=30, total=100)

            snapshot = await asyncio.to_thread(
                _iss_client.get_security_snapshot,
                ticker=input_model.ticker,
                board=input_model.board,
            )

            if ctx:
                await ctx.info("📊 Расчёт метрик")
                await ctx.report_progress(progress=70, total=100)

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

            if ctx:
                await ctx.info("✅ Снимок получен успешно")
                await ctx.report_progress(progress=100, total=100)

            span.set_attribute("success", True)
            span.set_attribute("ticker", snapshot.ticker)
            span.set_attribute("last_price", snapshot.last_price or 0)

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
            output = GetSecuritySnapshotOutput.from_error(error_model)
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
            output = GetSecuritySnapshotOutput.from_error(error=error_model)
            return ToolResult.from_dict(output.model_dump(mode="json"))

        finally:
            if _metrics and start_ts:
                _metrics.observe_latency(tool_name, time.perf_counter() - start_ts)
