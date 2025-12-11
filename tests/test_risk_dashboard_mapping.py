from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, List

from pydantic import BaseModel, Field

from risk_analytics_mcp.models import (
    ConcentrationMetrics,
    PortfolioMetrics,
    PortfolioRiskBasicOutput,
    PortfolioRiskPerInstrument,
    StressScenarioResult,
    VarLightResult,
)


class DashboardMetric(BaseModel):
    id: str
    label: str
    value: float
    unit: str
    severity: str


class DashboardChart(BaseModel):
    id: str
    type: str
    title: str
    x_axis: dict
    y_axis: dict
    series: List[dict]


class DashboardTable(BaseModel):
    id: str
    title: str
    columns: List[dict]
    data_ref: str


class DashboardAlert(BaseModel):
    id: str
    severity: str
    message: str
    related_ids: List[str] = Field(default_factory=list)


class RiskDashboardSpec(BaseModel):
    """
    Упрощённая модель RiskDashboardSpec по SPEC_risk_dashboard_agi_ui.
    """

    metadata: dict
    metrics: List[DashboardMetric]
    charts: List[DashboardChart]
    tables: List[DashboardTable]
    alerts: List[DashboardAlert]


class A2AOutput(BaseModel):
    """
    Минимальный A2A-выход агента по REQUIREMENTS_moex-market-analyst-agent.
    """

    text: str
    tables: List[dict] = Field(default_factory=list)
    dashboard: RiskDashboardSpec
    debug: dict | None = None


class A2AResponse(BaseModel):
    output: A2AOutput


def build_dashboard_from_portfolio(
    output: PortfolioRiskBasicOutput,
    *,
    scenario_type: str,
    portfolio_id: str | None = None,
    base_currency: str = "RUB",
) -> RiskDashboardSpec:
    """
    Пример маппинга PortfolioRiskBasicOutput → RiskDashboardSpec для сценария 7.

    Этот helper иллюстрирует роль DashboardSubagent и служит регрессионным
    тестом для формата дашборда.
    """
    metadata = {
        "as_of": output.metadata.get("as_of") or datetime.now(tz=timezone.utc).isoformat(),
        "scenario_type": scenario_type,
        "base_currency": base_currency,
        "portfolio_id": portfolio_id,
    }

    metrics: List[DashboardMetric] = []
    if output.portfolio_metrics.total_return_pct is not None:
        metrics.append(
            DashboardMetric(
                id="portfolio_total_return_pct",
                label="Доходность портфеля за период",
                value=output.portfolio_metrics.total_return_pct,
                unit="%",
                severity="info",
            )
        )
    if output.var_light is not None and output.var_light.var_pct is not None:
        metrics.append(
            DashboardMetric(
                id="portfolio_var_light",
                label="Var_light (95%, 1д)",
                value=output.var_light.var_pct,
                unit="%",
                severity="medium",
            )
        )

    charts = [
        DashboardChart(
            id="equity_curve",
            type="line",
            title="Динамика стоимости портфеля",
            x_axis={"field": "date", "label": "Дата"},
            y_axis={"field": "value", "label": "Стоимость, млн ₽"},
            series=[
                {
                    "id": "portfolio",
                    "label": "Портфель",
                    "data_ref": "time_series.portfolio_value",
                }
            ],
        ),
        DashboardChart(
            id="weights_by_ticker",
            type="bar",
            title="Структура портфеля по бумагам",
            x_axis={"field": "ticker", "label": "Тикер"},
            y_axis={"field": "weight_pct", "label": "Вес, %"},
            series=[
                {
                    "id": "weights",
                    "label": "Вес бумаги",
                    "data_ref": "tables.positions",
                }
            ],
        ),
    ]

    tables = [
        DashboardTable(
            id="positions",
            title="Позиции портфеля",
            columns=[
                {"id": "ticker", "label": "Тикер"},
                {"id": "weight_pct", "label": "Вес, %"},
                {"id": "total_return_pct", "label": "Доходность, %"},
                {"id": "annualized_volatility_pct", "label": "Волатильность, %"},
                {"id": "max_drawdown_pct", "label": "Max DD, %"},
            ],
            data_ref="data.per_instrument",
        ),
        DashboardTable(
            id="stress_results",
            title="Результаты стресс-сценариев",
            columns=[
                {"id": "id", "label": "Сценарий"},
                {"id": "description", "label": "Описание"},
                {"id": "pnl_pct", "label": "P&L, %"},
            ],
            data_ref="data.stress_results",
        ),
    ]

    alerts: List[DashboardAlert] = []
    top1 = output.concentration_metrics.top1_weight_pct
    if top1 is not None and top1 > 50.0:
        alerts.append(
            DashboardAlert(
                id="issuer_concentration",
                severity="high",
                message="Концентрация по эмитенту превышает 50%.",
                related_ids=["metric:top1_weight_pct"],
            )
        )

    return RiskDashboardSpec(
        metadata=metadata,
        metrics=metrics,
        charts=charts,
        tables=tables,
        alerts=alerts,
    )


def _sample_portfolio_output() -> PortfolioRiskBasicOutput:
    per_instrument = [
        PortfolioRiskPerInstrument(
            ticker="SBER",
            weight=0.6,
            total_return_pct=11.63,
            annualized_volatility_pct=20.0,
            max_drawdown_pct=5.0,
        ),
        PortfolioRiskPerInstrument(
            ticker="GAZP",
            weight=0.4,
            total_return_pct=8.0,
            annualized_volatility_pct=18.0,
            max_drawdown_pct=4.0,
        ),
    ]
    portfolio_metrics = PortfolioMetrics(
        total_return_pct=11.63,
        annualized_volatility_pct=15.0,
        max_drawdown_pct=6.0,
    )
    concentration_metrics = ConcentrationMetrics(
        top1_weight_pct=60.0,
        top3_weight_pct=100.0,
        top5_weight_pct=100.0,
        hhi=0.4,
    )
    stress_results = [
        StressScenarioResult(
            id="equity_-10_fx_+20",
            description="Падение акций на 10%, ослабление RUB на 20%",
            pnl_pct=-12.0,
            drivers={"equity_weight_pct": 100.0},
        )
    ]
    var_light = VarLightResult(
        method="parametric_normal",
        confidence_level=0.95,
        horizon_days=1,
        annualized_volatility_pct=15.0,
        var_pct=4.47,
    )
    metadata: dict[str, Any] = {
        "as_of": datetime(2025, 1, 1, 10, 0, tzinfo=timezone.utc).isoformat(),
        "from_date": "2024-01-01",
        "to_date": "2024-12-31",
        "rebalance": "buy_and_hold",
        "tickers": ["SBER", "GAZP"],
        "iss_base_url": "http://example/",
    }
    return PortfolioRiskBasicOutput.success(
        metadata=metadata,
        per_instrument=per_instrument,
        portfolio_metrics=portfolio_metrics,
        concentration_metrics=concentration_metrics,
        stress_results=stress_results,
        var_light=var_light,
    )


def test_build_dashboard_from_portfolio_basic_mapping():
    output = _sample_portfolio_output()
    spec = build_dashboard_from_portfolio(
        output,
        scenario_type="portfolio_risk_basic",
        portfolio_id="demo-portfolio-001",
    )

    assert spec.metadata["scenario_type"] == "portfolio_risk_basic"
    assert spec.metadata["portfolio_id"] == "demo-portfolio-001"
    assert spec.metadata["base_currency"] == "RUB"

    metric_ids = {m.id for m in spec.metrics}
    assert "portfolio_total_return_pct" in metric_ids
    assert "portfolio_var_light" in metric_ids

    total_return_metric = next(m for m in spec.metrics if m.id == "portfolio_total_return_pct")
    assert total_return_metric.value == 11.63

    var_metric = next(m for m in spec.metrics if m.id == "portfolio_var_light")
    assert var_metric.value == 4.47

    chart_ids = {c.id for c in spec.charts}
    assert {"equity_curve", "weights_by_ticker"} <= chart_ids

    positions_table = next(t for t in spec.tables if t.id == "positions")
    assert positions_table.data_ref == "data.per_instrument"

    stress_table = next(t for t in spec.tables if t.id == "stress_results")
    assert stress_table.data_ref == "data.stress_results"

    alert_ids = {a.id for a in spec.alerts}
    assert "issuer_concentration" in alert_ids


def test_risk_dashboard_spec_is_json_serializable():
    output = _sample_portfolio_output()
    spec = build_dashboard_from_portfolio(output, scenario_type="portfolio_risk_basic")

    payload = spec.model_dump(mode="json")
    # Проверяем, что payload можно отдать в AGI UI как JSON.
    json_text = json.dumps(payload, ensure_ascii=False)
    assert '"metrics"' in json_text
    assert '"charts"' in json_text
    assert '"tables"' in json_text


def test_a2a_response_contains_text_and_dashboard():
    """
    Проверка end-to-end контракта output.dashboard в A2A-ответе.
    """
    output = _sample_portfolio_output()
    dashboard = build_dashboard_from_portfolio(
        output,
        scenario_type="portfolio_risk_basic",
        portfolio_id="demo-portfolio-001",
    )

    a2a = A2AResponse(
        output=A2AOutput(
            text="Demo portfolio risk summary.",
            tables=[],
            dashboard=dashboard,
            debug={"scenario_type": "portfolio_risk_basic"},
        )
    )

    payload = a2a.model_dump(mode="json")
    assert "output" in payload
    assert payload["output"]["text"] == "Demo portfolio risk summary."
    assert "dashboard" in payload["output"]
    assert payload["output"]["dashboard"]["metadata"]["scenario_type"] == "portfolio_risk_basic"
