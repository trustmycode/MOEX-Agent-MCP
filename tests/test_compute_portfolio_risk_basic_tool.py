from datetime import datetime, timezone, date
from types import SimpleNamespace

import pytest

from risk_analytics_mcp.models import PortfolioRiskInput, PortfolioPosition
from risk_analytics_mcp.tools import compute_portfolio_risk_basic_core, compute_portfolio_risk_basic_tool
from moex_iss_sdk.models import OhlcvBar


class StubIssClient:
    def __init__(self):
        self.settings = SimpleNamespace(base_url="http://stub-iss/", default_board="TQBR")

    def get_ohlcv_series(self, ticker: str, board: str, from_date, to_date, interval: str, max_lookback_days: int):
        base = 100.0 if ticker == "AAA" else 200.0
        return [
            OhlcvBar(ts=datetime(2024, 1, 1, tzinfo=timezone.utc), open=base, high=base, low=base, close=base),
            OhlcvBar(ts=datetime(2024, 1, 2, tzinfo=timezone.utc), open=base * 1.05, high=base * 1.05, low=base * 1.05, close=base * 1.05),
        ]


def test_compute_portfolio_risk_basic_core_success():
    iss = StubIssClient()
    input_model = PortfolioRiskInput(
        positions=[PortfolioPosition(ticker="AAA", weight=0.5), PortfolioPosition(ticker="BBB", weight=0.5)],
        from_date=date(2024, 1, 1),
        to_date=date(2024, 1, 2),
    )

    output = compute_portfolio_risk_basic_core(input_model, iss, max_tickers=5, max_lookback_days=10)

    assert output.error is None
    assert output.portfolio_metrics.total_return_pct == pytest.approx(5.0)
    assert output.per_instrument[0].total_return_pct == pytest.approx(5.0)
    assert output.concentration_metrics.top1_weight_pct == pytest.approx(50.0)
    assert output.stress_results  # default scenarios are calculated
    assert output.var_light is not None


def test_compute_portfolio_risk_basic_tool_limits_error():
    iss = StubIssClient()
    payload = {
        "positions": [
            {"ticker": "AAA", "weight": 0.5},
            {"ticker": "BBB", "weight": 0.5},
        ],
        "from_date": "2024-01-01",
        "to_date": "2024-01-10",
    }

    result = compute_portfolio_risk_basic_tool(payload, iss, max_tickers=1, max_lookback_days=5)

    assert result["error"]["error_type"] == "TOO_MANY_TICKERS"

    long_range = {**payload, "to_date": "2024-02-15"}
    result_range = compute_portfolio_risk_basic_tool(long_range, iss, max_tickers=5, max_lookback_days=10)
    assert result_range["error"]["error_type"] == "DATE_RANGE_TOO_LARGE"


def test_compute_portfolio_risk_basic_uses_custom_board(monkeypatch):
    captured = {}

    def fake_get_ohlcv(ticker: str, board: str, from_date, to_date, interval: str, max_lookback_days: int):
        captured["board"] = board
        captured["ticker"] = ticker
        return [
            OhlcvBar(ts=datetime(2024, 1, 1, tzinfo=timezone.utc), open=100.0, high=100.0, low=100.0, close=100.0),
            OhlcvBar(ts=datetime(2024, 1, 2, tzinfo=timezone.utc), open=101.0, high=101.0, low=101.0, close=101.0),
        ]

    iss = StubIssClient()
    monkeypatch.setattr(iss, "get_ohlcv_series", fake_get_ohlcv)

    payload = {
        "positions": [
            {"ticker": "AAA", "weight": 1.0, "board": "tqtf"},
        ],
        "from_date": "2024-01-01",
        "to_date": "2024-01-02",
    }

    result = compute_portfolio_risk_basic_tool(payload, iss, max_tickers=5, max_lookback_days=10)
    assert result["error"] is None
    assert captured["board"] == "TQTF"
    assert captured["ticker"] == "AAA"


def test_compute_portfolio_risk_basic_invalid_rebalance():
    iss = StubIssClient()
    payload = {
        "positions": [{"ticker": "AAA", "weight": 1.0}],
        "from_date": "2024-01-01",
        "to_date": "2024-01-02",
        "rebalance": "weekly",
    }

    result = compute_portfolio_risk_basic_tool(payload, iss, max_tickers=5, max_lookback_days=10)
    assert result["error"]["error_type"] == "VALIDATION_ERROR"
