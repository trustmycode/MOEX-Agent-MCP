"""
Инструмент issuer_peers_compare: сравнение эмитента с пирами по ключевым метрикам.
"""

import asyncio
import time
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from fastmcp import Context
from opentelemetry import trace
from pydantic import Field
from pydantic.fields import FieldInfo

from moex_iss_sdk import IssClient
from moex_iss_sdk.error_mapper import ErrorMapper, ToolErrorModel
from moex_iss_sdk.exceptions import InvalidTickerError
from moex_iss_sdk.utils import utc_now

from ..calculations import build_peer_metrics, compute_metric_ranks, derive_flags, has_meaningful_metrics
from ..mcp_instance import mcp
from ..models import IssuerPeersCompareInput, IssuerPeersComparePeer, IssuerPeersCompareReport
from ..providers import FundamentalsDataProvider
from ..telemetry import NullTracing
from ..tools.utils import ToolResult

_iss_client: IssClient | None = None
_fundamentals_provider: FundamentalsDataProvider | None = None
_metrics = None
_tracing = NullTracing()
_max_peers: int | None = None
_default_index: str | None = None
_NOOP_SPAN = type("NoopSpan", (), {"set_attribute": lambda self, *args, **kwargs: None})()


def init_tool_dependencies(
    iss_client: IssClient,
    fundamentals_provider: FundamentalsDataProvider,
    metrics,
    tracing,
    max_peers: int,
    default_index_ticker: Optional[str],
) -> None:
    """Инициализировать зависимости для issuer_peers_compare."""
    global _iss_client, _fundamentals_provider, _metrics, _tracing, _max_peers, _default_index
    _iss_client = iss_client
    _fundamentals_provider = fundamentals_provider
    _metrics = metrics
    _tracing = tracing or NullTracing()
    _max_peers = max_peers
    _default_index = (default_index_ticker or "IMOEX").upper()


tracer = trace.get_tracer(__name__)


def _resolve_base_ticker(input_model: IssuerPeersCompareInput) -> str:
    if input_model.ticker:
        return input_model.ticker
    if input_model.isin:
        return input_model.isin
    if input_model.issuer_id:
        return str(input_model.issuer_id)
    raise ValueError("Ticker is required to fetch fundamentals")


def _select_peer_tickers(
    base_ticker: str,
    input_model: IssuerPeersCompareInput,
) -> Tuple[list[str], dict[str, str | None]]:
    """
    Определить список пиров (тикеров) и карту sector по тикеру.
    """
    sector_by_ticker: dict[str, str | None] = {}

    if input_model.peer_tickers:
        tickers = [t for t in input_model.peer_tickers if t != base_ticker]
        return tickers[: input_model.max_peers], sector_by_ticker

    if _iss_client is None:
        return [], sector_by_ticker

    index_ticker = (input_model.index_ticker or _default_index or "IMOEX").upper()
    as_of_date = input_model.as_of_date or utc_now().date()

    constituents = _iss_client.get_index_constituents(index_ticker, as_of_date)
    filtered: list[str] = []
    for member in constituents:
        ticker = (member.ticker or "").upper()
        if not ticker or ticker == base_ticker:
            continue
        sector = member.sector.upper() if member.sector else None
        sector_by_ticker[ticker] = sector
        if input_model.sector and sector and sector != input_model.sector:
            continue
        filtered.append(ticker)

    return filtered[: input_model.max_peers], sector_by_ticker


def _load_fundamentals(
    tickers: Sequence[str],
    sector_by_ticker: Mapping[str, Optional[str]],
) -> list[IssuerPeersComparePeer]:
    if _fundamentals_provider is None:
        raise ValueError("FundamentalsDataProvider is not initialized")
    peers: list[IssuerPeersComparePeer] = []
    fundamentals_map = _fundamentals_provider.get_issuer_fundamentals_many(tickers)
    for ticker, fundamentals in fundamentals_map.items():
        peer = build_peer_metrics(fundamentals, sector_hint=sector_by_ticker.get(ticker))
        if has_meaningful_metrics(peer):
            peers.append(peer)
    return peers


def _map_error(error: Exception) -> ToolErrorModel:
    if isinstance(error, InvalidTickerError):
        return ToolErrorModel(error_type="INVALID_TICKER", message=str(error) or "Invalid ticker")
    if isinstance(error, ValueError) and "peers" in (str(error).lower()):
        return ToolErrorModel(error_type="NO_PEERS_FOUND", message=str(error))
    if isinstance(error, ValueError) and "fundamental" in (str(error).lower()):
        return ToolErrorModel(error_type="NO_FUNDAMENTAL_DATA", message=str(error))
    if isinstance(error, ValueError):
        return ToolErrorModel(error_type="VALIDATION_ERROR", message=str(error))
    return ErrorMapper.map_exception(error)


def issuer_peers_compare_core(payload: Dict[str, Any]) -> IssuerPeersCompareReport:
    if _fundamentals_provider is None:
        raise ValueError("FundamentalsDataProvider is not initialized")
    normalized_payload = dict(payload)
    if normalized_payload.get("max_peers") is None:
        normalized_payload["max_peers"] = _max_peers or 10
    input_model = IssuerPeersCompareInput.model_validate(normalized_payload)
    base_ticker = _resolve_base_ticker(input_model)
    peer_tickers, sector_by_ticker = _select_peer_tickers(base_ticker, input_model)

    if not peer_tickers:
        raise ValueError("No peers found for the given filters")

    base_fundamentals = _fundamentals_provider.get_issuer_fundamentals(base_ticker)  # type: ignore[arg-type]
    base_peer = build_peer_metrics(base_fundamentals, sector_hint=sector_by_ticker.get(base_ticker))
    if not has_meaningful_metrics(base_peer):
        raise ValueError("No fundamental data available for base issuer")

    peers = _load_fundamentals(peer_tickers, sector_by_ticker)
    if not peers:
        raise ValueError("No peers found for the given filters")

    ranking = compute_metric_ranks(base_peer, peers)
    flags = derive_flags(base_peer, ranking)

    metadata = {
        "as_of": (base_peer.as_of or utc_now()).isoformat(),
        "base_ticker": base_ticker,
        "index_ticker": input_model.index_ticker or _default_index,
        "sector_filter": input_model.sector,
        "peer_count": len(peers),
        "max_peers": input_model.max_peers,
    }

    return IssuerPeersCompareReport.success(
        metadata=metadata,
        base_issuer=base_peer,
        peers=peers,
        ranking=ranking,
        flags=flags,
    )


@mcp.tool(
    name="issuer_peers_compare",
    description="""📊 Сравнить эмитента с пирами по базовым мультипликаторам и рыночным метрикам.

Формирует компактный peers-отчёт: базовый эмитент, список пиров, ранжирование по P/E, EV/EBITDA,
NetDebt/EBITDA, ROE и дивидендной доходности, а также простые флаги (overvalued/undervalued, leverage).
""",
)
async def issuer_peers_compare(
    ticker: Optional[str] = Field(default=None, description="Ticker целевого эмитента"),
    isin: Optional[str] = Field(default=None, description="ISIN, если тикер не указан"),
    issuer_id: Optional[str] = Field(default=None, description="MOEX issuer id (опционально)"),
    index_ticker: Optional[str] = Field(default=None, description="Индекс для подбора пиров (например, IMOEX)"),
    sector: Optional[str] = Field(default=None, description="Фильтр по сектору/отрасли"),
    peer_tickers: Optional[List[str]] = Field(default=None, description="Явный список тикеров-пиров"),
    max_peers: Optional[int] = Field(default=None, description="Максимальное число пиров в отчёте"),
    as_of_date: Optional[str] = Field(default=None, description="Дата среза (YYYY-MM-DD)"),
    ctx: Context = None,
) -> ToolResult:
    """
    Построить сравнительный отчёт по эмитенту и его пирам.
    """
    tool_name = "issuer_peers_compare"
    start_ts = None

    if _fundamentals_provider is None or _iss_client is None:
        raise ValueError("Tool dependencies are not initialized")

    def _clean(value: Any) -> Any:
        return None if isinstance(value, FieldInfo) else value

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
                await ctx.info("🔍 Запуск сравнения эмитента с пирами")
                await ctx.report_progress(progress=0, total=100)

            payload: Dict[str, Any] = {
                "ticker": _clean(ticker),
                "isin": _clean(isin),
                "issuer_id": _clean(issuer_id),
                "index_ticker": _clean(index_ticker),
                "sector": _clean(sector),
                "peer_tickers": _clean(peer_tickers),
                "max_peers": _clean(max_peers) or _max_peers or 10,
                "as_of_date": _clean(as_of_date),
            }

            input_model = IssuerPeersCompareInput.model_validate(payload)
            base_ticker = _resolve_base_ticker(input_model)

            span.set_attribute("base_ticker", base_ticker)
            span.set_attribute("index_ticker", input_model.index_ticker or _default_index)
            span.set_attribute("sector", input_model.sector or "ANY")

            if ctx:
                await ctx.info("📡 Получение списка пиров")
                await ctx.report_progress(progress=20, total=100)

            peer_tickers, sector_by_ticker = await asyncio.to_thread(_select_peer_tickers, base_ticker, input_model)
            if not peer_tickers:
                raise ValueError("No peers found for the given filters")

            if ctx:
                await ctx.info(f"📊 Загрузка фундаментала для {1 + len(peer_tickers)} эмитентов")
                await ctx.report_progress(progress=45, total=100)

            base_fundamentals = await asyncio.to_thread(
                _fundamentals_provider.get_issuer_fundamentals, base_ticker  # type: ignore[arg-type]
            )
            base_peer = build_peer_metrics(base_fundamentals, sector_hint=sector_by_ticker.get(base_ticker))
            if not has_meaningful_metrics(base_peer):
                error = ToolErrorModel(
                    error_type="NO_FUNDAMENTAL_DATA",
                    message="No fundamental data available for base issuer",
                )
                output = IssuerPeersCompareReport.from_error(error, metadata={"base_ticker": base_ticker})
                return ToolResult.from_dict(output.model_dump(mode="json"))

            peers = await asyncio.to_thread(_load_fundamentals, peer_tickers, sector_by_ticker)
            if not peers:
                raise ValueError("No peers found for the given filters")

            if ctx:
                await ctx.info("📈 Расчёт ранжирования и флагов")
                await ctx.report_progress(progress=75, total=100)

            ranking = await asyncio.to_thread(compute_metric_ranks, base_peer, peers)
            flags = await asyncio.to_thread(derive_flags, base_peer, ranking)

            metadata = {
                "as_of": (base_peer.as_of or utc_now()).isoformat(),
                "base_ticker": base_ticker,
                "index_ticker": input_model.index_ticker or _default_index,
                "sector_filter": input_model.sector,
                "peer_count": len(peers),
                "max_peers": input_model.max_peers,
            }

            output = IssuerPeersCompareReport.success(
                metadata=metadata,
                base_issuer=base_peer,
                peers=peers,
                ranking=ranking,
                flags=flags,
            )

            if ctx:
                await ctx.info("✅ Отчёт по пирам сформирован")
                await ctx.report_progress(progress=100, total=100)

            span.set_attribute("success", True)
            span.set_attribute("peer_count", len(peers))
            return ToolResult.from_dict(output.model_dump(mode="json"))

        except Exception as exc:
            error = _map_error(exc)
            if _metrics:
                _metrics.inc_tool_error(tool_name, error.error_type)
            span.set_attribute("error", str(exc))
            span.set_attribute("error_type", error.error_type)
            if ctx:
                await ctx.error(f"❌ Ошибка: {exc}")
            output = IssuerPeersCompareReport.from_error(
                error,
                metadata={"ticker": _clean(ticker), "index_ticker": _clean(index_ticker)},
            )
            return ToolResult.from_dict(output.model_dump(mode="json"))

        finally:
            if _metrics and start_ts:
                _metrics.observe_latency(tool_name, time.perf_counter() - start_ts)


__all__ = ["issuer_peers_compare_core", "issuer_peers_compare", "init_tool_dependencies"]
