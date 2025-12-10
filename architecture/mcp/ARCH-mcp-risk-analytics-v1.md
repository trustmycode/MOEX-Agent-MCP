---
id: ARCH-mcp-risk-analytics
title: "MCP-сервер risk-analytics-mcp"
type: service
layer: domain
owner: @team-moex-agent
version: v1
status: current
created: 2025-12-10
updated: 2025-12-10
tags: [mcp, risk, portfolio, analytics, moex]
depends_on: [ARCH-sdk-moex-iss, ARCH-mcp-moex-iss]
referenced_by: []
---

## Контекст

`risk-analytics-mcp` — специализированный MCP‑сервер для расчёта портфельных
рисков и отчётов по сценариям 5/7/9, описанным в
`docs/SCENARIOS_PORTFOLIO_RISK.md`:

- **5. `issuer_peers_compare`** — сравнительный анализ эмитента с пирами по
  фундаментальным метрикам и мультипликаторам;
- **7. `portfolio_risk`** — портфельный риск‑анализ (концентрации, Var_light,
  стрессы) и предложения ребалансировки;
- **9. `cfo_liquidity_report`** — отчёт CFO по ликвидности и устойчивости
  портфеля с несколькими стресс‑сценариями.

Сервер разгружает агента и базовый `moex-iss-mcp`, беря на себя тяжёлую
числовую обработку: расчёт доходностей, волатильностей, вкладов в риск,
концентрационных показателей, stress‑P&L и, при необходимости, матриц
корреляций.

`risk-analytics-mcp` использует `moex_iss_sdk.IssClient` и/или `moex-iss-mcp`
как источник рыночных данных (котировки, история, индексы) и работает строго
по JSON‑контрактам, зафиксированным в `docs/SCENARIOS_PORTFOLIO_RISK.md`:
`PortfolioRiskInput/Report`, `RebalanceInput/Proposal`,
`CfoLiquidityReportInput/Report`.

## Структура

Целевая структура пакета:

```text
risk_analytics_mcp/
  __init__.py
  main.py                 # Точка входа FastMCP (transport="streamable-http")
  config.py               # RiskMcpConfig: env, лимиты по тикерам/дням, телеметрия
  server.py               # Инициализация FastMCP, регистрация tools

  models/
    __init__.py
    inputs.py             # Pydantic-модели входа (PortfolioRiskInput, RebalanceInput, CfoLiquidityReportInput)
    outputs.py            # Pydantic-модели выхода (PortfolioRiskReport, RebalanceProposal, CfoLiquidityReport)
    errors.py             # Нормализованный error-объект

  tools/
    __init__.py
    analyze_portfolio_risk.py      # risk-analytics-mcp.analyze_portfolio_risk
    suggest_rebalance.py           # risk-analytics-mcp.suggest_rebalance
    build_cfo_liquidity_report.py  # risk-analytics-mcp.build_cfo_liquidity_report
    compute_correlation_matrix.py  # вспомогательный инструмент для drill-down

  providers/
    __init__.py
    fundamentals.py        # FundamentalsDataProvider / MoexIssFundamentalsProvider

  calculations/
    __init__.py
    returns.py             # Расчёт рядов доходностей
    portfolio_metrics.py   # Метрики портфеля и концентрации
    risk_measures.py       # Var_light, стрессовые P&L, max drawdown и др.
    correlation.py         # Построение матрицы корреляций

  telemetry/
    __init__.py
    metrics.py             # Prometheus-метрики
    tracing.py             # OTEL-трейсинг (по возможности)
```

Ключевые зависимости:

- `moex_iss_sdk.IssClient` — источник временных рядов и справочных данных MOEX.
- (Опционально) MCP‑вызовы в `moex-iss-mcp` как единый data-provider для
  котировок/индексов.
- `FundamentalsDataProvider` — абстракция для фундаментальных/CFO‑метрик
  (выручка, EBITDA, долг, мультипликаторы), реализуемая через MOEX ISS.

## Основные инструменты и поведение

### 1. analyze_portfolio_risk (сценарий 7)

**Назначение:** базовый портфельный риск‑анализ по контракту
`PortfolioRiskInput/Report`.

- **Вход** (`PortfolioRiskInput`, см. `SCENARIOS_PORTFOLIO_RISK.md`):
  - структура портфеля (`positions[]` с тикерами/isin, количеством, валютой,
    типом инструмента);
  - базовая валюта `base_currency`;
  - опциональные настройки риск‑профиля (`risk_prefs`).
- **Выход** (`PortfolioRiskReport`):
  - блок `totals` (стоимость портфеля, Var_light, ES_light и др.);
  - блоки концентраций `concentrations.by_issuer/by_sector/by_currency` с
    флагами нарушения лимитов;
  - блок `stress_scenarios[]` с P&L и max drawdown для фиксированных
    стресс‑сценариев (например, `equity_-10_fx_+20`, `rates_+300bp`);
  - блок `flags[]` с «красными флагами» и текстами для агента.

Под капотом инструмент:

1. Через SDK получает OHLCV‑ряды по каждому тикеру (с учётом лимитов по
   датам/количеству тикеров).
2. В модуле `returns.py` строит ряды доходностей по каждому инструменту и
   портфелю.
3. В `portfolio_metrics.py` рассчитывает доходность, волатильность,
   концентрации (top‑N, HHI и др.).
4. В `risk_measures.py` оценивает Var_light и результаты stress‑сценариев.
5. Формирует `PortfolioRiskReport` строго по JSON‑схеме.

### 2. suggest_rebalance (сценарий 7)

**Назначение:** предложить детерминированный план ребалансировки по контракту
`RebalanceInput/Proposal`.

- **Вход** (`RebalanceInput`):
  - `portfolio` — структура портфеля как в `PortfolioRiskInput`;
  - `constraints` — лимиты по max turnover, transaction_cost_bps,
    концентрациям по классам активов/эмитентам/сектора.
- **Выход** (`RebalanceProposal`):
  - целевые риск‑параметры (`target_risk`, например, новый Var_light);
  - массив `orders[]` (тикер, сторона buy/sell, количество);
  - сводка (`summary`) с оборотом и ожидаемым улучшением метрик риска.

Для MVP используется **простая детерминированная эвристика** (не QP/MILP):

- оценить текущие веса по классам активов/секторами;
- вычислить отклонения от таргет‑профиля;
- отсортировать позиции по величине отклонения;
- последовательно продавать «перегруженные» и покупать «недогруженные»
  позиции, пока не выполнены лимиты концентрации и `max_turnover`.

### 3. build_cfo_liquidity_report (сценарий 9)

**Назначение:** построить агрегированный отчёт для CFO по контракту
`CfoLiquidityReportInput/Report`.

- **Вход** (`CfoLiquidityReportInput`):
  - портфель (как в `PortfolioRiskInput`);
  - горизонт в месяцах и список стресс‑сценариев.
- **Выход** (`CfoLiquidityReport`):
  - `liquidity_buckets[]` (0–7d, 8–30d, 31–90d, 90d+);
  - показатели долговой нагрузки и coverage (при наличии данных);
  - результаты стресс‑сценариев с флагами ковенант;
  - `summary_findings[]` с ключевыми выводами для CFO.

Инструмент переиспользует сердцевину расчётов `analyze_portfolio_risk` и
`risk_measures`, переупаковывая их в CFO‑ориентированную структуру.

### 4. compute_correlation_matrix (вспомогательный инструмент)

**Назначение:** построение матрицы корреляций дневных доходностей для
использования в сценариях `portfolio_risk_drill_down` и расширенных отчётах.

- Вход: список тикеров и период (`from_date`, `to_date`).
- Выход: объект с `tickers[]`, `matrix[][]`, `metadata`, `error`.
- Вводится лимит `MAX_TICKERS_FOR_CORRELATION` (например, 15–20); при
  превышении возвращается `error_type = "TOO_MANY_TICKERS"`.

## Связь со сценариями 5/7/9

Архитектура сценариев строго опирается на `docs/SCENARIOS_PORTFOLIO_RISK.md`:

- **Scenario 7 — `portfolio_risk`**
  - Основной инструмент: `analyze_portfolio_risk`.
  - Опциональный инструмент: `suggest_rebalance`.
  - Планировщик агента использует `ScenarioTemplate` с `scenario_type =
    "portfolio_risk"` и ограничением числа детально рассматриваемых бумаг
    через шаг `limit_portfolio`.

- **Scenario 9 — `cfo_liquidity_report`**
  - Основной инструмент: `build_cfo_liquidity_report`, работающий поверх
    ядра `portfolio_risk` и stress‑блока.
  - Планировщик выбирает персону CFO и формирует отчёт с акцентом на
    ликвидности и ковенантах.

- **Scenario 5 — `issuer_peers_compare`**
  - В текущем дизайне `risk-analytics-mcp` предоставляет фундаментальный
    слой (`FundamentalsDataProvider`) и расчёты мультипликаторов/метрик,
    которые могут быть использованы агентом и/или отдельными инструментами
    MCP для построения peers‑отчёта.
  - Конкретный контракт инструмента для peers‑аналитики (например,
    `IssuerPeersCompareInput/Report`) описывается в `SCENARIOS_PORTFOLIO_RISK`
    и SPEC‑документах и может быть реализован как отдельный tool поверх
    `FundamentalsDataProvider`.

## Ошибки и наблюдаемость

- Все входы валидируются по JSON Schema/Pydantic до доменной логики;
  несоответствия приводят к контролируемым ошибкам с `error_type`.
- Исключения SDK (`InvalidTickerError`, `DateRangeTooLargeError`,
  `TooManyTickersError`, `IssTimeoutError`, `IssServerError`, `UnknownIssError`)
  маппятся в `error_type` (`INVALID_TICKER`, `DATE_RANGE_TOO_LARGE`,
  `TOO_MANY_TICKERS`, `ISS_TIMEOUT`, `ISS_5XX`, `UNKNOWN`).
- MCP экспортирует метрики вызовов/ошибок/латентности для каждого инструмента
  (`tool_calls_total`, `tool_errors_total{error_type}`,
  `mcp_http_latency_seconds{tool}`).

## Эволюция

### Планируемые расширения

Согласно задачам `TASK-2025-007`, `TASK-2025-008`, `TASK-2025-051` и др.:

- Добавление advanced‑метрик риска (beta, исторический/многодневный VaR,
  детальные stress‑тесты) и сценария `portfolio_stress_test`.
- Выделение дополнительных инструментов для факторного анализа и stress‑тестов
  портфеля (см. будущий `SPEC_risk_analytics.md`).
- Интеграция с подсистемой планировщика агента (advanced‑ и external‑режимы)
  для более сложных сценариев и cost-aware планирования.

На момент v1 `risk-analytics-mcp` фокусируется на базовом портфельном риске,
Var_light, стресс‑сценариях, ребалансировке и CFO‑отчётах в рамках JSON‑схем,
описанных в `SCENARIOS_PORTFOLIO_RISK.md`.
