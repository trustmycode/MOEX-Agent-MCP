"""
Инструмент MCP: compute_tail_metrics

Считает базовые метрики хвоста индекса (доходность, волатильность, max drawdown)
по переданным OHLCV-данным и, опционально, весам компонентов.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, ValidationError

from .utils import ToolResult


class TailMetricsInput(BaseModel):
    ohlcv: Dict[str, List[Dict[str, Any]]] = Field(..., description="OHLCV по тикерам: {ticker: [{close: ...}, ...]}")
    constituents: Optional[List[Dict[str, Any]]] = Field(
        default=None,
        description="Опциональный список компонентов индекса с полем weight_pct",
    )


def _compute_basic_metrics_from_ohlcv(series: List[Dict[str, Any]]) -> Dict[str, float]:
    if not series or not isinstance(series, list):
        raise ValueError("empty_ohlcv")

    closes: List[float] = []
    for bar in series:
        if isinstance(bar, dict):
            close_val = bar.get("close") or bar.get("Close") or bar.get("CLOSE")
            if close_val is not None:
                try:
                    closes.append(float(close_val))
                except Exception:
                    continue

    if len(closes) < 2:
        raise ValueError("not_enough_points")

    first, last = closes[0], closes[-1]
    return_pct = (last / first - 1.0) * 100 if first else 0.0

    returns = []
    for i in range(1, len(closes)):
        prev = closes[i - 1]
        curr = closes[i]
        if prev:
            returns.append((curr / prev - 1.0))
    if returns:
        mean = sum(returns) / len(returns)
        var = sum((r - mean) ** 2 for r in returns) / len(returns)
        ann_vol_pct = (var ** 0.5) * math.sqrt(252) * 100
    else:
        ann_vol_pct = 0.0

    peak = closes[0]
    max_dd = 0.0
    for price in closes:
        if price > peak:
            peak = price
        dd = (price / peak - 1.0) * 100
        if dd < max_dd:
            max_dd = dd

    return {
        "return_pct": return_pct,
        "ann_vol_pct": ann_vol_pct,
        "max_dd_pct": max_dd,
    }


def compute_tail_metrics(input_model: TailMetricsInput) -> ToolResult:
    try:
        payload = input_model.model_dump()
        ohlcv = payload["ohlcv"]
        constituents = payload.get("constituents") or []

        weight_map: Dict[str, Optional[float]] = {}
        for c in constituents:
            if isinstance(c, dict) and c.get("ticker") is not None:
                weight_map[c["ticker"]] = c.get("weight_pct")

        per_instrument: List[Dict[str, Any]] = []
        errors: List[str] = []

        for ticker, series in ohlcv.items():
            try:
                metrics = _compute_basic_metrics_from_ohlcv(series)
            except Exception as exc:
                errors.append(f"{ticker}: {type(exc).__name__}")
                continue

            weight_pct = weight_map.get(ticker)
            weight_fraction = (float(weight_pct) / 100.0) if weight_pct is not None else None

            per_instrument.append(
                {
                    "ticker": ticker,
                    "weight": weight_fraction,
                    "total_return_pct": metrics.get("return_pct"),
                    "annualized_volatility_pct": metrics.get("ann_vol_pct"),
                    "max_drawdown_pct": metrics.get("max_dd_pct"),
                }
            )

        if not per_instrument:
            return ToolResult.error(
                error_type="tail_metrics_empty",
                message="Не удалось посчитать метрики по хвосту индекса",
                details={"errors": errors},
            )

        result_data = {
            "per_instrument": per_instrument,
            "scenario": "index_tail_analysis",
        }

        if errors:
            return ToolResult.from_dict({"data": result_data, "error": {"message": "; ".join(errors)}})

        return ToolResult.success(data=result_data)

    except ValidationError as exc:
        return ToolResult.error(
            error_type="validation_error",
            message="Некорректные аргументы compute_tail_metrics",
            details={"errors": exc.errors()},
        )
    except Exception as exc:
        return ToolResult.error(
            error_type="internal_error",
            message=str(exc),
        )

