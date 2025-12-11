# SPEC — risk-analytics-mcp

Документ описывает формальный контракт MCP-сервера `risk-analytics-mcp`:

- назначение сервера и endpoints;
- JSON Schema входа/выхода для инструментов `compute_portfolio_risk_basic` и `compute_correlation_matrix`;
- формат ошибок;
- процесс синхронизации моделей ↔ JSON Schema ↔ `tools.json`.

---

## 1. Общие сведения

- MCP-сервер: `risk-analytics-mcp`
- Транспорт: FastMCP (`streamable-http`)
- Endpoint MCP: `/mcp`
- Дополнительные endpoints:
  - `/health` — `{"status":"ok"}`
  - `/metrics` — Prometheus (`tool_calls_total{tool}`, `tool_errors_total{tool,error_type}`, `mcp_http_latency_seconds{tool}`)
- Источник данных: `moex_iss_sdk.IssClient` (и/или вызовы `moex-iss-mcp`) с унифицированным маппером ошибок `ToolErrorModel`.
- Pydantic-модели: `risk_analytics_mcp.models`.

---

## 2. Инструменты MCP

### 2.1. Tool: `compute_portfolio_risk_basic`

**Назначение:** расчёт базовых метрик портфеля (доходность, волатильность, max drawdown, концентрации) для указанных позиций и периода.

#### Input JSON Schema

Источник: `docs/schemas/compute_portfolio_risk_basic_input.json`

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "ComputePortfolioRiskBasicInput",
  "description": "Input for risk-analytics-mcp.compute_portfolio_risk_basic.",
  "type": "object",
  "properties": {
    "positions": {
      "type": "array",
      "minItems": 1,
      "description": "Portfolio positions with weights that must sum to ~1.0.",
      "items": {
        "type": "object",
        "properties": {
          "ticker": {
            "type": "string",
            "minLength": 1,
            "maxLength": 32,
            "description": "Ticker, e.g. SBER."
          },
          "weight": {
            "type": "number",
            "exclusiveMinimum": 0,
            "maximum": 1,
            "description": "Weight of the instrument in the portfolio (0..1)."
          },
          "board": {
            "type": ["string", "null"],
            "minLength": 1,
            "maxLength": 16,
            "description": "MOEX board (optional)."
          }
        },
        "required": ["ticker", "weight"],
        "additionalProperties": false
      }
    },
    "from_date": {
      "type": "string",
      "format": "date",
      "description": "Start date, inclusive (YYYY-MM-DD)."
    },
    "to_date": {
      "type": "string",
      "format": "date",
      "description": "End date, inclusive (YYYY-MM-DD). Must be >= from_date."
    },
    "rebalance": {
      "type": "string",
      "enum": ["buy_and_hold", "monthly"],
      "default": "buy_and_hold",
      "description": "Rebalancing policy: buy_and_hold (default) or monthly."
    }
  },
  "required": ["positions", "from_date", "to_date"],
  "additionalProperties": false
}
```

Дополнительно валидируется вне схемы: сумма весов ≈ 1.0 (tolerance 1%), уникальность тикеров, `to_date >= from_date`.

#### Output JSON Schema

Источник: `docs/schemas/compute_portfolio_risk_basic_output.json`

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "ComputePortfolioRiskBasicOutput",
  "description": "Output of risk-analytics-mcp.compute_portfolio_risk_basic.",
  "type": "object",
  "properties": {
    "metadata": {
      "type": "object",
      "description": "Request metadata: dates, rebalance policy, tickers, data source.",
      "properties": {
        "as_of": { "type": "string", "format": "date-time" },
        "from_date": { "type": "string", "format": "date" },
        "to_date": { "type": "string", "format": "date" },
        "rebalance": { "type": "string", "enum": ["buy_and_hold", "monthly"] },
        "tickers": {
          "type": "array",
          "items": { "type": "string" }
        },
        "iss_base_url": { "type": "string" }
      },
      "additionalProperties": true
    },
    "per_instrument": {
      "type": "array",
      "minItems": 0,
      "description": "Per-instrument risk metrics.",
      "items": {
        "type": "object",
        "properties": {
          "ticker": { "type": "string", "description": "Ticker, e.g. SBER." },
          "weight": { "type": "number", "minimum": 0, "maximum": 1, "description": "Weight of the instrument (0..1)." },
          "total_return_pct": { "type": ["number", "null"], "description": "Total return over the period, %." },
          "annualized_volatility_pct": { "type": ["number", "null"], "description": "Annualized volatility from daily returns, %." },
          "max_drawdown_pct": { "type": ["number", "null"], "description": "Max drawdown over the period, %." }
        },
        "required": ["ticker", "weight"],
        "additionalProperties": false
      }
    },
    "portfolio_metrics": {
      "type": "object",
      "description": "Aggregated portfolio metrics.",
      "properties": {
        "total_return_pct": { "type": ["number", "null"], "description": "Total portfolio return, %." },
        "annualized_volatility_pct": { "type": ["number", "null"], "description": "Annualized portfolio volatility, %." },
        "max_drawdown_pct": { "type": ["number", "null"], "description": "Max portfolio drawdown, %." }
      },
      "additionalProperties": false
    },
    "concentration_metrics": {
      "type": "object",
      "description": "Basic concentration metrics.",
      "properties": {
        "top1_weight_pct": { "type": ["number", "null"], "description": "Weight of top-1 position, %." },
        "top3_weight_pct": { "type": ["number", "null"], "description": "Weight of top-3 positions, %." },
        "top5_weight_pct": { "type": ["number", "null"], "description": "Weight of top-5 positions, %." },
        "hhi": { "type": ["number", "null"], "description": "Herfindahl-Hirschman Index (0..1)." }
      },
      "additionalProperties": false
    },
    "error": {
      "type": ["object", "null"],
      "description": "Error details if the calculation failed.",
      "properties": {
        "error_type": { "type": "string" },
        "message": { "type": "string" },
        "details": { "type": ["object", "null"], "additionalProperties": true }
      },
      "required": ["error_type", "message"],
      "additionalProperties": true
    }
  },
  "required": ["metadata", "per_instrument", "portfolio_metrics", "concentration_metrics"],
  "additionalProperties": false
}
```

#### Дополнения MVP (стрессы и Var_light)

- **Новые входные поля**:  
  - `aggregates` — агрегированные характеристики портфеля (дюрация, валютная структура, веса классов активов) для стресс-сценариев;  
  - `stress_scenarios` — список id сценариев (если пусто, берутся дефолтные);  
  - `var_config` — параметры Var_light (`confidence_level`, `horizon_days`, `reference_volatility_pct`).
- **Новые выходные поля**:  
  - `stress_results[]` — результат стрессов с `id`, `description`, `pnl_pct` и `drivers`;  
  - `var_light` — параметрический VaR с указанием метода, горизонта и использованной волатильности.
- **Преднастроенные сценарии**:  
  - `equity_-10_fx_+20` — падение акций на 10% + ослабление базовой валюты на 20%;  
  - `rates_+300bp` — рост ставок на 300 bps с учётом дюрации;  
  - `credit_spreads_+150bp` — расширение кредитных спредов на 150 bps.

### 2.2. Tool: `compute_correlation_matrix`

**Назначение:** построение матрицы корреляций дневных доходностей для заданных тикеров и периода.

#### Input JSON Schema

Источник: `docs/schemas/compute_correlation_matrix_input.json`

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "ComputeCorrelationMatrixInput",
  "description": "Input for risk-analytics-mcp.compute_correlation_matrix.",
  "type": "object",
  "properties": {
    "tickers": {
      "type": "array",
      "minItems": 2,
      "description": "List of tickers for correlation calculation (unique, uppercased).",
      "items": {
        "type": "string",
        "minLength": 1
      }
    },
    "from_date": {
      "type": "string",
      "format": "date",
      "description": "Start date, inclusive (YYYY-MM-DD)."
    },
    "to_date": {
      "type": "string",
      "format": "date",
      "description": "End date, inclusive (YYYY-MM-DD). Must be >= from_date."
    }
  },
  "required": ["tickers", "from_date", "to_date"],
  "additionalProperties": false
}
```

Дополнительно валидируется вне схемы: уникальность тикеров, лимит `MAX_TICKERS_FOR_CORRELATION`, `to_date >= from_date`.

#### Output JSON Schema

Источник: `docs/schemas/compute_correlation_matrix_output.json`

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "ComputeCorrelationMatrixOutput",
  "description": "Output of risk-analytics-mcp.compute_correlation_matrix.",
  "type": "object",
  "properties": {
    "metadata": {
      "type": "object",
      "description": "Request metadata and calculation details.",
      "properties": {
        "from_date": { "type": "string", "format": "date" },
        "to_date": { "type": "string", "format": "date" },
        "tickers": {
          "type": "array",
          "items": { "type": "string" }
        },
        "method": { "type": "string" },
        "num_observations": { "type": ["integer", "null"], "minimum": 0 },
        "iss_base_url": { "type": "string" }
      },
      "additionalProperties": true
    },
    "tickers": {
      "type": "array",
      "description": "Tickers in calculation order.",
      "items": { "type": "string" }
    },
    "matrix": {
      "type": "array",
      "description": "Correlation matrix (rows align with tickers).",
      "items": {
        "type": "array",
        "items": { "type": "number" }
      }
    },
    "error": {
      "type": ["object", "null"],
      "description": "Error details if the calculation failed.",
      "properties": {
        "error_type": { "type": "string" },
        "message": { "type": "string" },
        "details": { "type": ["object", "null"], "additionalProperties": true }
      },
      "required": ["error_type", "message"],
      "additionalProperties": true
    }
  },
  "required": ["metadata", "tickers", "matrix"],
  "additionalProperties": false
}
```

---

## 3. Формат ошибок и `error_type`

Все инструменты возвращают `error` в формате `ToolErrorModel`:

```json
{
  "error_type": "INVALID_TICKER | DATE_RANGE_TOO_LARGE | TOO_MANY_TICKERS | ISS_TIMEOUT | ISS_5XX | VALIDATION_ERROR | INSUFFICIENT_DATA | UNKNOWN",
  "message": "Human-readable message",
  "details": { "optional": "structured details" }
}
```

- `INVALID_TICKER` — тикер/борда не найдены в ISS.
- `DATE_RANGE_TOO_LARGE` — превышен лимит глубины истории.
- `TOO_MANY_TICKERS` — превышен лимит тикеров (портфель или корреляции).
- `INSUFFICIENT_DATA` — недостаточно наблюдений для корреляции.
- `ISS_TIMEOUT` / `ISS_5XX` — сетевые/серверные ошибки ISS.
- `VALIDATION_ERROR` — нарушение контрактов схемы/валидаторов.
- `UNKNOWN` — прочие неисчерпывающие ошибки.

---

## 4. Синхронизация моделей, схем и `tools.json`

1. **Базовые модели**: обновлять Pydantic-модели в `risk_analytics_mcp.models` (единственный источник правды для полей).
2. **JSON Schema**: поддерживать `docs/schemas/*.json` в актуальном состоянии (копия Pydantic-схем с дополнительными бизнес-ограничениями).  
   - Проверка корректности схем:  
     `python - <<'PY'\nimport json\nfrom pathlib import Path\nfrom jsonschema import Draft7Validator\nfor path in Path(\"docs/schemas\").glob(\"compute_*_*.json\"):\n    Draft7Validator.check_schema(json.loads(path.read_text()))\n    print(f\"Schema OK: {path}\")\nPY`
3. **Соответствие Pydantic ↔ Schema**: при правках моделей сравнивать `model_json_schema()` с файлами схем и переносить отличия вручную или через вспомогательный скрипт (пример чернового сравнения):  
   `python - <<'PY'\nfrom risk_analytics_mcp.models import PortfolioRiskInput, PortfolioRiskBasicOutput, CorrelationMatrixInput, CorrelationMatrixOutput\nmodels = [PortfolioRiskInput, PortfolioRiskBasicOutput, CorrelationMatrixInput, CorrelationMatrixOutput]\nfor model in models:\n    schema = model.model_json_schema()\n    print(f\"Pydantic schema generated for {model.__name__} (keys: {list(schema.get('properties', {}).keys())})\")\nPY`
4. **tools.json**: обновлять ссылки на схемы и описания инструментов в `risk_analytics_mcp/tools.json` (см. раздел 2) после каждого изменения схем. Проверка JSON: `python -m json.tool risk_analytics_mcp/tools.json`.
5. **Интеграционная проверка**: запуск `jsonschema.validate` на реальных payloads/ответах из тестов `tests/` (добавить при появлении интеграционных тестов для risk-analytics-mcp).

Этот процесс исключает расхождения между кодом, схемами и артефактами регистрации MCP в Evolution AI Agents.

---

## 5. FundamentalsDataProvider (MVP)

Для сценариев 5/7/9 (`issuer_peers_compare`, `portfolio_risk`, `cfo_liquidity_report`) в
`risk-analytics-mcp` введён слой `FundamentalsDataProvider` с реализацией
`MoexIssFundamentalsProvider` поверх `moex_iss_sdk.IssClient`.

- Базовая доменная модель: `IssuerFundamentals` (`risk_analytics_mcp.models`), включающая:
  - идентификаторы: `ticker`, `isin`, `issuer_name`, `reporting_currency`, `as_of`;
  - отчётные метрики (поля есть в модели, значения могут быть `null`, если ISS не даёт JSON‑данных):
    `revenue`, `ebitda`, `ebit`, `net_income`, `total_debt`, `net_debt`,
    производные `debt_to_ebitda`, `ev_to_ebitda`, `pe_ratio`;
  - рыночные метрики (минимально гарантированный набор для MVP):
    - `price` — последняя рыночная цена (из `get_security_snapshot`);
    - `shares_outstanding` — объём выпуска (`ISSUESIZE` из `/securities/{ticker}.json`);
    - `market_cap` — капитализация (`price * shares_outstanding`);
    - `dividend_yield_pct` — дивидендная доходность, рассчитанная как сумма дивидендов
      за последний год (`get_security_dividends`) / `price`;
    - `free_float_shares`, `free_float_pct`, `enterprise_value` — поля модели, которые
      могут быть `null` до появления стабильного источника данных.
- Кэширование: `MoexIssFundamentalsProvider` использует in‑memory `TTLCache` (по умолчанию
  900 секунд, настраивается `RISK_FUNDAMENTALS_CACHE_TTL_SECONDS`) на уровне агрегированных
  `IssuerFundamentals`, поверх кэша/лимитов самого `IssClient`.
- Все будущие инструменты и сценарии, которым нужен фундаментал, должны получать его
  только через `FundamentalsDataProvider`, а не обращаться к MOEX ISS напрямую.
