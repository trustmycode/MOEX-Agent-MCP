import json
from pathlib import Path

from jsonschema import Draft7Validator

from risk_analytics_mcp.models import (
    ConcentrationMetrics,
    CorrelationMatrixInput,
    CorrelationMatrixOutput,
    IssuerPeersCompareInput,
    IssuerPeersComparePeer,
    IssuerPeersCompareReport,
    MetricRank,
    PeersFlag,
    PortfolioMetrics,
    PortfolioRiskBasicOutput,
    PortfolioRiskInput,
    PortfolioRiskPerInstrument,
    PortfolioPosition,
    StressScenarioResult,
    VarLightResult,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_DIR = REPO_ROOT / "docs" / "schemas"
TOOLS_JSON = REPO_ROOT / "risk_analytics_mcp" / "tools.json"


def _load_schema(filename: str) -> dict:
    return json.loads((SCHEMA_DIR / filename).read_text())


def test_risk_schemas_are_valid():
    for filename in [
        "compute_portfolio_risk_basic_input.json",
        "compute_portfolio_risk_basic_output.json",
        "compute_correlation_matrix_input.json",
        "compute_correlation_matrix_output.json",
        "issuer_peers_compare_input.json",
        "issuer_peers_compare_output.json",
        "suggest_rebalance_input.json",
        "suggest_rebalance_output.json",
        "cfo_liquidity_report_input.json",
        "cfo_liquidity_report_output.json",
    ]:
        schema = _load_schema(filename)
        Draft7Validator.check_schema(schema)


def test_tools_json_references_exist_and_named():
    tools_data = json.loads(TOOLS_JSON.read_text())
    names = {tool["name"] for tool in tools_data.get("tools", [])}
    assert names == {
        "compute_portfolio_risk_basic",
        "compute_correlation_matrix",
        "issuer_peers_compare",
        "suggest_rebalance",
        "build_cfo_liquidity_report",
    }

    base_dir = TOOLS_JSON.parent
    for tool in tools_data["tools"]:
        input_path = (base_dir / tool["input_schema"]["$ref"]).resolve()
        output_path = (base_dir / tool["output_schema"]["$ref"]).resolve()
        assert input_path.exists(), f"Missing input schema {input_path}"
        assert output_path.exists(), f"Missing output schema {output_path}"


def test_portfolio_risk_basic_schema_accepts_pydantic_payloads():
    schema_in = _load_schema("compute_portfolio_risk_basic_input.json")
    schema_out = _load_schema("compute_portfolio_risk_basic_output.json")

    input_model = PortfolioRiskInput(
        positions=[PortfolioPosition(ticker="SBER", weight=1.0)],
        from_date="2024-01-01",
        to_date="2024-01-02",
        rebalance="buy_and_hold",
    )
    Draft7Validator(schema_in).validate(input_model.model_dump(mode="json"))

    output_model = PortfolioRiskBasicOutput.success(
        metadata={"from_date": "2024-01-01", "to_date": "2024-01-02", "tickers": ["SBER"], "rebalance": "buy_and_hold"},
        per_instrument=[PortfolioRiskPerInstrument(ticker="SBER", weight=1.0, total_return_pct=1.0)],
        portfolio_metrics=PortfolioMetrics(total_return_pct=1.0, annualized_volatility_pct=2.0, max_drawdown_pct=0.5),
        concentration_metrics=ConcentrationMetrics(top1_weight_pct=100.0, top3_weight_pct=100.0, top5_weight_pct=100.0, hhi=1.0),
        stress_results=[
            StressScenarioResult(id="equity_-10_fx_+20", description="Test scenario", pnl_pct=-5.0, drivers={"equity_weight_pct": 100.0})
        ],
        var_light=VarLightResult(
            method="parametric_normal",
            confidence_level=0.95,
            horizon_days=1,
            annualized_volatility_pct=20.0,
            var_pct=1.0,
        ),
    )
    Draft7Validator(schema_out).validate(output_model.model_dump(mode="json"))


def test_correlation_matrix_schema_accepts_pydantic_payloads():
    schema_in = _load_schema("compute_correlation_matrix_input.json")
    schema_out = _load_schema("compute_correlation_matrix_output.json")

    input_model = CorrelationMatrixInput(tickers=["SBER", "GAZP"], from_date="2024-01-01", to_date="2024-01-05")
    Draft7Validator(schema_in).validate(input_model.model_dump(mode="json"))

    output_model = CorrelationMatrixOutput.success(
        metadata={"from_date": "2024-01-01", "to_date": "2024-01-05", "tickers": ["SBER", "GAZP"], "method": "pearson", "num_observations": 3},
        tickers=["SBER", "GAZP"],
        matrix=[[1.0, 0.2], [0.2, 1.0]],
    )
    Draft7Validator(schema_out).validate(output_model.model_dump(mode="json"))


def test_issuer_peers_compare_schema_accepts_pydantic_payloads():
    schema_in = _load_schema("issuer_peers_compare_input.json")
    schema_out = _load_schema("issuer_peers_compare_output.json")

    input_model = IssuerPeersCompareInput(ticker="SBER", index_ticker="IMOEX", max_peers=5)
    Draft7Validator(schema_in).validate(input_model.model_dump(mode="json"))

    base_peer = IssuerPeersComparePeer(
        ticker="SBER",
        price=300.0,
        market_cap=1_000_000_000_000.0,
        pe_ratio=5.0,
        ev_to_ebitda=4.0,
        debt_to_ebitda=1.0,
        roe_pct=20.0,
        dividend_yield_pct=7.0,
    )
    peer = IssuerPeersComparePeer(ticker="GAZP", price=200.0)
    report = IssuerPeersCompareReport.success(
        metadata={"base_ticker": "SBER", "peer_count": 1, "max_peers": 5},
        base_issuer=base_peer,
        peers=[peer],
        ranking=[MetricRank(metric="pe_ratio", value=5.0, rank=1, total=2, percentile=0.5)],
        flags=[PeersFlag(code="OVERVALUED", severity="medium", message="Test")],
    )
    Draft7Validator(schema_out).validate(report.model_dump(mode="json"))
