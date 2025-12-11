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

### 2.2. Tool: `issuer_peers_compare`

**Назначение:** сравнение эмитента с пирами по ключевым фундаментальным и рыночным мультипликаторам. Формирует компактный отчёт с базовым эмитентом, списком пиров, ранжированием по ключевым метрикам и эвристическими флагами.

#### Input JSON Schema

Источник: `docs/schemas/issuer_peers_compare_input.json`

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "IssuerPeersCompareInput",
  "description": "Input schema for risk-analytics-mcp.issuer_peers_compare tool.",
  "type": "object",
  "properties": {
    "ticker": {
      "type": ["string", "null"],
      "minLength": 1,
      "maxLength": 32,
      "description": "Target issuer ticker (preferred identifier), e.g. 'SBER'."
    },
    "isin": {
      "type": ["string", "null"],
      "minLength": 1,
      "maxLength": 20,
      "description": "ISIN identifier (used if ticker is not provided)."
    },
    "issuer_id": {
      "type": ["string", "null"],
      "minLength": 1,
      "description": "MOEX issuer id (optional)."
    },
    "index_ticker": {
      "type": ["string", "null"],
      "default": "IMOEX",
      "description": "Index used to pick peers (e.g. 'IMOEX', 'RTSI')."
    },
    "sector": {
      "type": ["string", "null"],
      "description": "Optional sector filter to narrow peer selection."
    },
    "peer_tickers": {
      "type": ["array", "null"],
      "description": "Explicit list of peer tickers (overrides index-based lookup).",
      "items": { "type": "string", "minLength": 1 },
      "minItems": 1,
      "maxItems": 100
    },
    "max_peers": {
      "type": ["integer", "null"],
      "minimum": 1,
      "maximum": 100,
      "default": 10,
      "description": "Maximum number of peers to include."
    },
    "as_of_date": {
      "type": ["string", "null"],
      "format": "date",
      "description": "Date for data snapshot (YYYY-MM-DD). Defaults to today."
    }
  },
  "additionalProperties": false
}
```

Дополнительно валидируется вне схемы: хотя бы один из `ticker`, `isin`, `issuer_id` должен быть задан.

#### Output JSON Schema

Источник: `docs/schemas/issuer_peers_compare_output.json`

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "IssuerPeersCompareReport",
  "type": "object",
  "properties": {
    "metadata": {
      "type": "object",
      "description": "Request metadata and applied filters.",
      "properties": {
        "as_of": { "type": "string", "format": "date-time" },
        "base_ticker": { "type": "string" },
        "index_ticker": { "type": ["string", "null"] },
        "sector_filter": { "type": ["string", "null"] },
        "peer_count": { "type": "integer", "minimum": 0 },
        "max_peers": { "type": "integer", "minimum": 1 }
      },
      "required": ["base_ticker", "peer_count", "max_peers"]
    },
    "base_issuer": {
      "type": ["object", "null"],
      "description": "Aggregated metrics for base issuer.",
      "properties": {
        "ticker": { "type": "string" },
        "isin": { "type": ["string", "null"] },
        "issuer_name": { "type": ["string", "null"] },
        "sector": { "type": ["string", "null"] },
        "price": { "type": ["number", "null"] },
        "market_cap": { "type": ["number", "null"] },
        "enterprise_value": { "type": ["number", "null"] },
        "pe_ratio": { "type": ["number", "null"] },
        "ev_to_ebitda": { "type": ["number", "null"] },
        "debt_to_ebitda": { "type": ["number", "null"] },
        "roe_pct": { "type": ["number", "null"] },
        "dividend_yield_pct": { "type": ["number", "null"] }
      }
    },
    "peers": {
      "type": "array",
      "description": "Peer issuers with comparable metrics.",
      "items": { "$ref": "#/definitions/IssuerPeersComparePeer" }
    },
    "ranking": {
      "type": "array",
      "description": "Ranking of base issuer against peers for key metrics.",
      "items": {
        "type": "object",
        "properties": {
          "metric": { "type": "string" },
          "value": { "type": ["number", "null"] },
          "rank": { "type": ["integer", "null"], "minimum": 1 },
          "total": { "type": "integer", "minimum": 0 },
          "percentile": { "type": ["number", "null"], "minimum": 0, "maximum": 1 }
        },
        "required": ["metric", "total"]
      }
    },
    "flags": {
      "type": "array",
      "description": "Heuristic flags (overvalued/undervalued, high_leverage, etc.).",
      "items": {
        "type": "object",
        "properties": {
          "code": { "type": "string" },
          "severity": { "type": "string", "enum": ["low", "medium", "high"] },
          "message": { "type": "string" },
          "metric": { "type": ["string", "null"] }
        },
        "required": ["code", "severity", "message"]
      }
    },
    "error": {
      "type": ["object", "null"],
      "description": "Error details if comparison failed.",
      "properties": {
        "error_type": { "type": "string" },
        "message": { "type": "string" },
        "details": { "type": ["object", "null"] }
      },
      "required": ["error_type", "message"]
    }
  },
  "required": ["metadata", "peers", "ranking", "flags"]
}
```

#### Поддерживаемые `error_type` для `issuer_peers_compare`

| error_type | Описание |
|------------|----------|
| `INVALID_TICKER` | Указанный тикер не найден в ISS. |
| `NO_PEERS_FOUND` | Не удалось найти пиров по заданным критериям (индекс/сектор). |
| `NO_FUNDAMENTAL_DATA` | Недостаточно фундаментальных данных по базовому эмитенту. |
| `VALIDATION_ERROR` | Нарушение контрактов схемы/валидаторов. |
| `ISS_TIMEOUT` / `ISS_5XX` | Сетевые/серверные ошибки ISS. |
| `UNKNOWN` | Прочие неисчерпывающие ошибки. |

#### Пример запроса/ответа

**Request:**
```json
{
  "ticker": "SBER",
  "index_ticker": "IMOEX",
  "sector": "FINANCIALS",
  "max_peers": 5
}
```

**Response:**
```json
{
  "metadata": {
    "as_of": "2025-01-15T10:30:00Z",
    "base_ticker": "SBER",
    "index_ticker": "IMOEX",
    "sector_filter": "FINANCIALS",
    "peer_count": 4,
    "max_peers": 5
  },
  "base_issuer": {
    "ticker": "SBER",
    "issuer_name": "Сбербанк России ПАО",
    "sector": "FINANCIALS",
    "price": 280.5,
    "market_cap": 6300000000000,
    "pe_ratio": 5.2,
    "ev_to_ebitda": null,
    "debt_to_ebitda": null,
    "roe_pct": 22.5,
    "dividend_yield_pct": 8.3
  },
  "peers": [
    {
      "ticker": "VTBR",
      "issuer_name": "Банк ВТБ ПАО",
      "sector": "FINANCIALS",
      "pe_ratio": 3.8,
      "roe_pct": 15.2,
      "dividend_yield_pct": 0.0
    }
  ],
  "ranking": [
    { "metric": "pe_ratio", "value": 5.2, "rank": 2, "total": 5, "percentile": 0.6 },
    { "metric": "roe_pct", "value": 22.5, "rank": 1, "total": 5, "percentile": 1.0 },
    { "metric": "dividend_yield_pct", "value": 8.3, "rank": 1, "total": 5, "percentile": 1.0 }
  ],
  "flags": [
    {
      "code": "HIGH_ROE",
      "severity": "low",
      "message": "ROE выше 75-го перцентиля среди пиров",
      "metric": "roe_pct"
    },
    {
      "code": "HIGH_DIVIDEND",
      "severity": "low",
      "message": "Дивидендная доходность в топ-25% среди пиров",
      "metric": "dividend_yield_pct"
    }
  ],
  "error": null
}
```

---

### 2.3. Tool: `compute_correlation_matrix`

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

### 2.4. Tool: `suggest_rebalance`

**Назначение:** формирование детерминированного предложения по ребалансировке портфеля с учётом заданного профиля риска (ограничения по классам активов, концентрации, обороту).

#### Input JSON Schema

Источник: `docs/schemas/suggest_rebalance_input.json`

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "SuggestRebalanceInput",
  "type": "object",
  "properties": {
    "positions": {
      "type": "array",
      "minItems": 1,
      "description": "Current portfolio positions with weights.",
      "items": {
        "type": "object",
        "properties": {
          "ticker": { "type": "string", "description": "Ticker, e.g. SBER." },
          "current_weight": { "type": "number", "minimum": 0, "maximum": 1 },
          "asset_class": { "type": "string", "default": "equity" },
          "issuer": { "type": ["string", "null"] }
        },
        "required": ["ticker", "current_weight"]
      }
    },
    "total_portfolio_value": { "type": ["number", "null"], "exclusiveMinimum": 0 },
    "risk_profile": {
      "type": "object",
      "properties": {
        "max_equity_weight": { "type": "number", "default": 1.0 },
        "max_fixed_income_weight": { "type": "number", "default": 1.0 },
        "max_fx_weight": { "type": "number", "default": 1.0 },
        "max_single_position_weight": { "type": "number", "default": 0.25 },
        "max_issuer_weight": { "type": "number", "default": 0.30 },
        "max_turnover": { "type": "number", "default": 0.50 },
        "target_asset_class_weights": { "type": "object" }
      }
    }
  },
  "required": ["positions"]
}
```

Дополнительно валидируется вне схемы: сумма `current_weight` ≈ 1.0 (tolerance 1%), уникальность тикеров.

#### Output JSON Schema

Источник: `docs/schemas/suggest_rebalance_output.json`

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "SuggestRebalanceOutput",
  "type": "object",
  "properties": {
    "metadata": { "type": "object" },
    "target_weights": {
      "type": "object",
      "description": "Target weights by ticker after rebalancing."
    },
    "trades": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "ticker": { "type": "string" },
          "side": { "type": "string", "enum": ["buy", "sell"] },
          "weight_delta": { "type": "number" },
          "target_weight": { "type": "number" },
          "estimated_value": { "type": ["number", "null"] },
          "reason": { "type": "string" }
        }
      }
    },
    "summary": {
      "type": ["object", "null"],
      "properties": {
        "total_turnover": { "type": "number" },
        "turnover_within_limit": { "type": "boolean" },
        "positions_changed": { "type": "integer" },
        "concentration_issues_resolved": { "type": "integer" },
        "asset_class_issues_resolved": { "type": "integer" },
        "warnings": { "type": "array", "items": { "type": "string" } }
      }
    },
    "error": { "type": ["object", "null"] }
  },
  "required": ["metadata", "target_weights", "trades"]
}
```

#### Поддерживаемые `error_type` для `suggest_rebalance`

| error_type | Описание |
|------------|----------|
| `EMPTY_PORTFOLIO` | Портфель не содержит позиций. |
| `CONSTRAINTS_INFEASIBLE` | Невозможно достичь целевого профиля (например, 1 позиция с лимитом <100%). |
| `VALIDATION_ERROR` | Нарушение контрактов схемы/валидаторов. |
| `UNKNOWN` | Прочие неисчерпывающие ошибки. |

#### Пример запроса/ответа

**Request:**
```json
{
  "positions": [
    { "ticker": "SBER", "current_weight": 0.45, "asset_class": "equity" },
    { "ticker": "GAZP", "current_weight": 0.20, "asset_class": "equity" },
    { "ticker": "LKOH", "current_weight": 0.15, "asset_class": "equity" },
    { "ticker": "OFZ", "current_weight": 0.20, "asset_class": "fixed_income" }
  ],
  "total_portfolio_value": 5000000.0,
  "risk_profile": {
    "max_single_position_weight": 0.25,
    "max_issuer_weight": 0.30,
    "max_turnover": 0.30
  }
}
```

**Response:**
```json
{
  "metadata": {
    "as_of": "2025-01-15T10:30:00Z",
    "input_positions_count": 4,
    "total_portfolio_value": 5000000.0,
    "risk_profile": {
      "max_turnover": 0.30,
      "max_single_position_weight": 0.25,
      "max_issuer_weight": 0.30
    }
  },
  "target_weights": {
    "SBER": 0.25,
    "GAZP": 0.25,
    "LKOH": 0.25,
    "OFZ": 0.25
  },
  "trades": [
    {
      "ticker": "SBER",
      "side": "sell",
      "weight_delta": -0.20,
      "target_weight": 0.25,
      "estimated_value": 1000000.0,
      "reason": "rebalance"
    },
    {
      "ticker": "GAZP",
      "side": "buy",
      "weight_delta": 0.05,
      "target_weight": 0.25,
      "estimated_value": 250000.0,
      "reason": "rebalance"
    },
    {
      "ticker": "LKOH",
      "side": "buy",
      "weight_delta": 0.10,
      "target_weight": 0.25,
      "estimated_value": 500000.0,
      "reason": "rebalance"
    },
    {
      "ticker": "OFZ",
      "side": "buy",
      "weight_delta": 0.05,
      "target_weight": 0.25,
      "estimated_value": 250000.0,
      "reason": "rebalance"
    }
  ],
  "summary": {
    "total_turnover": 0.20,
    "turnover_within_limit": true,
    "positions_changed": 4,
    "concentration_issues_resolved": 1,
    "asset_class_issues_resolved": 0,
    "warnings": []
  },
  "error": null
}
```

---

### 2.5. Tool: `build_cfo_liquidity_report`

**Назначение:** формирование CFO-ориентированного структурированного отчёта по ликвидности и устойчивости портфеля (Сценарий 9). Отчёт включает профиль ликвидности, дюрацию, валютную экспозицию, концентрации, стресс-сценарии с проверкой ковенант, рекомендации и executive summary.

#### Input JSON Schema

Источник: `docs/schemas/cfo_liquidity_report_input.json`

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "CfoLiquidityReportInput",
  "type": "object",
  "properties": {
    "positions": {
      "type": "array",
      "minItems": 1,
      "description": "Позиции портфеля с характеристиками ликвидности.",
      "items": {
        "type": "object",
        "properties": {
          "ticker": { "type": "string", "description": "Ticker, e.g. SBER." },
          "weight": { "type": "number", "exclusiveMinimum": 0, "maximum": 1 },
          "asset_class": { "type": "string", "enum": ["equity", "fixed_income", "cash", "fx", "credit"] },
          "liquidity_bucket": { "type": "string", "enum": ["0-7d", "8-30d", "31-90d", "90d+"] },
          "currency": { "type": "string", "minLength": 3, "maxLength": 3 }
        },
        "required": ["ticker", "weight"]
      }
    },
    "total_portfolio_value": { "type": ["number", "null"], "exclusiveMinimum": 0 },
    "base_currency": { "type": "string", "default": "RUB" },
    "from_date": { "type": "string", "format": "date" },
    "to_date": { "type": "string", "format": "date" },
    "horizon_months": { "type": "integer", "minimum": 1, "maximum": 36, "default": 12 },
    "stress_scenarios": { "type": ["array", "null"], "items": { "type": "string" } },
    "aggregates": { "type": ["object", "null"] },
    "covenant_limits": {
      "type": ["object", "null"],
      "properties": {
        "max_net_debt_ebitda": { "type": ["number", "null"] },
        "min_liquidity_ratio": { "type": ["number", "null"] },
        "min_current_ratio": { "type": ["number", "null"] }
      }
    }
  },
  "required": ["positions", "from_date", "to_date"]
}
```

#### Output JSON Schema

Источник: `docs/schemas/cfo_liquidity_report_output.json`

Основные секции выхода:

- `metadata` — метаданные запроса и расчёта;
- `liquidity_profile` — профиль ликвидности по корзинам (0-7d, 8-30d, 31-90d, 90d+);
- `duration_profile` — профиль дюрации для fixed income части;
- `currency_exposure` — валютная структура портфеля;
- `concentration_profile` — концентрации по позициям и классам активов;
- `risk_metrics` — ключевые метрики риска (доходность, волатильность, VaR);
- `stress_scenarios` — результаты стресс-тестирования с проверкой ковенант;
- `recommendations` — рекомендации для CFO;
- `executive_summary` — executive summary со статусом ликвидности, ключевыми рисками и действиями.

#### Поддерживаемые `error_type` для `build_cfo_liquidity_report`

| error_type | Описание |
|------------|----------|
| `VALIDATION_ERROR` | Нарушение контрактов схемы/валидаторов. |
| `TOO_MANY_TICKERS` | Превышен лимит позиций в портфеле. |
| `DATE_RANGE_TOO_LARGE` | Превышена глубина истории. |
| `ISS_TIMEOUT` / `ISS_5XX` | Сетевые/серверные ошибки ISS. |
| `UNKNOWN` | Прочие неисчерпывающие ошибки. |

#### Пример запроса/ответа

**Request:**
```json
{
  "positions": [
    { "ticker": "SBER", "weight": 0.30, "asset_class": "equity", "liquidity_bucket": "0-7d", "currency": "RUB" },
    { "ticker": "GAZP", "weight": 0.20, "asset_class": "equity", "liquidity_bucket": "0-7d", "currency": "RUB" },
    { "ticker": "OFZ26238", "weight": 0.25, "asset_class": "fixed_income", "liquidity_bucket": "8-30d", "currency": "RUB" },
    { "ticker": "USDRUB", "weight": 0.15, "asset_class": "fx", "liquidity_bucket": "0-7d", "currency": "USD" },
    { "ticker": "LKOH", "weight": 0.10, "asset_class": "equity", "liquidity_bucket": "0-7d", "currency": "RUB" }
  ],
  "from_date": "2024-01-01",
  "to_date": "2024-12-31",
  "base_currency": "RUB",
  "total_portfolio_value": 10000000.0,
  "horizon_months": 12,
  "stress_scenarios": ["base_case", "equity_-10_fx_+20", "rates_+300bp"],
  "aggregates": {
    "fixed_income_duration_years": 3.5
  },
  "covenant_limits": {
    "min_liquidity_ratio": 0.25
  }
}
```

**Response:**
```json
{
  "metadata": {
    "as_of": "2025-01-15T10:30:00Z",
    "from_date": "2024-01-01",
    "to_date": "2024-12-31",
    "horizon_months": 12,
    "base_currency": "RUB",
    "total_portfolio_value": 10000000.0,
    "positions_count": 5
  },
  "liquidity_profile": {
    "buckets": [
      { "bucket": "0-7d", "weight_pct": 75.0, "value": 7500000.0, "tickers": ["SBER", "GAZP", "USDRUB", "LKOH"] },
      { "bucket": "8-30d", "weight_pct": 25.0, "value": 2500000.0, "tickers": ["OFZ26238"] },
      { "bucket": "31-90d", "weight_pct": 0.0, "value": 0.0, "tickers": [] },
      { "bucket": "90d+", "weight_pct": 0.0, "value": 0.0, "tickers": [] }
    ],
    "quick_ratio_pct": 75.0,
    "short_term_ratio_pct": 100.0
  },
  "duration_profile": {
    "portfolio_duration_years": 3.5,
    "fixed_income_weight_pct": 25.0,
    "credit_spread_duration_years": null
  },
  "currency_exposure": {
    "by_currency": [
      { "currency": "RUB", "weight_pct": 85.0, "value": 8500000.0 },
      { "currency": "USD", "weight_pct": 15.0, "value": 1500000.0 }
    ],
    "fx_risk_pct": 15.0
  },
  "concentration_profile": {
    "top1_weight_pct": 30.0,
    "top3_weight_pct": 75.0,
    "top5_weight_pct": 100.0,
    "hhi": 0.225,
    "by_asset_class": [
      { "asset_class": "equity", "weight_pct": 60.0 },
      { "asset_class": "fixed_income", "weight_pct": 25.0 },
      { "asset_class": "fx", "weight_pct": 15.0 }
    ]
  },
  "risk_metrics": {
    "total_return_pct": 15.2,
    "annualized_volatility_pct": 18.5,
    "max_drawdown_pct": -8.3,
    "var_light": {
      "method": "parametric_normal",
      "confidence_level": 0.95,
      "horizon_days": 1,
      "var_pct": 1.92
    }
  },
  "stress_scenarios": [
    {
      "id": "base_case",
      "description": "Базовый сценарий — без стрессов.",
      "pnl_pct": 0.0,
      "pnl_value": 0.0,
      "liquidity_ratio_after": 100.0,
      "covenant_breaches": []
    },
    {
      "id": "equity_-10_fx_+20",
      "description": "Падение акций на 10% и ослабление базовой валюты на 20%.",
      "pnl_pct": -3.0,
      "pnl_value": -300000.0,
      "liquidity_ratio_after": 97.0,
      "covenant_breaches": [],
      "drivers": {
        "equity_weight_pct": 60.0,
        "fx_exposed_weight_pct": 15.0
      }
    },
    {
      "id": "rates_+300bp",
      "description": "Рост ставок на 300 bps с учётом дюрации долгового портфеля.",
      "pnl_pct": -2.63,
      "pnl_value": -262500.0,
      "liquidity_ratio_after": 97.37,
      "covenant_breaches": [],
      "drivers": {
        "fixed_income_weight_pct": 25.0,
        "duration_years": 3.5
      }
    }
  ],
  "recommendations": [
    {
      "priority": "high",
      "category": "concentration",
      "title": "Высокая концентрация в одной позиции",
      "description": "Крупнейшая позиция занимает 30% портфеля, что создаёт существенный идиосинкратический риск.",
      "action": "Снизить долю крупнейшей позиции до уровня не более 20-25%."
    },
    {
      "priority": "medium",
      "category": "concentration",
      "title": "Повышенная концентрация портфеля",
      "description": "Индекс Херфиндаля-Хиршмана (0.225) указывает на недостаточную диверсификацию.",
      "action": "Увеличить количество позиций или перераспределить веса для улучшения диверсификации."
    }
  ],
  "executive_summary": {
    "overall_liquidity_status": "adequate",
    "key_risks": [
      "Высокая концентрация в отдельных позициях",
      "Потенциальные потери до 3% при стрессе"
    ],
    "key_strengths": [
      "Высокий уровень ликвидности"
    ],
    "action_items": [
      "Снизить долю крупнейшей позиции до уровня не более 20-25%."
    ]
  },
  "error": null
}
```

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
