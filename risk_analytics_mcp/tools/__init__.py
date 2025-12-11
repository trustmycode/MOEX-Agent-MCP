"""
Инструменты MCP для risk-analytics-mcp.
"""

from .correlation_matrix import compute_correlation_matrix, compute_correlation_matrix_core
from .portfolio_risk import compute_portfolio_risk_basic, compute_portfolio_risk_basic_core
from .issuer_peers_compare import issuer_peers_compare, issuer_peers_compare_core

__all__ = [
    "compute_portfolio_risk_basic_core",
    "compute_portfolio_risk_basic",
    "compute_correlation_matrix_core",
    "compute_correlation_matrix",
    "issuer_peers_compare_core",
    "issuer_peers_compare",
]
