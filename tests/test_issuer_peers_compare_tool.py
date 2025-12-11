from __future__ import annotations

import asyncio
import inspect
from datetime import datetime, timezone

import pytest

from moex_iss_sdk import IssClientSettings
from moex_iss_sdk.models import IndexConstituent
from risk_analytics_mcp.config import RiskMcpConfig
from risk_analytics_mcp.models import IssuerFundamentals
from risk_analytics_mcp.providers import FundamentalsDataProvider
from risk_analytics_mcp.server import RiskMcpServer
from risk_analytics_mcp.tools.issuer_peers_compare import init_tool_dependencies


class StubFundamentalsProvider(FundamentalsDataProvider):
    def __init__(self, mapping: dict[str, IssuerFundamentals]):
        self.mapping = mapping

    def get_issuer_fundamentals(self, ticker: str) -> IssuerFundamentals:  # type: ignore[override]
        if ticker not in self.mapping:
            raise ValueError(f"Unknown ticker {ticker}")
        return self.mapping[ticker]

    def get_issuer_fundamentals_many(self, tickers):  # type: ignore[override]
        return {ticker: self.mapping[ticker] for ticker in tickers if ticker in self.mapping}


class StubIssClient:
    def __init__(self, constituents):
        self.constituents = constituents
        self.settings = IssClientSettings.from_env()

    def get_index_constituents(self, index_ticker: str, as_of_date):
        return self.constituents


def _fundamentals() -> dict[str, IssuerFundamentals]:
    as_of = datetime(2025, 1, 1, tzinfo=timezone.utc)
    return {
        "SBER": IssuerFundamentals(
            ticker="SBER",
            price=300.0,
            shares_outstanding=22_000_000_000,
            net_income=1_300_000_000_000,
            ebitda=1_800_000_000_000,
            net_debt=500_000_000_000,
            dividend_yield_pct=7.0,
            total_equity=2_000_000_000_000,
            as_of=as_of,
        ),
        "GAZP": IssuerFundamentals(
            ticker="GAZP",
            price=150.0,
            shares_outstanding=24_000_000_000,
            net_income=1_000_000_000_000,
            ebitda=1_500_000_000_000,
            net_debt=1_200_000_000_000,
            dividend_yield_pct=12.0,
            total_equity=3_000_000_000_000,
            as_of=as_of,
        ),
        "VTBR": IssuerFundamentals(
            ticker="VTBR",
            price=2.5,
            shares_outstanding=14_000_000_000_000,
            net_income=600_000_000_000,
            ebitda=900_000_000_000,
            net_debt=800_000_000_000,
            dividend_yield_pct=3.0,
            total_equity=1_500_000_000_000,
            as_of=as_of,
        ),
    }


def run_tool(tool, **kwargs):
    signature = inspect.signature(tool.fn)
    for param in ("ctx",):
        if param in signature.parameters and param not in kwargs:
            kwargs[param] = None
    result = asyncio.run(tool.fn(**kwargs))
    structured = result.structured_content
    return structured.get("structured_content", structured)


def test_issuer_peers_compare_builds_report():
    cfg = RiskMcpConfig(max_peers=3)
    server = RiskMcpServer(cfg)
    fundamentals_map = _fundamentals()

    constituents = [
        IndexConstituent(index_ticker="IMOEX", ticker="SBER", weight_pct=40.0, last_price=300.0, price_change_pct=0.0, sector="FIN", board="TQBR", figi=None, isin=None, raw={}),
        IndexConstituent(index_ticker="IMOEX", ticker="GAZP", weight_pct=30.0, last_price=150.0, price_change_pct=0.0, sector="OIL", board="TQBR", figi=None, isin=None, raw={}),
        IndexConstituent(index_ticker="IMOEX", ticker="VTBR", weight_pct=20.0, last_price=2.5, price_change_pct=0.0, sector="FIN", board="TQBR", figi=None, isin=None, raw={}),
    ]
    stub_client = StubIssClient(constituents)
    stub_provider = StubFundamentalsProvider(fundamentals_map)
    init_tool_dependencies(stub_client, stub_provider, server.metrics, server.tracing, max_peers=3, default_index_ticker="IMOEX")

    tool = server.fastmcp._tool_manager._tools["issuer_peers_compare"]
    payload = run_tool(tool, ticker="SBER", index_ticker="IMOEX", max_peers=2)

    assert payload["error"] is None
    data = payload["data"]
    assert data["base_issuer"]["ticker"] == "SBER"
    assert len(data["peers"]) == 2
    assert all(flag["code"] for flag in data["flags"])
    assert all(item["metric"] for item in data["ranking"])


def test_issuer_peers_compare_returns_error_when_no_peers():
    cfg = RiskMcpConfig(max_peers=2)
    server = RiskMcpServer(cfg)
    stub_client = StubIssClient([])
    fundamentals_map = _fundamentals()
    stub_provider = StubFundamentalsProvider(fundamentals_map)
    init_tool_dependencies(stub_client, stub_provider, server.metrics, server.tracing, max_peers=2, default_index_ticker="IMOEX")

    tool = server.fastmcp._tool_manager._tools["issuer_peers_compare"]
    payload = run_tool(tool, ticker="SBER")

    assert payload["error"]["error_type"] == "NO_PEERS_FOUND"
