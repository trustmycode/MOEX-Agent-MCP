# SPEC — moex-iss-mcp и A2A контракт

Документ описывает:

- формальный контракт MCP-сервера `moex-iss-mcp`;
- JSON Schema входных/выходных структур MCP-инструментов;
- пример `tools.json`;
- JSON Schema A2A-взаимодействия агента.

---

## 1. Общие сведения

- MCP-сервер: `moex-iss-mcp`
- Транспорт: FastMCP (HTTP / SSE)
- Основной endpoint: `/mcp`
- Дополнительные endpoints:
  - `/health` — `{"status":"ok"}`;
  - `/metrics` — Prometheus.

Все инструменты описаны через Pydantic-модели в коде и дублируются JSON Schema (ниже).

---

## 2. Инструменты MCP

### 2.1. Tool: `get_security_snapshot`

**Назначение:** краткий «снимок» по инструменту (последняя цена, изменение, ликвидность).

#### Input JSON Schema

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "GetSecuritySnapshotInput",
  "type": "object",
  "properties": {
    "ticker": {
      "type": "string",
      "minLength": 1,
      "maxLength": 16,
      "description": "Security ticker, e.g. 'SBER'."
    },
    "board": {
      "type": "string",
      "minLength": 1,
      "maxLength": 16,
      "description": "MOEX board, e.g. 'TQBR'.",
      "default": "TQBR"
    }
  },
  "required": ["ticker"],
  "additionalProperties": false
}
```

#### Output JSON Schema

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "GetSecuritySnapshotOutput",
  "type": "object",
  "properties": {
    "metadata": {
      "type": "object",
      "properties": {
        "source": { "type": "string", "enum": ["moex-iss"] },
        "ticker": { "type": "string" },
        "board": { "type": "string" },
        "as_of": { "type": "string", "format": "date-time" }
      },
      "required": ["source", "ticker", "board", "as_of"],
      "additionalProperties": false
    },
    "data": {
      "type": "object",
      "properties": {
        "last_price": { "type": "number" },
        "price_change_abs": { "type": "number" },
        "price_change_pct": { "type": "number" },
        "open_price": { "type": "number" },
        "high_price": { "type": "number" },
        "low_price": { "type": "number" },
        "volume": { "type": "number" },
        "value": { "type": "number" }
      },
      "required": [
        "last_price",
        "price_change_abs",
        "price_change_pct"
      ],
      "additionalProperties": true
    },
    "metrics": {
      "type": "object",
      "properties": {
        "intraday_volatility_estimate": { "type": "number" }
      },
      "required": [],
      "additionalProperties": true
    },
    "error": {
      "type": ["null", "object"],
      "properties": {
        "error_type": { "type": "string" },
        "message": { "type": "string" },
        "details": {}
      },
      "required": ["error_type", "message"],
      "additionalProperties": true
    }
  },
  "required": ["metadata", "data"],
  "additionalProperties": false
}
```

---

### 2.2. Tool: `get_ohlcv_timeseries`

**Назначение:** получение исторических OHLCV-данных по инструменту за период, с базовыми метриками.

#### Input JSON Schema

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "GetOhlcvTimeseriesInput",
  "type": "object",
  "properties": {
    "ticker": {
      "type": "string",
      "minLength": 1,
      "maxLength": 16,
      "description": "Security ticker, e.g. 'SBER'."
    },
    "board": {
      "type": "string",
      "minLength": 1,
      "maxLength": 16,
      "description": "MOEX board, e.g. 'TQBR'.",
      "default": "TQBR"
    },
    "from_date": {
      "type": "string",
      "format": "date",
      "description": "Start date, inclusive, in ISO format (YYYY-MM-DD)."
    },
    "to_date": {
      "type": "string",
      "format": "date",
      "description": "End date, inclusive, in ISO format (YYYY-MM-DD)."
    },
    "interval": {
      "type": "string",
      "enum": ["1d", "1h"],
      "description": "Aggregation interval: 1d (daily) or 1h (hourly).",
      "default": "1d"
    }
  },
  "required": ["ticker", "from_date", "to_date"],
  "additionalProperties": false
}
```

*(валидация `to_date >= from_date` реализуется на уровне Pydantic, вне JSON Schema)*

#### Output JSON Schema

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "GetOhlcvTimeseriesOutput",
  "type": "object",
  "properties": {
    "metadata": {
      "type": "object",
      "properties": {
        "source": { "type": "string", "enum": ["moex-iss"] },
        "ticker": { "type": "string" },
        "board": { "type": "string" },
        "interval": { "type": "string", "enum": ["1d", "1h"] },
        "from_date": { "type": "string", "format": "date" },
        "to_date": { "type": "string", "format": "date" }
      },
      "required": ["source", "ticker", "interval", "from_date", "to_date"],
      "additionalProperties": false
    },
    "data": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "ts": { "type": "string", "format": "date-time" },
          "open": { "type": "number" },
          "high": { "type": "number" },
          "low": { "type": "number" },
          "close": { "type": "number" },
          "volume": { "type": "number" },
          "value": { "type": "number" }
        },
        "required": ["ts", "open", "high", "low", "close"],
        "additionalProperties": true
      }
    },
    "metrics": {
      "type": "object",
      "properties": {
        "total_return_pct": { "type": "number" },
        "annualized_volatility": { "type": "number" },
        "avg_daily_volume": { "type": "number" }
      },
      "required": [],
      "additionalProperties": true
    },
    "error": {
      "type": ["null", "object"],
      "properties": {
        "error_type": { "type": "string" },
        "message": { "type": "string" },
        "details": {}
      },
      "required": ["error_type", "message"],
      "additionalProperties": true
    }
  },
  "required": ["metadata", "data"],
  "additionalProperties": false
}
```

---

### 2.3. Tool: `get_index_constituents_metrics`

**Назначение:** состав индекса и базовые показатели по бумагам.

#### Input JSON Schema

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "GetIndexConstituentsMetricsInput",
  "type": "object",
  "properties": {
    "index_ticker": {
      "type": "string",
      "enum": ["IMOEX", "RTSI"],
      "description": "Index ticker."
    },
    "as_of_date": {
      "type": "string",
      "format": "date",
      "description": "Date for which index composition is requested."
    }
  },
  "required": ["index_ticker", "as_of_date"],
  "additionalProperties": false
}
```

#### Output JSON Schema

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "GetIndexConstituentsMetricsOutput",
  "type": "object",
  "properties": {
    "metadata": {
      "type": "object",
      "properties": {
        "source": { "type": "string", "enum": ["moex-iss"] },
        "index_ticker": { "type": "string" },
        "as_of_date": { "type": "string", "format": "date" }
      },
      "required": ["source", "index_ticker", "as_of_date"],
      "additionalProperties": false
    },
    "data": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "ticker": { "type": "string" },
          "weight_pct": { "type": "number" },
          "last_price": { "type": "number" },
          "price_change_pct": { "type": "number" },
          "sector": { "type": "string" }
        },
        "required": ["ticker", "weight_pct"],
        "additionalProperties": true
      }
    },
    "metrics": {
      "type": "object",
      "properties": {
        "top5_weight_pct": { "type": "number" },
        "num_constituents": { "type": "integer" }
      },
      "required": [],
      "additionalProperties": true
    },
    "error": {
      "type": ["null", "object"],
      "properties": {
        "error_type": { "type": "string" },
        "message": { "type": "string" },
        "details": {}
      },
      "required": ["error_type", "message"],
      "additionalProperties": true
    }
  },
  "required": ["metadata", "data"],
  "additionalProperties": false
}
```

---

## 3. Пример `tools.json`

Формат `tools.json` может быть адаптирован под требования Evolution AI Agents. Внутри репозитория используется следующий формат (упрощённый):

```json
{
  "tools": [
    {
      "name": "get_security_snapshot",
      "description": "Get a short snapshot for a MOEX security (last price, change, liquidity).",
      "input_schema": { "$ref": "./schemas/get_security_snapshot_input.json" },
      "output_schema": { "$ref": "./schemas/get_security_snapshot_output.json" }
    },
    {
      "name": "get_ohlcv_timeseries",
      "description": "Get historical OHLCV data and basic metrics for a MOEX security.",
      "input_schema": { "$ref": "./schemas/get_ohlcv_timeseries_input.json" },
      "output_schema": { "$ref": "./schemas/get_ohlcv_timeseries_output.json" }
    },
    {
      "name": "get_index_constituents_metrics",
      "description": "Get index composition and per-constituent metrics.",
      "input_schema": { "$ref": "./schemas/get_index_constituents_metrics_input.json" },
      "output_schema": { "$ref": "./schemas/get_index_constituents_metrics_output.json" }
    }
  ]
}
```

> Примечание: при интеграции в Evolution AI Agents необходимо свериться с актуальным форматом описания MCP-инструментов в документации Cloud.ru и при необходимости добавить поля (например, `mcpServerId`, `version` и т.п.).

---

## 4. A2A JSON Schema (агент)

### 4.1. Вход агента (Request)

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "MoexMarketAnalystAgentInput",
  "type": "object",
  "properties": {
    "input": {
      "type": "object",
      "properties": {
        "messages": {
          "type": "array",
          "items": {
            "type": "object",
            "properties": {
              "role": {
                "type": "string",
                "enum": ["system", "user", "assistant"]
              },
              "content": {
                "type": "string"
              }
            },
            "required": ["role", "content"],
            "additionalProperties": false
          }
        },
        "metadata": {
          "type": "object",
          "properties": {
            "locale": { "type": "string" },
            "user_role": { "type": "string" }
          },
          "required": [],
          "additionalProperties": true
        }
      },
      "required": ["messages"],
      "additionalProperties": true
    }
  },
  "required": ["input"],
  "additionalProperties": false
}
```

### 4.2. Ответ агента (Response)

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "MoexMarketAnalystAgentOutput",
  "type": "object",
  "properties": {
    "output": {
      "type": "object",
      "properties": {
        "text": {
          "type": "string",
          "description": "Final human-readable summary in Russian."
        },
        "tables": {
          "type": "array",
          "items": {
            "type": "object",
            "properties": {
              "title": { "type": "string" },
              "columns": {
                "type": "array",
                "items": { "type": "string" }
              },
              "rows": {
                "type": "array",
                "items": {
                  "type": "array",
                  "items": {}
                }
              }
            },
            "required": ["columns", "rows"],
            "additionalProperties": false
          }
        },
        "debug": {
          "type": ["null", "object"],
          "properties": {
            "plan": {
              "type": "array",
              "items": { "type": "string" }
            },
            "tool_calls": {
              "type": "array",
              "items": {
                "type": "object",
                "properties": {
                  "tool": { "type": "string" },
                  "args": { "type": "object" }
                },
                "required": ["tool", "args"],
                "additionalProperties": true
              }
            }
          },
          "required": [],
          "additionalProperties": true
        }
      },
      "required": ["text"],
      "additionalProperties": false
    }
  },
  "required": ["output"],
  "additionalProperties": false
}
```
