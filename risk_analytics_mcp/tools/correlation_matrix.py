"""
Инструмент compute_correlation_matrix для расчёта матрицы корреляций.

Вычисляет корреляционную матрицу доходностей для списка инструментов.
"""

import asyncio
import time
from typing import List, Optional, Sequence

from fastmcp import Context
from opentelemetry import trace
from pydantic import Field

from moex_iss_sdk import IssClient
from moex_iss_sdk.error_mapper import ErrorMapper, ToolErrorModel
from moex_iss_sdk.exceptions import TooManyTickersError
from moex_iss_sdk.utils import validate_date_range

from ..calculations import build_returns_by_ticker
from ..calculations.correlation import InsufficientDataError, compute_correlation_matrix as calc_correlation_matrix
from ..mcp_instance import mcp
from ..models import CorrelationMatrixInput, CorrelationMatrixOutput
from ..tools.utils import ToolResult
from ..telemetry import NullTracing

# Глобальные зависимости (инициализируются при запуске сервера)
_iss_client = None
_metrics = None
_tracing = NullTracing()
_max_tickers = None
_max_lookback_days = None
_NOOP_SPAN = type("NoopSpan", (), {"set_attribute": lambda self, *args, **kwargs: None})()


def init_tool_dependencies(iss_client, metrics, tracing, max_tickers, max_lookback_days):
    """Инициализировать зависимости для инструментов."""
    global _iss_client, _metrics, _tracing, _max_tickers, _max_lookback_days
    _iss_client = iss_client
    _metrics = metrics
    _tracing = tracing or NullTracing()
    _max_tickers = max_tickers
    _max_lookback_days = max_lookback_days


tracer = trace.get_tracer(__name__)


def _map_error(exc: Exception) -> ToolErrorModel:
    """Преобразовать исключение в ToolErrorModel."""
    if isinstance(exc, InsufficientDataError):
        return ToolErrorModel(
            error_type=getattr(exc, "error_type", "INSUFFICIENT_DATA"),
            message=str(exc) or "Insufficient data for correlation",
            details={"exception_type": type(exc).__name__},
        )
    return ErrorMapper.map_exception(exc)


def _fetch_ohlcv_for_tickers(
    iss_client: IssClient,
    tickers: Sequence[str],
    *,
    from_date,
    to_date,
    max_lookback_days: int,
):
    data: Dict[str, Sequence] = {}
    for ticker in tickers:
        data[ticker] = iss_client.get_ohlcv_series(
            ticker=ticker,
            board=iss_client.settings.default_board,
            from_date=from_date,
            to_date=to_date,
            interval="1d",
            max_lookback_days=max_lookback_days,
        )
    return data


def _map_error(exc: Exception) -> ToolErrorModel:
    if isinstance(exc, InsufficientDataError):
        return ToolErrorModel(
            error_type=getattr(exc, "error_type", "INSUFFICIENT_DATA"),
            message=str(exc) or "Insufficient data for correlation",
            details={"exception_type": type(exc).__name__},
        )
    return ErrorMapper.map_exception(exc)


def compute_correlation_matrix_core(
    payload,
    iss_client: IssClient,
    *,
    max_tickers: int,
    max_lookback_days: int,
) -> CorrelationMatrixOutput:
    input_model = payload if isinstance(payload, CorrelationMatrixInput) else CorrelationMatrixInput.model_validate(payload)

    if len(input_model.tickers) > max_tickers:
        raise TooManyTickersError(
            f"Too many tickers: {len(input_model.tickers)} > {max_tickers}",
            details={"tickers": input_model.tickers},
        )
    validate_date_range(input_model.from_date, input_model.to_date, max_lookback_days=max_lookback_days)

    ohlcv_by_ticker = _fetch_ohlcv_for_tickers(
        iss_client,
        input_model.tickers,
        from_date=input_model.from_date,
        to_date=input_model.to_date,
        max_lookback_days=max_lookback_days,
    )
    returns_by_ticker = build_returns_by_ticker(ohlcv_by_ticker)
    matrix, calc_metadata = compute_correlation_matrix(input_model.tickers, returns_by_ticker)

    metadata = {
        "from_date": input_model.from_date.isoformat(),
        "to_date": input_model.to_date.isoformat(),
        "tickers": input_model.tickers,
        "method": calc_metadata.get("method"),
        "num_observations": calc_metadata.get("num_observations"),
        "iss_base_url": iss_client.settings.base_url,
    }

    return CorrelationMatrixOutput.success(metadata=metadata, tickers=input_model.tickers, matrix=matrix)


async def _fetch_ohlcv_for_tickers_async(
    tickers: Sequence[str],
    *,
    from_date,
    to_date,
    max_lookback_days: int,
):
    """Асинхронная версия получения OHLCV данных."""
    data: dict[str, Sequence] = {}
    for ticker in tickers:
        data[ticker] = await asyncio.to_thread(
            _iss_client.get_ohlcv_series,
            ticker=ticker,
            board=_iss_client.settings.default_board,
            from_date=from_date,
            to_date=to_date,
            interval="1d",
            max_lookback_days=max_lookback_days,
        )
    return data


@mcp.tool(
    name="compute_correlation_matrix",
    description="""📊 Вычислить матрицу корреляций доходностей для списка инструментов.

Инструмент рассчитывает корреляционную матрицу на основе исторических данных
о доходах инструментов за указанный период.

Примеры использования:
- Рассчитать корреляцию между акциями банков
- Оценить диверсификацию портфеля
- Найти инструменты с низкой корреляцией
""",
)
async def compute_correlation_matrix(
    tickers: List[str] = Field(
        ...,
        description="Список тикеров для построения матрицы корреляций (минимум 2)",
    ),
    from_date: str = Field(
        ...,
        description="Начальная дата периода в формате YYYY-MM-DD (включительно)",
    ),
    to_date: str = Field(
        ...,
        description="Конечная дата периода в формате YYYY-MM-DD (включительно)",
    ),
    ctx: Context = None,
) -> ToolResult:
    """
    Вычислить матрицу корреляций доходностей для списка инструментов.

    Args:
        tickers: Список тикеров для построения матрицы корреляций (минимум 2)
        from_date: Начальная дата периода в формате YYYY-MM-DD (включительно)
        to_date: Конечная дата периода в формате YYYY-MM-DD (включительно)
        ctx: Контекст для логирования и отслеживания прогресса

    Returns:
        ToolResult: Результат с матрицей корреляций и метаданными

    Raises:
        McpError: При ошибках выполнения или валидации параметров
    """
    tool_name = "compute_correlation_matrix"
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
                await ctx.info(f"🚀 Начинаем расчёт матрицы корреляций для {len(tickers)} инструментов")
                await ctx.report_progress(progress=0, total=100)

            # Настройка атрибутов спана
            span.set_attribute("tickers_count", len(tickers))
            span.set_attribute("from_date", from_date)
            span.set_attribute("to_date", to_date)

            # Валидация входных данных
            if ctx:
                await ctx.info("🔍 Валидация параметров")
                await ctx.report_progress(progress=10, total=100)

            payload = {
                "tickers": tickers,
                "from_date": from_date,
                "to_date": to_date,
            }
            input_model = CorrelationMatrixInput.model_validate(payload)

            # Проверка лимитов
            if len(input_model.tickers) > _max_tickers:
                raise TooManyTickersError(
                    f"Too many tickers: {len(input_model.tickers)} > {_max_tickers}",
                    details={"tickers": input_model.tickers},
                )
            validate_date_range(input_model.from_date, input_model.to_date, max_lookback_days=_max_lookback_days)

            # Получение данных
            if ctx:
                await ctx.info("📡 Запрос исторических данных")
                await ctx.report_progress(progress=20, total=100)

            ohlcv_by_ticker = await _fetch_ohlcv_for_tickers_async(
                input_model.tickers,
                from_date=input_model.from_date,
                to_date=input_model.to_date,
                max_lookback_days=_max_lookback_days,
            )

            if ctx:
                await ctx.info("📊 Расчёт доходностей")
                await ctx.report_progress(progress=50, total=100)

            returns_by_ticker = await asyncio.to_thread(build_returns_by_ticker, ohlcv_by_ticker)

            if ctx:
                await ctx.info("📈 Расчёт матрицы корреляций")
                await ctx.report_progress(progress=70, total=100)

            matrix, calc_metadata = await asyncio.to_thread(
                calc_correlation_matrix, input_model.tickers, returns_by_ticker
            )

            metadata = {
                "from_date": input_model.from_date.isoformat(),
                "to_date": input_model.to_date.isoformat(),
                "tickers": input_model.tickers,
                "method": calc_metadata.get("method"),
                "num_observations": calc_metadata.get("num_observations"),
                "iss_base_url": _iss_client.settings.base_url,
            }

            output = CorrelationMatrixOutput.success(metadata=metadata, tickers=input_model.tickers, matrix=matrix)

            if ctx:
                await ctx.info("✅ Матрица корреляций рассчитана успешно")
                await ctx.report_progress(progress=100, total=100)

            span.set_attribute("success", True)
            span.set_attribute("matrix_size", len(matrix))

            return ToolResult.from_dict(output.model_dump(mode="json"))

        except ValueError as e:
            error_type = ErrorMapper.get_error_type_for_exception(e)
            if _metrics:
                _metrics.inc_tool_error(tool_name, error_type)
            span.set_attribute("error", str(e))
            span.set_attribute("error_type", error_type)
            if ctx:
                await ctx.error(f"❌ Ошибка валидации: {e}")
            error_model = _map_error(e)
            output = CorrelationMatrixOutput.from_error(error_model)
            return ToolResult.from_dict(output.model_dump(mode="json"))

        except Exception as exc:
            error_type = ErrorMapper.get_error_type_for_exception(exc)
            if _metrics:
                _metrics.inc_tool_error(tool_name, error_type)
            span.set_attribute("error", str(exc))
            span.set_attribute("error_type", error_type)

            if ctx:
                await ctx.error(f"❌ Ошибка выполнения: {exc}")

            error_model = _map_error(exc)
            metadata = {
                "from_date": from_date,
                "to_date": to_date,
                "tickers": tickers,
            }
            output = CorrelationMatrixOutput.from_error(error_model, metadata=metadata)

            return ToolResult.from_dict(output.model_dump(mode="json"))

        finally:
            if _metrics and start_ts:
                _metrics.observe_latency(tool_name, time.perf_counter() - start_ts)


__all__ = [
    "compute_correlation_matrix_core",
    "compute_correlation_matrix",
]
