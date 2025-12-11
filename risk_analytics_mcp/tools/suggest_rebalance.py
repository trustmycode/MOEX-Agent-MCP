"""
Инструмент suggest_rebalance для формирования предложений по ребалансировке портфеля.

Вычисляет детерминированное предложение по ребалансировке на основе входных
позиций и заданного профиля риска (ограничения по классам активов, концентрации,
обороту).
"""

import asyncio
import time
from typing import Any, Dict, List, Optional

from fastmcp import Context
from opentelemetry import trace
from pydantic import Field

from moex_iss_sdk.utils import utc_now
from moex_iss_sdk.error_mapper import ErrorMapper, ToolErrorModel

from ..calculations import compute_rebalance, RebalanceError
from ..mcp_instance import mcp
from ..models import (
    RebalanceInput,
    RebalanceOutput,
    RebalancePosition,
    RebalanceSummary,
    RebalanceTrade,
    RiskProfileTarget,
)
from ..tools.utils import ToolResult
from ..telemetry import NullTracing

# Глобальные зависимости (инициализируются при запуске сервера)
_metrics = None
_tracing = NullTracing()
_NOOP_SPAN = type("NoopSpan", (), {"set_attribute": lambda self, *args, **kwargs: None})()


def init_tool_dependencies(metrics, tracing):
    """Инициализировать зависимости для инструмента suggest_rebalance."""
    global _metrics, _tracing
    _metrics = metrics
    _tracing = tracing or NullTracing()


tracer = trace.get_tracer(__name__)


def suggest_rebalance_core(input_payload) -> RebalanceOutput:
    """
    Выполнить расчёт ребалансировки без привязки к FastMCP.

    Args:
        input_payload: Входные данные (dict или RebalanceInput).

    Returns:
        RebalanceOutput с целевыми весами, сделками и сводкой.
    """
    input_model = (
        input_payload
        if isinstance(input_payload, RebalanceInput)
        else RebalanceInput.model_validate(input_payload)
    )

    # Подготовка данных для расчётной функции
    positions_data = [
        {
            "ticker": pos.ticker,
            "current_weight": pos.current_weight,
            "current_value": pos.current_value,
            "asset_class": pos.asset_class,
            "issuer": pos.issuer,
        }
        for pos in input_model.positions
    ]

    risk_profile_data = {
        "max_equity_weight": input_model.risk_profile.max_equity_weight,
        "max_fixed_income_weight": input_model.risk_profile.max_fixed_income_weight,
        "max_fx_weight": input_model.risk_profile.max_fx_weight,
        "max_single_position_weight": input_model.risk_profile.max_single_position_weight,
        "max_issuer_weight": input_model.risk_profile.max_issuer_weight,
        "max_turnover": input_model.risk_profile.max_turnover,
        "target_asset_class_weights": input_model.risk_profile.target_asset_class_weights,
    }

    # Вызов расчётной логики
    result = compute_rebalance(
        positions=positions_data,
        risk_profile=risk_profile_data,
        total_portfolio_value=input_model.total_portfolio_value,
    )

    # Преобразование результата в Pydantic-модели
    trades = [
        RebalanceTrade(
            ticker=t["ticker"],
            side=t["side"],
            weight_delta=t["weight_delta"],
            target_weight=t["target_weight"],
            estimated_value=t.get("estimated_value"),
            reason=t.get("reason", "rebalance"),
        )
        for t in result.trades
    ]

    summary = RebalanceSummary(
        total_turnover=result.summary["total_turnover"],
        turnover_within_limit=result.summary["turnover_within_limit"],
        positions_changed=result.summary["positions_changed"],
        concentration_issues_resolved=result.summary["concentration_issues_resolved"],
        asset_class_issues_resolved=result.summary["asset_class_issues_resolved"],
        warnings=result.summary.get("warnings", []),
    )

    metadata = {
        "as_of": utc_now().isoformat(),
        "input_positions_count": len(input_model.positions),
        "total_portfolio_value": input_model.total_portfolio_value,
        "risk_profile": {
            "max_turnover": input_model.risk_profile.max_turnover,
            "max_single_position_weight": input_model.risk_profile.max_single_position_weight,
            "max_issuer_weight": input_model.risk_profile.max_issuer_weight,
        },
    }

    return RebalanceOutput.success(
        metadata=metadata,
        target_weights=result.target_weights,
        trades=trades,
        summary=summary,
    )


@mcp.tool(
    name="suggest_rebalance",
    description="""📊 Предложить ребалансировку портфеля.

Инструмент анализирует текущий портфель и формирует детерминированное предложение
по ребалансировке с учётом заданного профиля риска:
- ограничения по классам активов (макс. доля акций/облигаций/FX),
- лимиты концентрации по позициям и эмитентам,
- максимально допустимый оборот (turnover).

Примеры использования:
- Привести портфель к целевой аллокации по классам активов
- Снизить концентрацию по отдельным позициям
- Перебалансировать портфель в рамках ограничений оборота
""",
)
async def suggest_rebalance(
    positions: List[Dict[str, Any]] = Field(
        ...,
        description="Список текущих позиций портфеля с весами и метаданными",
    ),
    total_portfolio_value: Optional[float] = Field(
        default=None,
        description="Общая стоимость портфеля (для расчёта сделок в валюте)",
    ),
    risk_profile: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Целевой профиль риска с ограничениями по классам активов, концентрации и обороту",
    ),
    ctx: Context = None,
) -> ToolResult:
    """
    Предложить ребалансировку портфеля.

    Args:
        positions: Список текущих позиций с тикерами, весами и классами активов
        total_portfolio_value: Общая стоимость портфеля (опционально)
        risk_profile: Целевой профиль риска и ограничения
        ctx: Контекст для логирования и отслеживания прогресса

    Returns:
        ToolResult: Результат с целевыми весами, сделками и сводкой

    Raises:
        McpError: При ошибках выполнения или валидации параметров
    """
    tool_name = "suggest_rebalance"
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
                await ctx.info(f"🚀 Начинаем расчёт ребалансировки для портфеля из {len(positions)} позиций")
                await ctx.report_progress(progress=0, total=100)

            # Настройка атрибутов спана
            span.set_attribute("positions_count", len(positions))
            if total_portfolio_value:
                span.set_attribute("total_portfolio_value", total_portfolio_value)

            # Валидация входных данных
            if ctx:
                await ctx.info("🔍 Валидация параметров")
                await ctx.report_progress(progress=20, total=100)

            payload = {
                "positions": positions,
            }
            if total_portfolio_value is not None:
                payload["total_portfolio_value"] = total_portfolio_value
            if risk_profile is not None:
                payload["risk_profile"] = risk_profile

            input_model = RebalanceInput.model_validate(payload)

            # Расчёт ребалансировки
            if ctx:
                await ctx.info("📊 Расчёт ребалансировки")
                await ctx.report_progress(progress=50, total=100)

            output = await asyncio.to_thread(suggest_rebalance_core, input_model)

            if ctx:
                trades_count = len(output.trades)
                await ctx.info(f"✅ Ребалансировка рассчитана: {trades_count} сделок предложено")
                await ctx.report_progress(progress=100, total=100)

            span.set_attribute("success", True)
            span.set_attribute("trades_count", len(output.trades))
            if output.summary:
                span.set_attribute("total_turnover", output.summary.total_turnover)

            return ToolResult.from_dict(output.model_dump(mode="json"))

        except RebalanceError as e:
            error_type = e.error_type
            if _metrics:
                _metrics.inc_tool_error(tool_name, error_type)
            span.set_attribute("error", str(e))
            span.set_attribute("error_type", error_type)

            if ctx:
                await ctx.error(f"❌ Ошибка ребалансировки: {e.message}")

            error_model = ToolErrorModel(
                error_type=error_type,
                message=e.message,
                details=e.details,
            )
            metadata = {
                "input_positions_count": len(positions),
            }
            output = RebalanceOutput.from_error(error_model, metadata=metadata)
            return ToolResult.from_dict(output.model_dump(mode="json"))

        except ValueError as e:
            error_type = ErrorMapper.get_error_type_for_exception(e)
            if _metrics:
                _metrics.inc_tool_error(tool_name, error_type)
            span.set_attribute("error", str(e))
            span.set_attribute("error_type", error_type)

            if ctx:
                await ctx.error(f"❌ Ошибка валидации: {e}")

            error_model = ErrorMapper.map_exception(e)
            output = RebalanceOutput.from_error(error_model)
            return ToolResult.from_dict(output.model_dump(mode="json"))

        except Exception as exc:
            error_type = ErrorMapper.get_error_type_for_exception(exc)
            if _metrics:
                _metrics.inc_tool_error(tool_name, error_type)
            span.set_attribute("error", str(exc))
            span.set_attribute("error_type", error_type)

            if ctx:
                await ctx.error(f"❌ Неожиданная ошибка: {exc}")

            error_model = ErrorMapper.map_exception(exc)
            metadata = {
                "input_positions_count": len(positions) if positions else 0,
            }
            output = RebalanceOutput.from_error(error_model, metadata=metadata)
            return ToolResult.from_dict(output.model_dump(mode="json"))

        finally:
            if _metrics and start_ts:
                _metrics.observe_latency(tool_name, time.perf_counter() - start_ts)


__all__ = ["suggest_rebalance_core", "suggest_rebalance", "init_tool_dependencies"]
