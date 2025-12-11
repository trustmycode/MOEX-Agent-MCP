# SPEC — Risk Dashboard / AGI UI профиль

## 1. Назначение

Этот документ фиксирует формат `RiskDashboardSpec`, который агент `moex-market-analyst-agent` возвращает в поле `output.dashboard` A2A-ответа и который используется фронтендом / AGI UI как payload backend‑события `type="risk_dashboard"`.

`RiskDashboardSpec` не является произвольным форматом: это **доменно-ориентированный профиль** поверх общих возможностей AGI UI (backend tool rendering, custom events), оптимизированный под сценарии портфельного риска (7) и связанные сценарии (5/9).

---

## 2. Структура RiskDashboardSpec (высокоуровнево)

```jsonc
{
  "metadata": {
    "as_of": "2025-12-11T10:00:00Z",
    "scenario_type": "portfolio_risk_basic",
    "base_currency": "RUB",
    "portfolio_id": "demo-portfolio-001"
  },
  "metrics": [
    {
      "id": "portfolio_total_return_pct",
      "label": "Доходность портфеля за период",
      "value": 11.63,
      "unit": "%",
      "severity": "info"
    },
    {
      "id": "portfolio_var_light",
      "label": "Var_light (95%, 1д)",
      "value": 4.47,
      "unit": "%",
      "severity": "medium"
    }
  ],
  "charts": [
    {
      "id": "equity_curve",
      "type": "line",
      "title": "Динамика стоимости портфеля",
      "x_axis": { "field": "date", "label": "Дата" },
      "y_axis": { "field": "value", "label": "Стоимость, млн ₽" },
      "series": [
        {
          "id": "portfolio",
          "label": "Портфель",
          "data_ref": "time_series.portfolio_value"
        }
      ]
    },
    {
      "id": "weights_by_ticker",
      "type": "bar",
      "title": "Структура портфеля по бумагам",
      "x_axis": { "field": "ticker", "label": "Тикер" },
      "y_axis": { "field": "weight_pct", "label": "Вес, %" },
      "series": [
        {
          "id": "weights",
          "label": "Вес бумаги",
          "data_ref": "tables.positions"
        }
      ]
    }
  ],
  "tables": [
    {
      "id": "positions",
      "title": "Позиции портфеля",
      "columns": [
        { "id": "ticker", "label": "Тикер" },
        { "id": "weight_pct", "label": "Вес, %" },
        { "id": "total_return_pct", "label": "Доходность, %" },
        { "id": "annualized_volatility_pct", "label": "Волатильность, %" },
        { "id": "max_drawdown_pct", "label": "Max DD, %" }
      ],
      "data_ref": "data.per_instrument"
    },
    {
      "id": "stress_results",
      "title": "Результаты стресс-сценариев",
      "columns": [
        { "id": "id", "label": "Сценарий" },
        { "id": "description", "label": "Описание" },
        { "id": "pnl_pct", "label": "P&L, %" }
      ],
      "data_ref": "data.stress_results"
    }
  ],
  "alerts": [
    {
      "id": "issuer_concentration",
      "severity": "high",
      "message": "Концентрация по эмитенту SBER превышает лимит 15%.",
      "related_ids": ["ticker:SBER", "metric:top1_weight_pct"]
    },
    {
      "id": "var_limit_near",
      "severity": "medium",
      "message": "Var_light 4.5% близок к установленному лимиту 5%.",
      "related_ids": ["metric:portfolio_var_light"]
    }
  ]
}
```

На практике `DashboardSubagent` формирует поле `output.dashboard` на основе:

- `PortfolioRiskBasicOutput` из `risk-analytics-mcp` (per_instrument, portfolio_metrics, concentration_metrics, stress_results, var_light);
- при необходимости — данных `moex-iss-mcp` (история цен для построения equity curve).

---

## 3. Поля и маппинг на MCP-ответы

### 3.1. `metadata`

- `as_of` — момент времени, на который актуальны метрики (обычно `metadata.as_of` из `compute_portfolio_risk_basic` или текущее время UTC).
- `scenario_type` — строковый идентификатор сценария (`portfolio_risk_basic`, `index_risk_scan`, `cfo_liquidity_report` и т.п.), установленный `ResearchPlannerSubagent`.
- `base_currency` — базовая валюта портфеля (`PortfolioAggregates.base_currency` либо значение по умолчанию `RUB`).
- `portfolio_id` — опциональный идентификатор портфеля (если он пришёл во входе MCP/агента).

### 3.2. `metrics[]`

Каждый элемент описывает одну агрегированную метрику:

- `id` — машинно-читаемый идентификатор (используется в alerts и debug);
- `label` — человекочитаемое название на русском;
- `value` — числовое значение (float);
- `unit` — единицы измерения (`"%"`, `"RUB"`, `"bp"`, и т.д.);
- `severity` — метка важности/уровня риска: `info` / `low` / `medium` / `high`.

Примеры маппинга:

- `portfolio_metrics.total_return_pct` → `id="portfolio_total_return_pct"`;
- `portfolio_metrics.annualized_volatility_pct` → `id="portfolio_annualized_volatility_pct"`;
- `concentration_metrics.top1_weight_pct` → `id="top1_weight_pct"`;
- `var_light.var_pct` → `id="portfolio_var_light"`.

### 3.3. `charts[]`

Описание графиков, которые фронт может отрисовать по data_ref:

- `equity_curve`:
  - `data_ref = "time_series.portfolio_value"` — массив `{date, value}`, который вычисляется в RiskAnalyticsSubagent на основе временных рядов `moex-iss-mcp` и результатов агрегирования портфеля.
- `weights_by_ticker`:
  - использует `tables.positions` как источник данных: фронт берёт веса/тикеры и строит bar chart.

### 3.4. `tables[]`

Таблицы поверх структурированных данных:

- `positions`:
  - `data_ref = "data.per_instrument"` соответствует массиву `per_instrument` в ответе `compute_portfolio_risk_basic`;
  - DashboardSubagent может использовать поля `ticker`, `weight`, `total_return_pct`, `annualized_volatility_pct`, `max_drawdown_pct` и конвертировать веса в проценты.
- `stress_results`:
  - `data_ref = "data.stress_results"` соответствует массиву `stress_results` (`StressScenarioResult`) в `PortfolioRiskBasicOutput`.

### 3.5. `alerts[]`

Alerts отображают ключевые «красные флаги» портфеля:

- примеры:
  - превышение лимитов концентрации (`top1_weight_pct` > лимита);
  - Var_light близок к лимиту;
  - сильные стресс‑потери в отдельных сценариях.
- `related_ids` позволяет фронту (и ExplainerSubagent) связывать alerts с конкретными метриками/тикерами.

---

## 4. Профиль для сценария `portfolio_risk_basic`

Для сценария `portfolio_risk_basic` (MVP/сценарий 7 в упрощённом виде) `DashboardSubagent` использует `PortfolioRiskBasicOutput` из `risk-analytics-mcp` следующим образом:

- `metadata`:
  - `as_of` ← `metadata.as_of` (если присутствует) либо текущее время UTC;
  - `scenario_type` = `"portfolio_risk_basic"`;
  - `base_currency` ← `aggregates.base_currency` (если был передан) либо `"RUB"`;
  - `portfolio_id` ← пользовательский идентификатор/alias портфеля (если известен).

- `metrics[]`:
  - `portfolio_total_return_pct` ← `portfolio_metrics.total_return_pct`;
  - `portfolio_annualized_volatility_pct` ← `portfolio_metrics.annualized_volatility_pct`;
  - `portfolio_max_drawdown_pct` ← `portfolio_metrics.max_drawdown_pct`;
  - `top1_weight_pct`, `top3_weight_pct`, `top5_weight_pct`, `portfolio_hhi` ← поля из `concentration_metrics`;
  - `portfolio_var_light` ← `var_light.var_pct` (при наличии блока `var_light`).
  - Поле `severity` рассчитывается по простым порогам (например, Var_light / концентрации ближе к лимиту → `medium`/`high`).

- `tables[]`:
  - `positions`:
    - `data_ref = "data.per_instrument"` и заполняется из `per_instrument[]`;
    - веса конвертируются в проценты (`weight_pct = weight * 100`), остальные поля копируются.
  - `stress_results`:
    - `data_ref = "data.stress_results"` и заполняется из `stress_results[]` (id, description, pnl_pct).

- `charts[]`:
  - `weights_by_ticker` (bar):
    - основан на `data.per_instrument` (тикер/вес, опционально волатильность/доходность);
  - `equity_curve` (line, при наличии агрегированного ряда портфеля):
    - `data_ref = "time_series.portfolio_value"` — этот ряд может быть рассчитан RiskAnalyticsSubagent как накопленная стоимость портфеля по дням.

- `alerts[]`:
  - формируются на основе:
    - превышения лимитов концентрации по эмитенту/сектору (например, `top1_weight_pct` выше предельного значения);
    - величины Var_light относительно установленного лимита;
    - результатов стресс-сценариев (особенно «красных» P&L).

Такой профиль `RiskDashboardSpec` даёт фронтенду достаточно информации для построения основного Risk Cockpit по сценарию `portfolio_risk_basic` без дополнительной бизнес-логики.

---

## 5. Интеграция с AGI UI

### 4.1. Backend tool rendering / custom events

Агент формирует A2A-ответ с полем `output.dashboard: RiskDashboardSpec`. На уровне AGI UI / CopilotKit это может использоваться как:

- backend tool rendering event:

```jsonc
{
  "type": "risk_dashboard",
  "payload": { /* RiskDashboardSpec */ },
  "id": "risk-dashboard-portfolio_risk_basic"
}
```

- custom event: если протокол предусматривает открытые события для произвольных payload.

Фронтенд/AGI UI подписывается на события с `type="risk_dashboard"` и передаёт `payload` в специализированный компонент (например, `RiskCockpitView`), который знает, как интерпретировать структуру `RiskDashboardSpec`.

### 4.2. Streaming (опционально)

Для долгих расчётов возможно постепенное формирование дашборда:

- сначала отправляются простые метрики (размер портфеля, базовые метрики);
- затем — таблица позиций;
- затем — результаты стрессов и Var_light.

AGI UI может использовать `tool output streaming`, чтобы отображать прогресс и частичные данные; при этом формат `RiskDashboardSpec` остаётся неизменным — меняется только момент и состав отправляемых фрагментов.

---

## 6. Расширение и совместимость

- Минимальный профиль, описанный выше, достаточен для MVP сценариев:
  - `portfolio_risk_basic`,
  - `index_risk_scan`.
- В дальнейшем `RiskDashboardSpec` может быть расширен:
  - дополнительными графиками (heatmap корреляций, факторный риск и т.п.);
  - новыми таблицами (ликвидность по временным корзинам, ковенант‑чекеры);
  - дополнительными полями в `metadata` (тенант, профиль RAG, версия методики).
- Все изменения должны быть **backward compatible** для фронтенда:
  - новые поля — опциональны;
  - существующие поля не меняют тип и семантику.
