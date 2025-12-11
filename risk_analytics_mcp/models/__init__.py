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


# =============================================================================
# Модели для suggest_rebalance
# =============================================================================


class RiskProfileTarget(BaseModel):
    """
    Целевой профиль риска для ребалансировки.

    Содержит ограничения по классам активов, концентрации и обороту.
    """

    max_equity_weight: float = Field(
        default=1.0, ge=0, le=1, description="Максимальная доля акций в портфеле (0..1)."
    )
    max_fixed_income_weight: float = Field(
        default=1.0, ge=0, le=1, description="Максимальная доля облигаций в портфеле (0..1)."
    )
    max_fx_weight: float = Field(
        default=1.0, ge=0, le=1, description="Максимальная доля валютных активов в портфеле (0..1)."
    )
    max_single_position_weight: float = Field(
        default=0.25, gt=0, le=1, description="Максимальная доля одной позиции (лимит концентрации)."
    )
    max_issuer_weight: float = Field(
        default=0.30, gt=0, le=1, description="Максимальная доля одного эмитента в портфеле."
    )
    max_turnover: float = Field(
        default=0.50, ge=0, le=1, description="Максимально допустимый оборот при ребалансировке (0..1)."
    )
    target_asset_class_weights: dict[str, float] = Field(
        default_factory=dict,
        description="Целевые веса по классам активов (equity, fixed_income, fx и т.п.), сумма может быть <1.",
    )

    @field_validator("target_asset_class_weights")
    @classmethod
    def validate_target_weights(cls, value: dict[str, float]) -> dict[str, float]:
        cleaned: dict[str, float] = {}
        total = 0.0
        for key, weight in value.items():
            if weight is None:
                continue
            if weight < 0:
                raise ValueError("Target asset class weights must be non-negative")
            if weight > 1:
                raise ValueError("Target asset class weight cannot exceed 1.0")
            cleaned[key.strip().lower()] = float(weight)
            total += weight
        if total > 1.01:
            raise ValueError("Sum of target asset class weights cannot exceed 1.0")
        return cleaned


class RebalancePosition(BaseModel):
    """
    Позиция портфеля для ребалансировки с опциональными метаданными.
    """

    ticker: str = Field(min_length=1, max_length=32, description="Ticker, e.g. SBER.")
    current_weight: float = Field(ge=0, le=1, description="Текущий вес позиции в портфеле (0..1).")
    current_value: Optional[float] = Field(
        default=None, ge=0, description="Текущая стоимость позиции (опционально)."
    )
    asset_class: str = Field(
        default="equity", min_length=1, description="Класс актива (equity, fixed_income, fx, cash и т.п.)."
    )
    issuer: Optional[str] = Field(
        default=None, description="Код эмитента (для группировки по эмитентам)."
    )
    board: Optional[str] = Field(default=None, min_length=1, max_length=16, description="MOEX board (optional).")

    @field_validator("ticker")
    @classmethod
    def normalize_ticker(cls, value: str) -> str:
        normalized = value.strip().upper()
        if not normalized:
            raise ValueError("Ticker cannot be empty")
        return normalized

    @field_validator("asset_class")
    @classmethod
    def normalize_asset_class(cls, value: str) -> str:
        normalized = value.strip().lower()
        if not normalized:
            raise ValueError("Asset class cannot be empty")
        return normalized

    @field_validator("issuer")
    @classmethod
    def normalize_issuer(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        normalized = value.strip().upper()
        return normalized or None


class RebalanceInput(BaseModel):
    """
    Входные данные для suggest_rebalance: текущий портфель и целевые ограничения.
    """

    positions: list[RebalancePosition] = Field(
        min_length=1, description="Текущие позиции портфеля с весами."
    )
    total_portfolio_value: Optional[float] = Field(
        default=None, gt=0, description="Общая стоимость портфеля (для расчёта сделок в единицах)."
    )
    risk_profile: RiskProfileTarget = Field(
        default_factory=RiskProfileTarget, description="Целевой профиль риска и ограничения."
    )

    @model_validator(mode="after")
    def validate_positions(self) -> "RebalanceInput":
        total_weight = sum(pos.current_weight for pos in self.positions)
        if total_weight <= 0:
            raise ValueError("Positions current_weight must be positive and non-zero")
        if not (0.99 <= total_weight <= 1.01):
            raise ValueError("Positions current_weight must sum to 1.0 within 1% tolerance")

        tickers = [pos.ticker for pos in self.positions]
        if len(tickers) != len(set(tickers)):
            raise ValueError("Positions tickers must be unique")
        return self


class RebalanceTrade(BaseModel):
    """
    Предлагаемая сделка при ребалансировке.
    """

    ticker: str = Field(min_length=1, max_length=32, description="Ticker бумаги для сделки.")
    side: Literal["buy", "sell"] = Field(description="Направление сделки: buy или sell.")
    weight_delta: float = Field(description="Изменение веса (положительное для buy, отрицательное для sell).")
    target_weight: float = Field(ge=0, le=1, description="Целевой вес после ребалансировки.")
    estimated_value: Optional[float] = Field(
        default=None, description="Оценка стоимости сделки (если задана total_portfolio_value)."
    )
    reason: str = Field(default="", description="Причина сделки (concentration, asset_class и т.п.).")


class RebalanceSummary(BaseModel):
    """
    Сводка по результату ребалансировки.
    """

    total_turnover: float = Field(ge=0, le=1, description="Суммарный оборот (сумма |delta| / 2).")
    turnover_within_limit: bool = Field(description="Оборот не превышает max_turnover.")
    positions_changed: int = Field(ge=0, description="Количество позиций с изменениями.")
    concentration_issues_resolved: int = Field(ge=0, description="Количество устранённых нарушений концентрации.")
    asset_class_issues_resolved: int = Field(ge=0, description="Количество устранённых нарушений по классам активов.")
    warnings: list[str] = Field(default_factory=list, description="Предупреждения при ребалансировке.")


class RebalanceOutput(BaseModel):
    """
    Ответ инструмента suggest_rebalance: целевые веса и сделки.
    """

    metadata: dict = Field(default_factory=dict, description="Метаданные запроса и расчёта.")
    target_weights: dict[str, float] = Field(
        default_factory=dict, description="Целевые веса по тикерам после ребалансировки."
    )
    trades: list[RebalanceTrade] = Field(default_factory=list, description="Список предлагаемых сделок.")
    summary: Optional[RebalanceSummary] = Field(default=None, description="Сводка по результату ребалансировки.")
    error: Optional[ToolErrorModel] = Field(default=None, description="Информация об ошибке, если ребалансировка невозможна.")

    @classmethod
    def success(
        cls,
        *,
        metadata: dict,
        target_weights: dict[str, float],
        trades: list[RebalanceTrade],
        summary: RebalanceSummary,
    ) -> "RebalanceOutput":
        return cls(
            metadata=metadata,
            target_weights=target_weights,
            trades=trades,
            summary=summary,
            error=None,
        )

    @classmethod
    def from_error(cls, error: ToolErrorModel, metadata: Optional[dict] = None) -> "RebalanceOutput":
        return cls(
            metadata=metadata or {},
            target_weights={},
            trades=[],
            summary=None,
            error=error,
        )


# =============================================================================
# Модели для CFO Liquidity Report (Scenario 9)
# =============================================================================


class CfoLiquidityPosition(BaseModel):
    """
    Позиция портфеля для CFO-отчёта с характеристиками ликвидности.
    """

    ticker: str = Field(min_length=1, max_length=32, description="Ticker, e.g. SBER.")
    weight: float = Field(gt=0, le=1, description="Вес инструмента в портфеле (0..1).")
    asset_class: Literal["equity", "fixed_income", "cash", "fx", "credit"] = Field(
        default="equity", description="Класс актива."
    )
    liquidity_bucket: Literal["0-7d", "8-30d", "31-90d", "90d+"] = Field(
        default="0-7d", description="Корзина ликвидности — срок реализации актива."
    )
    board: Optional[str] = Field(default=None, min_length=1, max_length=16, description="MOEX board (optional).")
    currency: str = Field(default="RUB", min_length=3, max_length=3, description="Валюта позиции (ISO 4217).")

    @field_validator("ticker")
    @classmethod
    def normalize_ticker(cls, value: str) -> str:
        normalized = value.strip().upper()
        if not normalized:
            raise ValueError("Ticker cannot be empty")
        return normalized

    @field_validator("currency")
    @classmethod
    def normalize_currency(cls, value: str) -> str:
        normalized = value.strip().upper()
        if not normalized or len(normalized) != 3:
            raise ValueError("Currency must be 3-letter ISO code")
        return normalized


class CovenantLimits(BaseModel):
    """
    Лимиты ковенант для проверки.
    """

    max_net_debt_ebitda: Optional[float] = Field(
        default=None, gt=0, description="Максимальный NetDebt/EBITDA."
    )
    min_liquidity_ratio: Optional[float] = Field(
        default=None, gt=0, description="Минимальный коэффициент ликвидности."
    )
    min_current_ratio: Optional[float] = Field(
        default=None, gt=0, description="Минимальный коэффициент текущей ликвидности."
    )


class CfoLiquidityReportInput(BaseModel):
    """
    Входные данные для build_cfo_liquidity_report.
    """

    positions: list[CfoLiquidityPosition] = Field(
        min_length=1, description="Позиции портфеля с характеристиками ликвидности."
    )
    total_portfolio_value: Optional[float] = Field(
        default=None, gt=0, description="Общая стоимость портфеля (опционально)."
    )
    base_currency: str = Field(default="RUB", min_length=3, max_length=3, description="Базовая валюта отчёта.")
    from_date: date = Field(description="Начальная дата периода анализа.")
    to_date: date = Field(description="Конечная дата периода анализа.")
    horizon_months: int = Field(
        default=12, ge=1, le=36, description="Горизонт прогнозирования ликвидности (месяцы)."
    )
    stress_scenarios: list[str] = Field(
        default_factory=lambda: ["base_case", "equity_-10_fx_+20", "rates_+300bp"],
        description="Список идентификаторов стресс-сценариев.",
    )
    aggregates: Optional[PortfolioAggregates] = Field(
        default=None, description="Агрегированные характеристики портфеля для стресс-сценариев."
    )
    covenant_limits: Optional[CovenantLimits] = Field(
        default=None, description="Лимиты ковенант для проверки."
    )

    @field_validator("base_currency")
    @classmethod
    def normalize_base_currency(cls, value: str) -> str:
        normalized = value.strip().upper()
        if not normalized or len(normalized) != 3:
            raise ValueError("base_currency must be 3-letter ISO code")
        return normalized

    @field_validator("to_date")
    @classmethod
    def validate_dates(cls, to_date_value: date, info) -> date:
        from_date_value = info.data.get("from_date")
        if from_date_value and to_date_value < from_date_value:
            raise ValueError("to_date must not be earlier than from_date")
        return to_date_value

    @model_validator(mode="after")
    def validate_weights(self) -> "CfoLiquidityReportInput":
        total_weight = sum(pos.weight for pos in self.positions)
        if total_weight <= 0:
            raise ValueError("Positions weights must be positive and non-zero")
        if not (0.99 <= total_weight <= 1.01):
            raise ValueError("Positions weights must sum to 1.0 within 1% tolerance")

        tickers = [pos.ticker for pos in self.positions]
        if len(tickers) != len(set(tickers)):
            raise ValueError("Positions tickers must be unique")
        return self


class LiquidityBucket(BaseModel):
    """
    Корзина ликвидности с агрегированными метриками.
    """

    bucket: Literal["0-7d", "8-30d", "31-90d", "90d+"] = Field(description="Идентификатор корзины.")
    weight_pct: float = Field(ge=0, le=100, description="Доля портфеля в данной корзине, %.")
    value: Optional[float] = Field(default=None, ge=0, description="Стоимость в данной корзине.")
    tickers: list[str] = Field(default_factory=list, description="Тикеры, попадающие в корзину.")


class LiquidityProfile(BaseModel):
    """
    Профиль ликвидности портфеля.
    """

    buckets: list[LiquidityBucket] = Field(description="Распределение по корзинам ликвидности.")
    quick_ratio_pct: Optional[float] = Field(
        default=None, ge=0, le=100, description="Доля высоколиквидных активов (0-7d), %."
    )
    short_term_ratio_pct: Optional[float] = Field(
        default=None, ge=0, le=100, description="Доля краткосрочных активов (0-30d), %."
    )


class DurationProfile(BaseModel):
    """
    Профиль дюрации для fixed income части портфеля.
    """

    portfolio_duration_years: Optional[float] = Field(
        default=None, ge=0, description="Средневзвешенная дюрация долговой части."
    )
    fixed_income_weight_pct: Optional[float] = Field(
        default=None, ge=0, le=100, description="Доля fixed_income в портфеле, %."
    )
    credit_spread_duration_years: Optional[float] = Field(
        default=None, ge=0, description="Дюрация по кредитным спрэдам."
    )


class CurrencyExposureItem(BaseModel):
    """
    Экспозиция по отдельной валюте.
    """

    currency: str = Field(min_length=3, max_length=3, description="Код валюты (ISO 4217).")
    weight_pct: float = Field(ge=0, le=100, description="Доля в портфеле, %.")
    value: Optional[float] = Field(default=None, ge=0, description="Стоимость в данной валюте.")


class CurrencyExposure(BaseModel):
    """
    Валютная структура портфеля.
    """

    by_currency: list[CurrencyExposureItem] = Field(description="Распределение по валютам.")
    fx_risk_pct: Optional[float] = Field(
        default=None, ge=0, le=100, description="Доля портфеля с валютным риском, %."
    )


class AssetClassWeight(BaseModel):
    """
    Вес класса активов в портфеле.
    """

    asset_class: str = Field(description="Класс актива.")
    weight_pct: float = Field(ge=0, le=100, description="Доля в портфеле, %.")


class CfoConcentrationProfile(BaseModel):
    """
    Концентрации портфеля для CFO-отчёта.
    """

    top1_weight_pct: Optional[float] = Field(default=None, ge=0, le=100)
    top3_weight_pct: Optional[float] = Field(default=None, ge=0, le=100)
    top5_weight_pct: Optional[float] = Field(default=None, ge=0, le=100)
    hhi: Optional[float] = Field(default=None, ge=0, le=1, description="Индекс Херфиндаля-Хиршмана.")
    by_asset_class: list[AssetClassWeight] = Field(
        default_factory=list, description="Распределение по классам активов."
    )


class CfoRiskMetrics(BaseModel):
    """
    Ключевые метрики риска для CFO.
    """

    total_return_pct: Optional[float] = Field(default=None, description="Совокупная доходность, %.")
    annualized_volatility_pct: Optional[float] = Field(default=None, ge=0, description="Годовая волатильность, %.")
    max_drawdown_pct: Optional[float] = Field(default=None, ge=0, description="Максимальная просадка, %.")
    var_light: Optional[VarLightResult] = Field(default=None, description="Parametric VaR.")


class CovenantBreach(BaseModel):
    """
    Информация о нарушении ковенанта.
    """

    code: str = Field(description="Код ковенанта (NET_DEBT_EBITDA, LIQUIDITY_RATIO и т.п.).")
    description: str = Field(description="Описание нарушения.")
    limit: Optional[float] = Field(default=None, description="Установленный лимит.")
    actual: Optional[float] = Field(default=None, description="Фактическое значение.")


class CfoStressScenarioResult(BaseModel):
    """
    Результат стресс-сценария для CFO-отчёта.
    """

    id: str = Field(description="Идентификатор сценария.")
    description: str = Field(description="Описание сценария.")
    pnl_pct: float = Field(description="Оценка P&L, % от стоимости портфеля.")
    pnl_value: Optional[float] = Field(default=None, description="Оценка P&L в базовой валюте.")
    liquidity_ratio_after: Optional[float] = Field(
        default=None, description="Коэффициент ликвидности после стресса."
    )
    covenant_breaches: list[CovenantBreach] = Field(
        default_factory=list, description="Нарушения ковенант при данном сценарии."
    )
    drivers: dict[str, float] = Field(default_factory=dict, description="Ключевые драйверы сценария.")


class CfoRecommendation(BaseModel):
    """
    Рекомендация для CFO.
    """

    priority: Literal["high", "medium", "low"] = Field(description="Приоритет рекомендации.")
    category: Literal["liquidity", "concentration", "duration", "fx_risk", "stress_resilience"] = Field(
        description="Категория рекомендации."
    )
    title: str = Field(description="Краткий заголовок.")
    description: str = Field(description="Развёрнутое описание.")
    action: Optional[str] = Field(default=None, description="Конкретное действие для выполнения.")


class CfoExecutiveSummary(BaseModel):
    """
    Executive summary для CFO.
    """

    overall_liquidity_status: Literal["healthy", "adequate", "warning", "critical"] = Field(
        description="Общий статус ликвидности."
    )
    key_risks: list[str] = Field(description="Ключевые риски.")
    key_strengths: list[str] = Field(default_factory=list, description="Ключевые сильные стороны.")
    action_items: list[str] = Field(default_factory=list, description="Приоритетные действия.")


class CfoLiquidityReport(BaseModel):
    """
    CFO-ориентированный структурированный отчёт по ликвидности и устойчивости портфеля.
    """

    metadata: dict = Field(default_factory=dict, description="Метаданные запроса и расчёта.")
    liquidity_profile: LiquidityProfile = Field(description="Профиль ликвидности портфеля.")
    duration_profile: Optional[DurationProfile] = Field(
        default=None, description="Профиль дюрации для fixed income."
    )
    currency_exposure: CurrencyExposure = Field(description="Валютная структура портфеля.")
    concentration_profile: CfoConcentrationProfile = Field(description="Концентрации портфеля.")
    risk_metrics: Optional[CfoRiskMetrics] = Field(default=None, description="Ключевые метрики риска.")
    stress_scenarios: list[CfoStressScenarioResult] = Field(
        default_factory=list, description="Результаты стресс-тестирования."
    )
    recommendations: list[CfoRecommendation] = Field(
        default_factory=list, description="Рекомендации для CFO."
    )
    executive_summary: CfoExecutiveSummary = Field(description="Executive summary для CFO.")
    error: Optional[ToolErrorModel] = Field(default=None, description="Информация об ошибке.")

    @classmethod
    def success(
        cls,
        *,
        metadata: dict,
        liquidity_profile: LiquidityProfile,
        duration_profile: Optional[DurationProfile],
        currency_exposure: CurrencyExposure,
        concentration_profile: CfoConcentrationProfile,
        risk_metrics: Optional[CfoRiskMetrics],
        stress_scenarios: list[CfoStressScenarioResult],
        recommendations: list[CfoRecommendation],
        executive_summary: CfoExecutiveSummary,
    ) -> "CfoLiquidityReport":
        return cls(
            metadata=metadata,
            liquidity_profile=liquidity_profile,
            duration_profile=duration_profile,
            currency_exposure=currency_exposure,
            concentration_profile=concentration_profile,
            risk_metrics=risk_metrics,
            stress_scenarios=stress_scenarios,
            recommendations=recommendations,
            executive_summary=executive_summary,
            error=None,
        )

    @classmethod
    def from_error(cls, error: ToolErrorModel, metadata: Optional[dict] = None) -> "CfoLiquidityReport":
        return cls(
            metadata=metadata or {},
            liquidity_profile=LiquidityProfile(buckets=[]),
            duration_profile=None,
            currency_exposure=CurrencyExposure(by_currency=[]),
            concentration_profile=CfoConcentrationProfile(),
            risk_metrics=None,
            stress_scenarios=[],
            recommendations=[],
            executive_summary=CfoExecutiveSummary(
                overall_liquidity_status="critical",
                key_risks=["Ошибка при формировании отчёта"],
            ),
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
    # Модели для suggest_rebalance
    "RiskProfileTarget",
    "RebalancePosition",
    "RebalanceInput",
    "RebalanceTrade",
    "RebalanceSummary",
    "RebalanceOutput",
    # Модели для CFO Liquidity Report
    "CfoLiquidityPosition",
    "CovenantLimits",
    "CfoLiquidityReportInput",
    "LiquidityBucket",
    "LiquidityProfile",
    "DurationProfile",
    "CurrencyExposureItem",
    "CurrencyExposure",
    "AssetClassWeight",
    "CfoConcentrationProfile",
    "CfoRiskMetrics",
    "CovenantBreach",
    "CfoStressScenarioResult",
    "CfoRecommendation",
    "CfoExecutiveSummary",
    "CfoLiquidityReport",
]
