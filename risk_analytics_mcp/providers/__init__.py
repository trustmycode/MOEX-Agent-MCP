from __future__ import annotations

"""
Провайдеры данных для risk-analytics-mcp.

Содержит абстракцию FundamentalsDataProvider и её реализацию
на базе MOEX ISS (`MoexIssFundamentalsProvider`).
"""

from .fundamentals import FundamentalsDataProvider, MoexIssFundamentalsProvider

__all__ = ["FundamentalsDataProvider", "MoexIssFundamentalsProvider"]

