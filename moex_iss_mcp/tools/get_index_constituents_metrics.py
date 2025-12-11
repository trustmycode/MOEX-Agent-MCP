"""
Инструмент get_index_constituents_metrics для получения метрик компонентов индекса.

Возвращает список компонентов индекса с их весами, ценами и другими метриками.
"""

import asyncio
import time
from typing import Annotated, Any, Optional

from fastmcp import Context
from opentelemetry import trace
from pydantic import Field

from moex_iss_mcp.domain_calculations import calc_top5_weight_pct
from moex_iss_mcp.models import GetIndexConstituentsMetricsInput, GetIndexConstituentsMetricsOutput
from moex_iss_sdk.error_mapper import ErrorMapper, ToolErrorModel
from moex_iss_mcp.mcp_instance import mcp
from moex_iss_mcp.telemetry import NullTracing
from moex_iss_mcp.tools.utils import ToolResult

# Глобальные зависимости (инициализируются при запуске сервера)
_iss_client = None
_metrics = None
_tracing = NullTracing()
_index_cache = None
_NOOP_SPAN = type("NoopSpan", (), {"set_attribute": lambda self, *args, **kwargs: None})()


def init_tool_dependencies(iss_client, metrics, tracing, index_cache):
    """Инициализировать зависимости для инструментов."""
    global _iss_client, _metrics, _tracing, _index_cache
    _iss_client = iss_client
    _metrics = metrics
    _tracing = tracing or NullTracing()
    _index_cache = index_cache


def _map_index_ticker(index_ticker: str) -> str | None:
    """
    Преобразовать тикер индекса в идентификатор ISS с кэшированием.

    Args:
        index_ticker: Тикер индекса (например, 'IMOEX')

    Returns:
        Идентификатор индекса для ISS или None, если индекс неизвестен
    """
    key = index_ticker.upper()
    if _index_cache:
        cached = _index_cache.get(key)
        if cached:
            return cached

    mapping = {"IMOEX": "IMOEX", "RTSI": "RTSI"}
    index_id = mapping.get(key)
    if index_id and _index_cache:
        _index_cache.set(key, index_id)
    return index_id


tracer = trace.get_tracer(__name__)


@mcp.tool(
    name="get_index_constituents_metrics",
    description="""📊 Получить метрики компонентов индекса.

Инструмент возвращает список компонентов указанного индекса с их весами,
ценами, изменениями и другими метриками.

Примеры использования:
- Получить состав индекса IMOEX
- Проверить концентрацию индекса (топ-5 бумаг)
- Получить метрики по каждому компоненту индекса
""",
)
async def get_index_constituents_metrics(
    index_ticker: Annotated[str, Field(description="Тикер индекса, например 'IMOEX' или 'RTSI'")],
    as_of_date: Annotated[
        Optional[str],
        Field(description="Дата, на которую получить состав индекса в формате YYYY-MM-DD. Если не указана, используется текущая дата"),
    ] = None,
    ctx: Context = None,
) -> ToolResult:
    """
    Получить метрики компонентов индекса.

    Args:
        index_ticker: Тикер индекса, например 'IMOEX' или 'RTSI'
        as_of_date: Дата, на которую получить состав индекса в формате YYYY-MM-DD
        ctx: Контекст для логирования и отслеживания прогресса

    Returns:
        ToolResult: Результат с данными о компонентах индекса и метриками

    Raises:
        McpError: При ошибках выполнения или валидации параметров
    """
    tool_name = "get_index_constituents_metrics"
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
                await ctx.info(f"🚀 Начинаем получение метрик для индекса {index_ticker}")
                await ctx.report_progress(progress=0, total=100)

            # Настройка атрибутов спана
            span.set_attribute("index_ticker", index_ticker)
            span.set_attribute("as_of_date", str(as_of_date) if as_of_date else "current")

            # Валидация входных данных
            if ctx:
                await ctx.info("🔍 Валидация параметров")
                await ctx.report_progress(progress=10, total=100)

            input_model = GetIndexConstituentsMetricsInput(index_ticker=index_ticker, as_of_date=as_of_date)

            # Маппинг тикера индекса
            if ctx:
                await ctx.info("🔍 Определение идентификатора индекса")
                await ctx.report_progress(progress=20, total=100)

            index_id = _map_index_ticker(input_model.index_ticker)
            if index_id is None:
                if _metrics:
                    _metrics.inc_tool_error(tool_name, "UNKNOWN_INDEX")
                error = ToolErrorModel(
                    error_type="UNKNOWN_INDEX",
                    message=f"Unknown index ticker: {input_model.index_ticker}",
                    details={"index_ticker": input_model.index_ticker},
                )
                span.set_attribute("error", "UNKNOWN_INDEX")
                if ctx:
                    await ctx.error(f"❌ Неизвестный индекс: {input_model.index_ticker}")

                output = GetIndexConstituentsMetricsOutput.from_error(error)
                return ToolResult.from_dict(output.model_dump(mode="json"))

            # Запрос данных
            if ctx:
                await ctx.info("📡 Запрос данных с MOEX ISS")
                await ctx.report_progress(progress=40, total=100)

            constituents = await asyncio.to_thread(
                _iss_client.get_index_constituents, index_id, input_model.as_of_date
            )

            if ctx:
                await ctx.info("📊 Обработка данных")
                await ctx.report_progress(progress=70, total=100)

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

            if ctx:
                await ctx.info("📈 Расчёт метрик")
                await ctx.report_progress(progress=90, total=100)

            output = GetIndexConstituentsMetricsOutput.success(
                index_ticker=input_model.index_ticker,
                as_of_date=input_model.as_of_date,
                data=data_rows,
                top5_weight_pct=calc_top5_weight_pct(constituents),
                num_constituents=len(constituents),
            )

            if ctx:
                await ctx.info("✅ Метрики получены успешно")
                await ctx.report_progress(progress=100, total=100)

            span.set_attribute("success", True)
            span.set_attribute("num_constituents", len(constituents))

            return ToolResult.from_dict(output.model_dump(mode="json"))

        except ValueError as e:
            # Для прямых вызовов (ctx=None) пробрасываем, чтобы сохранить поведение тестов
            if ctx is None:
                raise
            error_type = ErrorMapper.get_error_type_for_exception(e)
            if _metrics:
                _metrics.inc_tool_error(tool_name, error_type)
            span.set_attribute("error", str(e))
            span.set_attribute("error_type", error_type)
            error_model = ErrorMapper.map_exception(e)
            output = GetIndexConstituentsMetricsOutput.from_error(error_model)
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
            output = GetIndexConstituentsMetricsOutput.from_error(error_model)
            return ToolResult.from_dict(output.model_dump(mode="json"))

        finally:
            if _metrics and start_ts:
                _metrics.observe_latency(tool_name, time.perf_counter() - start_ts)
