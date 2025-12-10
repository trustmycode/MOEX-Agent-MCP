"""
Pydantic-модели для инструментов risk-analytics-mcp.

Модели согласованы с черновым SPEC risk-analytics-mcp и предназначены
для обмена данными между MCP-слоем и расчётным модулем.
"""

from __future__ import annotations

from datetime import date
from typing import Literal, Optional

from moex_iss_mcp.error_mapper import ToolErrorModel
from pydantic import BaseModel, Field, field_validator, model_validator


class PortfolioPosition(BaseModel):
    """
    Отдельная позиция портфеля с весом.
    """

    ticker: str = Field(min_length=1, max_length=32, description="Ticker, e.g. SBER.")
    weight: float = Field(gt=0, description="Доля бумаги в портфеле (0..1).")
    board: Optional[str] = Field(default=None, min_length=1, max_length=16, description="MOEX board (optional).")

    @field_validator("ticker")
    @classmethod
    def normalize_ticker(cls, value: str) -> str:
        normalized = value.strip().upper()
        if not normalized:
            raise ValueError("Ticker cannot be empty")
        return normalized

    @field_validator("board")
    @classmethod
    def normalize_board(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        normalized = value.strip().upper()
        if not normalized:
            raise ValueError("Board cannot be empty if provided")
        return normalized


class PortfolioRiskInput(BaseModel):
    """
    Входные данные для compute_portfolio_risk_basic.
    """

    positions: list[PortfolioPosition] = Field(min_length=1, description="Список позиций портфеля.")
    from_date: date = Field(description="Начальная дата периода (включительно).")
    to_date: date = Field(description="Конечная дата периода (включительно).")
    rebalance: Literal["buy_and_hold", "monthly"] = Field(
        default="buy_and_hold",
        description="Стратегия ребалансировки: buy_and_hold или ежемесячная фиксация весов.",
    )

    @field_validator("to_date")
    @classmethod
    def validate_dates(cls, to_date_value: date, info) -> date:
        from_date_value = info.data.get("from_date")
        if from_date_value and to_date_value < from_date_value:
            raise ValueError("to_date must not be earlier than from_date")
        return to_date_value

    @model_validator(mode="after")
    def validate_weights(self) -> "PortfolioRiskInput":
        total_weight = sum(pos.weight for pos in self.positions)
        if total_weight <= 0:
            raise ValueError("Positions weights must be positive and non-zero")
        if not (0.99 <= total_weight <= 1.01):
            raise ValueError("Positions weights must sum to 1.0 within 1% tolerance")

        tickers = [pos.ticker for pos in self.positions]
        if len(tickers) != len(set(tickers)):
            raise ValueError("Positions tickers must be unique")
        return self


class PortfolioRiskPerInstrument(BaseModel):
    """
    Метрики риска по каждому инструменту.
    """

    ticker: str = Field(description="Ticker, e.g. SBER.")
    weight: float = Field(description="Вес бумаги в портфеле (0..1).")
    total_return_pct: Optional[float] = Field(default=None, description="Совокупная доходность, %.")  # noqa: E501
    annualized_volatility_pct: Optional[float] = Field(
        default=None, description="Годовая волатильность на основе дневных доходностей, %."
    )
    max_drawdown_pct: Optional[float] = Field(default=None, description="Максимальная просадка за период, %.")  # noqa: E501


class PortfolioMetrics(BaseModel):
    """
    Агрегированные метрики портфеля.
    """

    total_return_pct: Optional[float] = Field(default=None, description="Совокупная доходность портфеля, %.")  # noqa: E501
    annualized_volatility_pct: Optional[float] = Field(
        default=None, description="Годовая волатильность портфеля, %."
    )
    max_drawdown_pct: Optional[float] = Field(default=None, description="Максимальная просадка портфеля, %.")  # noqa: E501


class ConcentrationMetrics(BaseModel):
    """
    Базовые показатели концентрации портфеля.
    """

    top1_weight_pct: Optional[float] = Field(default=None, description="Суммарный вес топ-1 бумаги, %.")  # noqa: E501
    top3_weight_pct: Optional[float] = Field(default=None, description="Суммарный вес топ-3 бумаг, %.")  # noqa: E501
    top5_weight_pct: Optional[float] = Field(default=None, description="Суммарный вес топ-5 бумаг, %.")  # noqa: E501
    hhi: Optional[float] = Field(default=None, description="Индекс Херфиндаля–Хиршмана (0..1).")


class PortfolioRiskBasicOutput(BaseModel):
    """
    Ответ инструмента compute_portfolio_risk_basic.
    """

    metadata: dict = Field(default_factory=dict, description="Метаданные запроса: даты, политика ребаланса, валюты.")
    per_instrument: list[PortfolioRiskPerInstrument] = Field(description="Метрики по каждой бумаге.")  # noqa: E501
    portfolio_metrics: PortfolioMetrics = Field(description="Агрегированные метрики портфеля.")
    concentration_metrics: ConcentrationMetrics = Field(description="Концентрационные метрики.")
    error: Optional[ToolErrorModel] = Field(default=None, description="Информация об ошибке, если расчёт не удался.")  # noqa: E501

    @classmethod
    def success(
        cls,
        *,
        metadata: dict,
        per_instrument: list[PortfolioRiskPerInstrument],
        portfolio_metrics: PortfolioMetrics,
        concentration_metrics: ConcentrationMetrics,
    ) -> "PortfolioRiskBasicOutput":
        return cls(
            metadata=metadata,
            per_instrument=per_instrument,
            portfolio_metrics=portfolio_metrics,
            concentration_metrics=concentration_metrics,
            error=None,
        )

    @classmethod
    def from_error(cls, error: ToolErrorModel, metadata: Optional[dict] = None) -> "PortfolioRiskBasicOutput":
        return cls(
            metadata=metadata or {},
            per_instrument=[],
            portfolio_metrics=PortfolioMetrics(),
            concentration_metrics=ConcentrationMetrics(),
            error=error,
        )


class CorrelationMatrixInput(BaseModel):
    """
    Входные данные для compute_correlation_matrix.
    """

    tickers: list[str] = Field(min_length=2, description="Список тикеров для построения матрицы.")
    from_date: date = Field(description="Начало периода (включительно).")
    to_date: date = Field(description="Конец периода (включительно).")

    @field_validator("tickers")
    @classmethod
    def normalize_tickers(cls, tickers: list[str]) -> list[str]:
        normalized: list[str] = []
        seen: set[str] = set()
        for ticker in tickers:
            value = (ticker or "").strip().upper()
            if not value:
                raise ValueError("Ticker cannot be empty")
            if value in seen:
                raise ValueError("Tickers must be unique")
            normalized.append(value)
            seen.add(value)
        return normalized

    @field_validator("to_date")
    @classmethod
    def validate_dates(cls, to_date_value: date, info) -> date:
        from_date_value = info.data.get("from_date")
        if from_date_value and to_date_value < from_date_value:
            raise ValueError("to_date must not be earlier than from_date")
        return to_date_value


class CorrelationMatrixOutput(BaseModel):
    """
    Ответ инструмента compute_correlation_matrix.
    """

    metadata: dict = Field(default_factory=dict, description="Метаданные запроса: даты, метод, число наблюдений.")
    tickers: list[str] = Field(default_factory=list, description="Список тикеров в порядке расчёта.")
    matrix: list[list[float]] = Field(default_factory=list, description="Матрица корреляций.")
    error: Optional[ToolErrorModel] = Field(default=None, description="Информация об ошибке, если расчёт не удался.")

    @classmethod
    def success(cls, *, metadata: dict, tickers: list[str], matrix: list[list[float]]) -> "CorrelationMatrixOutput":
        return cls(metadata=metadata, tickers=tickers, matrix=matrix, error=None)

    @classmethod
    def from_error(cls, error: ToolErrorModel, metadata: Optional[dict] = None) -> "CorrelationMatrixOutput":
        return cls(metadata=metadata or {}, tickers=[], matrix=[], error=error)


__all__ = [
    "PortfolioPosition",
    "PortfolioRiskInput",
    "PortfolioRiskPerInstrument",
    "PortfolioMetrics",
    "ConcentrationMetrics",
    "PortfolioRiskBasicOutput",
    "CorrelationMatrixInput",
    "CorrelationMatrixOutput",
]
