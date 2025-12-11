"""
Pydantic-модели для инструментов risk-analytics-mcp.

Модели согласованы с SPEC risk-analytics-mcp и предназначены
для обмена данными между MCP-слоем, расчётным модулем и вспомогательными
провайдерами (такими как FundamentalsDataProvider).
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal, Optional

from moex_iss_mcp.error_mapper import ToolErrorModel
from pydantic import BaseModel, Field, field_validator, model_validator


class PortfolioAggregates(BaseModel):
    """
    Агрегированные характеристики портфеля для стресс-сценариев.
    """

    base_currency: str = Field(default="RUB", min_length=1, max_length=8, description="Базовая валюта портфеля.")
    asset_class_weights: dict[str, float] = Field(
        default_factory=dict,
        description="Доли классов активов (equity, fixed_income, credit и т.п.), 0..1.",
    )
    fx_exposure_weights: dict[str, float] = Field(
        default_factory=dict,
        description="Валютная структура портфеля: доля в каждой валюте, 0..1.",
    )
    fixed_income_duration_years: Optional[float] = Field(
        default=None,
        ge=0,
        description="Эффективная дюрация долгового портфеля (годы) для ставки +bps.",
    )
    credit_spread_duration_years: Optional[float] = Field(
        default=None,
        ge=0,
        description="Дюрация по кредитным спрэдам (годы) для сценария credit spreads.",
    )

    @field_validator("base_currency")
    @classmethod
    def normalize_currency(cls, value: str) -> str:
        normalized = value.strip().upper()
        if not normalized:
            raise ValueError("base_currency cannot be empty")
        return normalized

    @field_validator("asset_class_weights", "fx_exposure_weights")
    @classmethod
    def validate_weight_map(cls, value: dict[str, float]) -> dict[str, float]:
        cleaned: dict[str, float] = {}
        for key, weight in value.items():
            if weight is None:
                continue
            if weight < 0:
                raise ValueError("Weights must be non-negative")
            cleaned[key.strip().lower()] = float(weight)
        return cleaned


class VarLightConfig(BaseModel):
    """
    Параметры расчёта лёгкого VaR (Var_light).
    """

    confidence_level: float = Field(default=0.95, ge=0.8, le=0.999, description="Уровень доверия, например 0.95.")
    horizon_days: int = Field(default=1, ge=1, le=60, description="Горизонт в днях для Var_light.")
    reference_volatility_pct: Optional[float] = Field(
        default=None,
        gt=0,
        description="Опциональная годовая волатильность, если портфельная не доступна.",
    )
    method: Literal["parametric_normal"] = Field(
        default="parametric_normal",
        description="Метод оценки (сейчас фиксирован parametric_normal).",
    )


class StressScenarioResult(BaseModel):
    """
    Результат стресс-сценария.
    """

    id: str = Field(description="Идентификатор стресс-сценария.")
    description: str = Field(description="Описание сценария.")
    pnl_pct: float = Field(description="Оценка P&L портфеля при сценарии, % от стоимости портфеля.")
    drivers: dict[str, float] = Field(default_factory=dict, description="Ключевые шоки/веса, использованные в оценке.")


class VarLightResult(BaseModel):
    """
    Результат расчёта Var_light.
    """

    method: str = Field(default="parametric_normal", description="Метод расчёта Var_light.")
    confidence_level: float = Field(description="Уровень доверия (0..1).")
    horizon_days: int = Field(description="Горизонт в днях.")
    annualized_volatility_pct: float = Field(description="Годовая волатильность, использованная в оценке, %.")  # noqa: E501
    var_pct: float = Field(description="Parametric VaR, % от стоимости портфеля.")


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
    aggregates: Optional[PortfolioAggregates] = Field(
        default=None,
        description="Агрегированные характеристики портфеля для стрессов (дюрация, валюты, классы активов).",
    )
    stress_scenarios: list[str] = Field(
        default_factory=list,
        description="Список id стресс-сценариев для расчёта (пусто — использовать дефолтные).",
    )
    var_config: VarLightConfig = Field(
        default_factory=VarLightConfig,
        description="Параметры для расчёта Var_light (уровень доверия, горизонт, референсная волатильность).",
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
    stress_results: list[StressScenarioResult] = Field(
        default_factory=list, description="Результаты по стресс-сценариям (id, описание, P&L)."
    )
    var_light: Optional[VarLightResult] = Field(
        default=None,
        description="Параметрический Var_light с параметрами расчёта.",
    )
    error: Optional[ToolErrorModel] = Field(default=None, description="Информация об ошибке, если расчёт не удался.")  # noqa: E501

    @classmethod
    def success(
        cls,
        *,
        metadata: dict,
        per_instrument: list[PortfolioRiskPerInstrument],
        portfolio_metrics: PortfolioMetrics,
        concentration_metrics: ConcentrationMetrics,
        stress_results: list[StressScenarioResult],
        var_light: Optional[VarLightResult],
    ) -> "PortfolioRiskBasicOutput":
        return cls(
            metadata=metadata,
            per_instrument=per_instrument,
            portfolio_metrics=portfolio_metrics,
            concentration_metrics=concentration_metrics,
            stress_results=stress_results,
            var_light=var_light,
            error=None,
        )

    @classmethod
    def from_error(cls, error: ToolErrorModel, metadata: Optional[dict] = None) -> "PortfolioRiskBasicOutput":
        return cls(
            metadata=metadata or {},
            per_instrument=[],
            portfolio_metrics=PortfolioMetrics(),
            concentration_metrics=ConcentrationMetrics(),
            stress_results=[],
            var_light=None,
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


class IssuerFundamentals(BaseModel):
    """
    Нормализованный набор фундаментальных и рыночных метрик по эмитенту.

    Модель используется провайдером FundamentalsDataProvider и инструментами,
    работающими со сценариями issuer_peers_compare / portfolio_risk / cfo_liquidity_report.
    """

    ticker: str = Field(min_length=1, max_length=32, description="Ticker, e.g. SBER.")
    isin: Optional[str] = Field(default=None, description="ISIN код бумаги, если доступен.")
    issuer_name: Optional[str] = Field(default=None, description="Название эмитента по данным MOEX.")
    sector: Optional[str] = Field(default=None, description="Сектор/отрасль эмитента, если доступен.")
    industry: Optional[str] = Field(default=None, description="Подотрасль/индустрия, если доступна.")
    reporting_currency: Optional[str] = Field(
        default="RUB",
        description="Валюта отчётности/метрик (для MVP обычно RUB).",
    )
    as_of: Optional[datetime] = Field(
        default=None,
        description="Момент времени, на который актуальны рыночные метрики.",
    )
    total_equity: Optional[float] = Field(
        default=None,
        description="Собственный капитал акционеров для расчёта ROE.",
    )

    # Базовые отчётные показатели (последний период)
    revenue: Optional[float] = Field(default=None, description="Выручка за последний отчётный период.")
    ebitda: Optional[float] = Field(default=None, description="EBITDA за последний отчётный период.")
    ebit: Optional[float] = Field(default=None, description="EBIT за последний отчётный период.")
    net_income: Optional[float] = Field(default=None, description="Чистая прибыль за последний отчётный период.")
    total_debt: Optional[float] = Field(default=None, description="Совокупный долг.")
    net_debt: Optional[float] = Field(default=None, description="Чистый долг.")

    # Рыночные показатели
    price: Optional[float] = Field(default=None, description="Текущая рыночная цена одной акции.")
    shares_outstanding: Optional[float] = Field(
        default=None,
        description="Количество акций в обращении (issuesize).",
    )
    free_float_shares: Optional[float] = Field(
        default=None,
        description="Количество акций в свободном обращении.",
    )
    free_float_pct: Optional[float] = Field(
        default=None,
        description="Доля free float в капитале, %.",
    )
    market_cap: Optional[float] = Field(default=None, description="Рыночная капитализация (price * shares).")
    enterprise_value: Optional[float] = Field(default=None, description="Enterprise Value.")

    # Мультипликаторы и производные метрики
    pe_ratio: Optional[float] = Field(default=None, description="P/E мультипликатор.")
    ev_to_ebitda: Optional[float] = Field(default=None, description="EV/EBITDA мультипликатор.")
    debt_to_ebitda: Optional[float] = Field(default=None, description="Долг/EBITDA.")
    dividend_yield_pct: Optional[float] = Field(default=None, description="Дивидендная доходность, %.")

    source: str = Field(
        default="moex-iss",
        description="Источник данных (по умолчанию moex-iss через moex_iss_sdk).",
    )

    @field_validator("ticker")
    @classmethod
    def normalize_ticker(cls, value: str) -> str:
        normalized = (value or "").strip().upper()
        if not normalized:
            raise ValueError("ticker cannot be empty")
        return normalized

    @field_validator("reporting_currency")
    @classmethod
    def normalize_currency(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        normalized = value.strip().upper()
        return normalized or None


class IssuerPeersComparePeer(BaseModel):
    """
    Сводные метрики по эмитенту для сравнительного анализа с пирами.
    """

    ticker: str = Field(min_length=1, max_length=32, description="Ticker, e.g. SBER.")
    isin: Optional[str] = Field(default=None, description="ISIN код бумаги, если доступен.")
    issuer_name: Optional[str] = Field(default=None, description="Название эмитента.")
    sector: Optional[str] = Field(default=None, description="Сектор/отрасль, если доступен.")
    as_of: Optional[datetime] = Field(default=None, description="Время среза рыночных метрик.")
    price: Optional[float] = Field(default=None, description="Текущая рыночная цена.")
    shares_outstanding: Optional[float] = Field(default=None, description="Количество акций в обращении.")
    market_cap: Optional[float] = Field(default=None, description="Рыночная капитализация.")
    enterprise_value: Optional[float] = Field(default=None, description="Enterprise Value.")
    net_debt: Optional[float] = Field(default=None, description="Чистый долг.")
    ebitda: Optional[float] = Field(default=None, description="EBITDA за последний период.")
    net_income: Optional[float] = Field(default=None, description="Чистая прибыль за период.")
    pe_ratio: Optional[float] = Field(default=None, description="P/E мультипликатор.")
    ev_to_ebitda: Optional[float] = Field(default=None, description="EV/EBITDA.")
    debt_to_ebitda: Optional[float] = Field(default=None, description="NetDebt/EBITDA.")
    roe_pct: Optional[float] = Field(default=None, description="ROE, %.")
    dividend_yield_pct: Optional[float] = Field(default=None, description="Дивидендная доходность, %.")  # noqa: E501

    @field_validator("ticker")
    @classmethod
    def normalize_ticker(cls, value: str) -> str:
        normalized = (value or "").strip().upper()
        if not normalized:
            raise ValueError("ticker cannot be empty")
        return normalized

    @field_validator("sector")
    @classmethod
    def normalize_sector(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        normalized = value.strip().upper()
        return normalized or None


class MetricRank(BaseModel):
    """
    Ранжирование базового эмитента по выбранной метрике среди пиров.
    """

    metric: str = Field(description="Имя метрики (pe_ratio, ev_to_ebitda, roe_pct, debt_to_ebitda, dividend_yield_pct).")  # noqa: E501
    value: Optional[float] = Field(default=None, description="Значение метрики у базового эмитента.")
    rank: Optional[int] = Field(default=None, ge=1, description="Позиция эмитента среди пиров (1 — лучшая).")
    total: int = Field(ge=0, description="Количество эмитентов, участвующих в ранжировании.")
    percentile: Optional[float] = Field(default=None, ge=0, le=1, description="Перцентиль базового эмитента по метрике.")  # noqa: E501


class PeersFlag(BaseModel):
    """
    Эвристические флаги по итогам сравнения с пирами.
    """

    code: str = Field(description="Код флага (OVERVALUED, UNDERVALUED, HIGH_LEVERAGE и т.п.).")
    severity: Literal["low", "medium", "high"] = Field(description="Уровень значимости флага.")
    message: str = Field(description="Человекочитаемое описание вывода.")
    metric: Optional[str] = Field(default=None, description="Метрика, на основе которой поставлен флаг.")


class IssuerPeersCompareInput(BaseModel):
    """
    Входные параметры инструмента issuer_peers_compare.
    """

    ticker: Optional[str] = Field(default=None, description="Ticker (предпочтительный идентификатор).")
    isin: Optional[str] = Field(default=None, description="ISIN, если тикер не указан.")
    issuer_id: Optional[str] = Field(default=None, description="MOEX issuer id, если доступен.")
    index_ticker: Optional[str] = Field(default="IMOEX", description="Индекс, в составе которого подбираются пиры.")
    sector: Optional[str] = Field(default=None, description="Фильтр по сектору/отрасли (опционально).")
    peer_tickers: Optional[list[str]] = Field(default=None, description="Явный список тикеров-пиров (если задан, перекрывает index_ticker).")  # noqa: E501
    max_peers: int = Field(default=10, ge=1, le=100, description="Максимальное количество пиров в отчёте.")
    as_of_date: Optional[date] = Field(default=None, description="Дата для среза данных (по умолчанию — сегодня).")

    @model_validator(mode="after")
    def ensure_identifier(self) -> "IssuerPeersCompareInput":
        if not (self.ticker or self.isin or self.issuer_id):
            raise ValueError("One of ticker/isin/issuer_id must be provided")
        return self

    @field_validator("ticker")
    @classmethod
    def normalize_ticker(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        normalized = value.strip().upper()
        return normalized or None

    @field_validator("index_ticker")
    @classmethod
    def normalize_index(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        normalized = value.strip().upper()
        return normalized or None

    @field_validator("sector")
    @classmethod
    def normalize_sector(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        normalized = value.strip().upper()
        return normalized or None

    @field_validator("peer_tickers")
    @classmethod
    def normalize_peers(cls, tickers: Optional[list[str]]) -> Optional[list[str]]:
        if tickers is None:
            return None
        normalized: list[str] = []
        seen: set[str] = set()
        for ticker in tickers:
            value = (ticker or "").strip().upper()
            if not value:
                continue
            if value in seen:
                continue
            normalized.append(value)
            seen.add(value)
        return normalized or None


class IssuerPeersCompareReport(BaseModel):
    """
    Выход инструмента issuer_peers_compare: базовый эмитент, список пиров, ранжирование и флаги.
    """

    metadata: dict = Field(default_factory=dict, description="Метаданные запроса и применённые фильтры.")
    base_issuer: Optional[IssuerPeersComparePeer] = Field(default=None, description="Агрегированные метрики базового эмитента.")  # noqa: E501
    peers: list[IssuerPeersComparePeer] = Field(default_factory=list, description="Пиры с тем же набором метрик.")
    ranking: list[MetricRank] = Field(default_factory=list, description="Ранжирование базового эмитента по ключевым метрикам.")  # noqa: E501
    flags: list[PeersFlag] = Field(default_factory=list, description="Эвристические флаги по итогам сравнения.")
    error: Optional[ToolErrorModel] = Field(default=None, description="Информация об ошибке, если сравнение не удалось.")

    @classmethod
    def success(
        cls,
        *,
        metadata: dict,
        base_issuer: IssuerPeersComparePeer,
        peers: list[IssuerPeersComparePeer],
        ranking: list[MetricRank],
        flags: list[PeersFlag],
    ) -> "IssuerPeersCompareReport":
        return cls(
            metadata=metadata,
            base_issuer=base_issuer,
            peers=peers,
            ranking=ranking,
            flags=flags,
            error=None,
        )

    @classmethod
    def from_error(cls, error: ToolErrorModel, metadata: Optional[dict] = None) -> "IssuerPeersCompareReport":
        return cls(
            metadata=metadata or {},
            base_issuer=None,
            peers=[],
            ranking=[],
            flags=[],
            error=error,
        )


__all__ = [
    "PortfolioAggregates",
    "PortfolioPosition",
    "PortfolioRiskInput",
    "PortfolioRiskPerInstrument",
    "PortfolioMetrics",
    "ConcentrationMetrics",
    "PortfolioRiskBasicOutput",
    "CorrelationMatrixInput",
    "CorrelationMatrixOutput",
    "StressScenarioResult",
    "VarLightConfig",
    "VarLightResult",
    "IssuerFundamentals",
    "IssuerPeersComparePeer",
    "MetricRank",
    "PeersFlag",
    "IssuerPeersCompareInput",
    "IssuerPeersCompareReport",
]
