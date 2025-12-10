"""
Реализация инструмента compute_correlation_matrix.
"""

from __future__ import annotations

from typing import Dict, Sequence

from moex_iss_mcp.error_mapper import ErrorMapper, ToolErrorModel
from moex_iss_sdk import IssClient
from moex_iss_sdk.exceptions import TooManyTickersError
from moex_iss_sdk.utils import validate_date_range

from ..calculations import build_returns_by_ticker
from ..calculations.correlation import InsufficientDataError, compute_correlation_matrix
from ..models import CorrelationMatrixInput, CorrelationMatrixOutput


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


def compute_correlation_matrix_tool(
    payload,
    iss_client: IssClient,
    *,
    max_tickers: int,
    max_lookback_days: int,
) -> dict:
    """
    Обёртка, преобразующая исключения в стандартный формат ошибки инструмента.
    """
    try:
        output_model = compute_correlation_matrix_core(
            payload,
            iss_client,
            max_tickers=max_tickers,
            max_lookback_days=max_lookback_days,
        )
        return output_model.model_dump(mode="json")
    except Exception as exc:
        error_model = _map_error(exc)
        metadata = {}
        if isinstance(payload, dict):
            metadata = {
                "from_date": payload.get("from_date"),
                "to_date": payload.get("to_date"),
                "tickers": payload.get("tickers", []),
            }
        return CorrelationMatrixOutput.from_error(error_model, metadata=metadata).model_dump(mode="json")


__all__ = [
    "compute_correlation_matrix_core",
    "compute_correlation_matrix_tool",
]
