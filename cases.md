Давайте сначала изучу структуру вашего проекта, чтобы составить релевантные E2E тест-кейсы для ваших MCP-серверов.

[12 tools called]

Теперь у меня есть полное понимание вашего проекта. Вот подробные E2E тест-кейсы для проверки ваших MCP-серверов:

---

# E2E Тест-кейсы для MCP-серверов MOEX

## 🔧 Предусловия (для всех тестов)

### Установка зависимостей

```bash
cd /Users/Admin/CursorProject/MOEX-Agent-MCP
uv sync
```

### Запуск серверов

**Вариант A: Локальный запуск**

```bash
# Терминал 1 — moex-iss-mcp (порт 8000)
uv run python -m moex_iss_mcp.main

# Терминал 2 — risk-analytics-mcp (порт 8010)
uv run python -m risk_analytics_mcp.main
```

**Вариант B: Docker**

```bash
# moex-iss-mcp
cd moex_iss_mcp && docker-compose up --build -d

# risk-analytics-mcp
cd risk_analytics_mcp && docker-compose up --build -d
```

### Важно: Парсинг SSE-ответов

MCP-серверы используют Streamable HTTP транспорт и возвращают ответы в формате **Server-Sent Events (SSE)**. Для извлечения JSON-результата используйте:

```bash
# Хелпер-функция для парсинга SSE (добавить в .bashrc или выполнить перед тестами)
parse_sse() {
  grep '^data:' | tail -1 | sed 's/^data: //'
}

# Пример использования:
curl -s -X POST http://localhost:8000/mcp ... | parse_sse | jq .
```

Или однострочник:

```bash
curl ... | grep '^data:' | tail -1 | sed 's/^data: //' | jq .
```

---

## 📗 Тест-кейс 1: Health Check обоих серверов

**Цель:** Проверить что оба MCP-сервера запущены и отвечают на health-эндпоинт.

### Предусловия

- Оба сервера запущены

### Шаги

```bash
# 1. Проверка moex-iss-mcp
curl -s http://localhost:8000/health | jq .

# 2. Проверка risk-analytics-mcp
curl -s http://localhost:8010/health | jq .
```

### Ожидаемый результат

```json
{ "status": "ok" }
```

---

## 📗 Тест-кейс 2: Получение снимка инструмента (get_security_snapshot)

**Цель:** Проверить получение актуальных данных по бумаге SBER через MCP-протокол.

### Предусловия

- `moex-iss-mcp` запущен на порту 8000
- Доступ к интернету (для запросов к MOEX ISS API)

### Шаги

```bash
curl -s -X POST http://localhost:8000/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{
    "jsonrpc": "2.0",
    "id": "test-snapshot-1",
    "method": "tools/call",
    "params": {
      "name": "get_security_snapshot",
      "arguments": {
        "ticker": "SBER",
        "board": "TQBR"
      }
    }
  }' | grep '^data:' | tail -1 | sed 's/^data: //' | jq .
```

export MCP_URL=http://localhost:8000/mcp

# snapshot PIKK
curl -s "$MCP_URL" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json" \
  -d '{"jsonrpc":"2.0","id":"1","method":"tools/call","params":{"name":"get_security_snapshot","arguments":{"ticker":"PIKK","board":"TQBR"}}}'

### Ожидаемый результат

```json
{
  "jsonrpc": "2.0",
  "id": "test-snapshot-1",
  "result": {
    "structuredContent": {
      "error": null,
      "data": {
        "last_price": <number>,
        "price_change_abs": <number>,
        "price_change_pct": <number>,
        "open_price": <number>,
        "high_price": <number>,
        "low_price": <number>,
        "volume": <number>,
        "value": <number>
      },
      "metadata": {
        "source": "moex-iss",
        "ticker": "SBER",
        "board": "TQBR",
        "as_of": "<ISO datetime>"
      },
      "metrics": {
        "intraday_volatility_estimate": <number>
      }
    }
  }
}
```

### Проверки

- `error` должен быть `null`
- `data.last_price` — положительное число
- `metadata.source` равен `"moex-iss"`
- `metadata.ticker` равен `"SBER"`
- `metrics.intraday_volatility_estimate` — число

---

## 📗 Тест-кейс 3: Получение OHLCV данных (get_ohlcv_timeseries)

**Цель:** Проверить получение исторических свечей с расчётом метрик.

### Предусловия

- `moex-iss-mcp` запущен

### Шаги

```bash
curl -s -X POST http://localhost:8000/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{
    "jsonrpc": "2.0",
    "id": "test-ohlcv-1",
    "method": "tools/call",
    "params": {
      "name": "get_ohlcv_timeseries",
      "arguments": {
        "ticker": "GAZP",
        "board": "TQBR",
        "from_date": "2024-11-01",
        "to_date": "2024-11-30",
        "interval": "1d"
      }
    }
  }' | grep '^data:' | tail -1 | sed 's/^data: //' | jq .
```

### Ожидаемый результат

```json
{
  "jsonrpc": "2.0",
  "id": "test-ohlcv-1",
  "result": {
    "structuredContent": {
      "error": null,
      "data": [
        {
          "ts": "<ISO datetime>",
          "open": <number>,
          "high": <number>,
          "low": <number>,
          "close": <number>,
          "volume": <number>,
          "value": <number>
        }
        // ... ещё свечи
      ],
      "metadata": {
        "source": "moex-iss",
        "ticker": "GAZP",
        "board": "TQBR",
        "from_date": "2024-11-01",
        "to_date": "2024-11-30",
        "interval": "1d"
      },
      "metrics": {
        "total_return_pct": <number>,
        "annualized_volatility": <number>,
        "avg_daily_volume": <number>
      }
    }
  }
}
```

### Проверки

- `data` — массив с торговыми днями (~20-22 свечи)
- `metrics.total_return_pct` — число (может быть отрицательным)
- `metrics.annualized_volatility` > 0
- Каждая свеча имеет `open`, `high`, `low`, `close`, `volume`

---

## 📗 Тест-кейс 4: Получение состава индекса IMOEX

**Цель:** Проверить получение компонентов индекса Мосбиржи.

### Предусловия

- `moex-iss-mcp` запущен

### Шаги

```bash
curl -s -X POST http://localhost:8000/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{
    "jsonrpc": "2.0",
    "id": "test-index-1",
    "method": "tools/call",
    "params": {
      "name": "get_index_constituents_metrics",
      "arguments": {
        "index_ticker": "IMOEX",
        "as_of_date": "2024-12-10"
      }
    }
  }' | grep '^data:' | tail -1 | sed 's/^data: //' | jq .
```

### Ожидаемый результат

```json
{
  "jsonrpc": "2.0",
  "id": "test-index-1",
  "result": {
    "structuredContent": {
      "error": null,
      "data": [
        {
          "ticker": "GAZP",
          "weight_pct": 11.14
        },
        {
          "ticker": "LKOH",
          "weight_pct": 17.88
        }
        // ... другие компоненты
      ],
      "metadata": {
        "source": "moex-iss",
        "index_ticker": "IMOEX",
        "as_of_date": "2024-12-10"
      },
      "metrics": {
        "top5_weight_pct": <number>,
        "num_constituents": <number>
      }
    }
  }
}
```

### Проверки

- `data` — массив компонентов индекса
- `data[].ticker` и `data[].weight_pct` — обязательные поля
- `metrics.num_constituents` — количество бумаг в индексе
- `metrics.top5_weight_pct` — суммарный вес топ-5 бумаг
- Присутствуют крупные тикеры: LKOH, GAZP, GMKN, SBER

---

## 📗 Тест-кейс 5: Базовый риск портфеля (compute_portfolio_risk_basic)

**Цель:** Проверить расчёт метрик риска для простого портфеля.

### Предусловия

- `risk-analytics-mcp` запущен на порту 8010
- Доступ к интернету (данные загружаются из MOEX)

### Шаги

```bash
curl -s -X POST http://localhost:8010/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{
    "jsonrpc": "2.0",
    "id": "test-risk-1",
    "method": "tools/call",
    "params": {
      "name": "compute_portfolio_risk_basic",
      "arguments": {
        "positions": [
          {"ticker": "SBER", "weight": 0.5},
          {"ticker": "GAZP", "weight": 0.3},
          {"ticker": "LKOH", "weight": 0.2}
        ],
        "from_date": "2024-09-01",
        "to_date": "2024-11-30",
        "rebalance": "buy_and_hold"
      }
    }
  }' | grep '^data:' | tail -1 | sed 's/^data: //' | jq .
```

### Ожидаемый результат

```json
{
  "jsonrpc": "2.0",
  "id": "test-risk-1",
  "result": {
    "structuredContent": {
      "error": null,
      "metadata": {
        "as_of": "<ISO datetime>",
        "from_date": "2024-09-01",
        "to_date": "2024-11-30",
        "rebalance": "buy_and_hold",
        "tickers": ["SBER", "GAZP", "LKOH"],
        "iss_base_url": "https://iss.moex.com/iss/",
        "stress_scenarios": ["equity_-10_fx_+20", "rates_+300bp", "credit_spreads_+150bp"],
        "var_light_params": {"confidence_level": 0.95, "horizon_days": 1}
      },
      "data": {
        "per_instrument": [
          {
            "ticker": "SBER",
            "weight": 0.5,
            "total_return_pct": <number>,
            "annualized_volatility_pct": <number>,
            "max_drawdown_pct": <number>
          }
          // ... GAZP, LKOH
        ],
        "portfolio_metrics": {
          "total_return_pct": <number>,
          "annualized_volatility_pct": <number>,
          "max_drawdown_pct": <number>
        },
        "concentration_metrics": {
          "top1_weight_pct": 50.0,
          "top3_weight_pct": 100.0,
          "top5_weight_pct": 100.0,
          "hhi": <number>
        },
        "stress_results": [
          {
            "id": "equity_-10_fx_+20",
            "description": "Падение акций на 10% и ослабление базовой валюты на 20%.",
            "pnl_pct": -10.0,
            "drivers": {...}
          }
        ],
        "var_light": {
          "method": "parametric_normal",
          "confidence_level": 0.95,
          "horizon_days": 1,
          "annualized_volatility_pct": <number>,
          "var_pct": <number>
        }
      }
    }
  }
}
```

### Проверки

- `error` равен `null`
- `data.per_instrument` содержит 3 элемента
- `data.per_instrument[].weight` — число от 0 до 1 (не проценты!)
- `data.portfolio_metrics.total_return_pct` — число
- `data.concentration_metrics.hhi` — индекс Херфиндаля (0..1)
- `data.stress_results` — массив из 3 сценариев по умолчанию
- `data.var_light.var_pct` — положительное число (% потерь)

---

## 📗 Тест-кейс 6: Портфельный риск со стресс-сценариями и VaR

**Цель:** Проверить расширенный расчёт с явными стресс-сценариями и VaR.

### Предусловия

- `risk-analytics-mcp` запущен

### Шаги

```bash
curl -s -X POST http://localhost:8010/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{
    "jsonrpc": "2.0",
    "id": "test-stress-1",
    "method": "tools/call",
    "params": {
      "name": "compute_portfolio_risk_basic",
      "arguments": {
        "positions": [
          {"ticker": "SBER", "weight": 0.6},
          {"ticker": "VTBR", "weight": 0.4}
        ],
        "from_date": "2024-10-01",
        "to_date": "2024-11-30",
        "rebalance": "buy_and_hold",
        "aggregates": {
          "asset_class_weights": {"equity": 1.0},
          "fx_exposure_weights": {"RUB": 0.8, "USD": 0.2}
        },
        "stress_scenarios": ["equity_-10_fx_+20", "rates_+300bp"],
        "var_config": {
          "confidence_level": 0.95,
          "horizon_days": 1
        }
      }
    }
  }' | grep '^data:' | tail -1 | sed 's/^data: //' | jq .
```

### Ожидаемый результат

```json
{
  "result": {
    "structuredContent": {
      "error": null,
      "metadata": {...},
      "data": {
        "per_instrument": [...],
        "portfolio_metrics": {...},
        "concentration_metrics": {...},
        "stress_results": [
          {
            "id": "equity_-10_fx_+20",
            "description": "Падение акций на 10% и ослабление базовой валюты на 20%.",
            "pnl_pct": <number>,
            "drivers": {
              "equity_weight_pct": 100.0,
              "fx_exposed_weight_pct": <number>,
              "equity_shock_pct": -10.0,
              "fx_shock_pct": 20.0
            }
          },
          {
            "id": "rates_+300bp",
            "description": "Рост ставок на 300 bps с учётом дюрации долгового портфеля.",
            "pnl_pct": <number>,
            "drivers": {...}
          }
        ],
        "var_light": {
          "method": "parametric_normal",
          "confidence_level": 0.95,
          "horizon_days": 1,
          "annualized_volatility_pct": <number>,
          "var_pct": <number>
        }
      }
    }
  }
}
```

### Проверки

- `data.stress_results` содержит ровно 2 запрошенных сценария
- `data.stress_results[].description` — человекочитаемое описание на русском
- `data.var_light.var_pct` — положительное число (% потерь при заданном уровне доверия)
- `data.var_light.annualized_volatility_pct` — положительное число

---

## 📗 Тест-кейс 7: Матрица корреляций (compute_correlation_matrix)

**Цель:** Проверить расчёт корреляционной матрицы доходностей.

### Предусловия

- `risk-analytics-mcp` запущен

### Шаги

```bash
curl -s -X POST http://localhost:8010/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{
    "jsonrpc": "2.0",
    "id": "test-corr-1",
    "method": "tools/call",
    "params": {
      "name": "compute_correlation_matrix",
      "arguments": {
        "tickers": ["SBER", "GAZP", "LKOH", "YNDX"],
        "from_date": "2024-06-01",
        "to_date": "2024-11-30"
      }
    }
  }' | grep '^data:' | tail -1 | sed 's/^data: //' | jq .
```

### Ожидаемый результат

```json
{
  "result": {
    "structuredContent": {
      "error": null,
      "metadata": {
        "from_date": "2024-06-01",
        "to_date": "2024-11-30",
        "tickers": ["SBER", "GAZP", "LKOH", "YNDX"],
        "method": "pearson",
        "num_observations": <number>
      },
      "data": {
        "tickers": ["SBER", "GAZP", "LKOH", "YNDX"],
        "matrix": [
          [1.0, <corr>, <corr>, <corr>],
          [<corr>, 1.0, <corr>, <corr>],
          [<corr>, <corr>, 1.0, <corr>],
          [<corr>, <corr>, <corr>, 1.0]
        ]
      }
    }
  }
}
```

### Проверки

- `data.tickers` — массив из 4 тикеров
- `data.matrix` — квадратная матрица 4×4
- Диагональ матрицы = 1.0 (корреляция с собой)
- Матрица симметричная: `matrix[i][j] == matrix[j][i]`
- Все значения в диапазоне [-1, 1]
- `metadata.num_observations` > 0

---

## 📕 Тест-кейс 8: Обработка ошибки — невалидный тикер

**Цель:** Проверить корректную обработку ошибки для несуществующего тикера.

### Предусловия

- `moex-iss-mcp` запущен

### Шаги

```bash
curl -s -X POST http://localhost:8000/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{
    "jsonrpc": "2.0",
    "id": "test-invalid-ticker",
    "method": "tools/call",
    "params": {
      "name": "get_security_snapshot",
      "arguments": {
        "ticker": "XXXXXX",
        "board": "TQBR"
      }
    }
  }' | grep '^data:' | tail -1 | sed 's/^data: //' | jq .
```

### Ожидаемый результат

```json
{
  "result": {
    "structuredContent": {
      "error": {
        "error_type": "INVALID_TICKER",
        "message": "...",
        "details": {...}
      },
      "data": null,
      "metadata": {}
    }
  }
}
```

### Проверки

- `error.error_type` == `"INVALID_TICKER"`
- HTTP статус 200 (ошибка обработана внутри MCP)

> **Примечание:** Тикер должен быть ≤16 символов, иначе сработает `VALIDATION_ERROR`

---

## 📕 Тест-кейс 9: Обработка ошибки — слишком большой диапазон дат

**Цель:** Проверить валидацию лимитов на диапазон дат.

### Предусловия

- `risk-analytics-mcp` запущен с лимитом `RISK_MAX_LOOKBACK_DAYS=365`

### Шаги

```bash
curl -s -X POST http://localhost:8010/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{
    "jsonrpc": "2.0",
    "id": "test-date-range",
    "method": "tools/call",
    "params": {
      "name": "compute_portfolio_risk_basic",
      "arguments": {
        "positions": [{"ticker": "SBER", "weight": 1.0}],
        "from_date": "2020-01-01",
        "to_date": "2024-12-01"
      }
    }
  }' | grep '^data:' | tail -1 | sed 's/^data: //' | jq .
```

### Ожидаемый результат

```json
{
  "result": {
    "structuredContent": {
      "error": {
        "error_type": "DATE_RANGE_TOO_LARGE",
        "message": "..."
      },
      "data": null
    }
  }
}
```

---

## 📕 Тест-кейс 10: Обработка ошибки — слишком много тикеров

**Цель:** Проверить лимит на количество тикеров в портфеле.

### Предусловия

- `risk-analytics-mcp` запущен с дефолтным `RISK_MAX_PORTFOLIO_TICKERS=50`

### Шаги

```bash
# Генерируем запрос с 51 тикером (лимит = 50)
# Веса: 50 × 0.0196 + 1 × 0.02 = 1.0
curl -s -X POST http://localhost:8010/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{
    "jsonrpc": "2.0",
    "id": "test-too-many",
    "method": "tools/call",
    "params": {
      "name": "compute_portfolio_risk_basic",
      "arguments": {
        "positions": [
          {"ticker": "T01", "weight": 0.0196}, {"ticker": "T02", "weight": 0.0196},
          {"ticker": "T03", "weight": 0.0196}, {"ticker": "T04", "weight": 0.0196},
          {"ticker": "T05", "weight": 0.0196}, {"ticker": "T06", "weight": 0.0196},
          {"ticker": "T07", "weight": 0.0196}, {"ticker": "T08", "weight": 0.0196},
          {"ticker": "T09", "weight": 0.0196}, {"ticker": "T10", "weight": 0.0196},
          {"ticker": "T11", "weight": 0.0196}, {"ticker": "T12", "weight": 0.0196},
          {"ticker": "T13", "weight": 0.0196}, {"ticker": "T14", "weight": 0.0196},
          {"ticker": "T15", "weight": 0.0196}, {"ticker": "T16", "weight": 0.0196},
          {"ticker": "T17", "weight": 0.0196}, {"ticker": "T18", "weight": 0.0196},
          {"ticker": "T19", "weight": 0.0196}, {"ticker": "T20", "weight": 0.0196},
          {"ticker": "T21", "weight": 0.0196}, {"ticker": "T22", "weight": 0.0196},
          {"ticker": "T23", "weight": 0.0196}, {"ticker": "T24", "weight": 0.0196},
          {"ticker": "T25", "weight": 0.0196}, {"ticker": "T26", "weight": 0.0196},
          {"ticker": "T27", "weight": 0.0196}, {"ticker": "T28", "weight": 0.0196},
          {"ticker": "T29", "weight": 0.0196}, {"ticker": "T30", "weight": 0.0196},
          {"ticker": "T31", "weight": 0.0196}, {"ticker": "T32", "weight": 0.0196},
          {"ticker": "T33", "weight": 0.0196}, {"ticker": "T34", "weight": 0.0196},
          {"ticker": "T35", "weight": 0.0196}, {"ticker": "T36", "weight": 0.0196},
          {"ticker": "T37", "weight": 0.0196}, {"ticker": "T38", "weight": 0.0196},
          {"ticker": "T39", "weight": 0.0196}, {"ticker": "T40", "weight": 0.0196},
          {"ticker": "T41", "weight": 0.0196}, {"ticker": "T42", "weight": 0.0196},
          {"ticker": "T43", "weight": 0.0196}, {"ticker": "T44", "weight": 0.0196},
          {"ticker": "T45", "weight": 0.0196}, {"ticker": "T46", "weight": 0.0196},
          {"ticker": "T47", "weight": 0.0196}, {"ticker": "T48", "weight": 0.0196},
          {"ticker": "T49", "weight": 0.0196}, {"ticker": "T50", "weight": 0.0196},
          {"ticker": "T51", "weight": 0.02}
        ],
        "from_date": "2024-11-01",
        "to_date": "2024-11-30"
      }
    }
  }' | grep '^data:' | tail -1 | sed 's/^data: //' | jq '.result.structuredContent.error'
```

### Ожидаемый результат

```json
{
  "error_type": "TOO_MANY_TICKERS",
  "message": "..."
}
```

---

## 📗 Тест-кейс 11: MCP-протокол — инициализация и вызов инструмента

**Цель:** Проверить полный flow MCP-протокола: инициализация + вызов инструмента.

### Предусловия

- `risk-analytics-mcp` запущен

> **Примечание:** Сервер работает в `stateless_http=True` режиме, поэтому `mcp-session-id` не используется. Каждый запрос независим.

### Шаги

```bash
# Шаг 1: Инициализация MCP-протокола
curl -s -X POST http://localhost:8010/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -D - \
  -d '{
    "jsonrpc": "2.0",
    "id": "init-1",
    "method": "initialize",
    "params": {
      "protocolVersion": "2024-11-05",
      "clientInfo": {"name": "curl-test", "version": "1.0"},
      "capabilities": {}
    }
  }' 2>&1 | grep -E "(mcp-session-id|protocolVersion|serverInfo)"

# Шаг 2: Вызов инструмента (без session ID — stateless режим)
curl -s -X POST http://localhost:8010/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{
    "jsonrpc": "2.0",
    "id": "call-1",
    "method": "tools/call",
    "params": {
      "name": "compute_correlation_matrix",
      "arguments": {
        "tickers": ["SBER", "GAZP"],
        "from_date": "2024-10-01",
        "to_date": "2024-11-30"
      }
    }
  }' | grep '^data:' | tail -1 | sed 's/^data: //' | jq '.result.structuredContent.data'
```

### Ожидаемый результат

**Шаг 1:** Успешная инициализация с информацией о сервере:

```json
{
  "protocolVersion": "2024-11-05",
  "serverInfo": {
    "name": "risk-analytics-mcp",
    "version": "..."
  }
}
```

**Шаг 2:** Успешный ответ с матрицей корреляций:

```json
{
  "tickers": ["SBER", "GAZP"],
  "matrix": [[1.0, <corr>], [<corr>, 1.0]]
}
```

---

## 📗 Тест-кейс 12: Prometheus метрики

**Цель:** Проверить экспорт метрик после вызовов инструментов.

### Предусловия

- Серверы запущены с `ENABLE_MONITORING=true`

### Шаги

```bash
# 1. Запустить сервер с мониторингом
ENABLE_MONITORING=true uv run python -m moex_iss_mcp.main &

# 2. Сделать несколько вызовов
curl -s -X POST http://localhost:8000/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{"jsonrpc":"2.0","id":"1","method":"tools/call","params":{"name":"get_security_snapshot","arguments":{"ticker":"SBER"}}}' > /dev/null

# 3. Проверить метрики
curl -s http://localhost:8000/metrics | grep -E "(tool_calls_total|tool_errors_total|moex_iss_mcp_up)"
```

### Ожидаемый результат

```
# HELP moex_iss_mcp_up Server up indicator
# TYPE moex_iss_mcp_up gauge
moex_iss_mcp_up 1.0
# HELP tool_calls_total Total number of tool calls
# TYPE tool_calls_total counter
tool_calls_total{tool="get_security_snapshot"} 1.0
```

---

## 📗 Тест-кейс 13: Сквозной сценарий — анализ портфеля

**Цель:** Полный E2E сценарий: получить данные, рассчитать риск, построить корреляции.

### Предусловия

- Оба сервера запущены

### Шаги

```bash
# Шаг 1: Получить состав индекса IMOEX (top-5 бумаг для портфеля)
echo "=== Шаг 1: Состав IMOEX ==="
curl -s -X POST http://localhost:8000/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{"jsonrpc":"2.0","id":"1","method":"tools/call","params":{"name":"get_index_constituents_metrics","arguments":{"index_ticker":"IMOEX","as_of_date":"2024-12-10"}}}' \
  | grep '^data:' | tail -1 | sed 's/^data: //' | jq '.result.structuredContent.data[:5] | .[].ticker'

# Шаг 2: Получить OHLCV для SBER
echo "=== Шаг 2: OHLCV SBER ==="
curl -s -X POST http://localhost:8000/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{"jsonrpc":"2.0","id":"2","method":"tools/call","params":{"name":"get_ohlcv_timeseries","arguments":{"ticker":"SBER","from_date":"2024-11-01","to_date":"2024-11-30"}}}' \
  | grep '^data:' | tail -1 | sed 's/^data: //' | jq '.result.structuredContent.metrics'

# Шаг 3: Рассчитать риск портфеля из top-3 бумаг
echo "=== Шаг 3: Портфельный риск ==="
curl -s -X POST http://localhost:8010/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{
    "jsonrpc":"2.0","id":"3","method":"tools/call",
    "params":{"name":"compute_portfolio_risk_basic","arguments":{
      "positions":[
        {"ticker":"SBER","weight":0.4},
        {"ticker":"GAZP","weight":0.3},
        {"ticker":"LKOH","weight":0.3}
      ],
      "from_date":"2024-11-01",
      "to_date":"2024-11-30"
    }}}' \
  | grep '^data:' | tail -1 | sed 's/^data: //' | jq '.result.structuredContent.data.portfolio_metrics'

# Шаг 4: Построить корреляционную матрицу
echo "=== Шаг 4: Корреляционная матрица ==="
curl -s -X POST http://localhost:8010/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{
    "jsonrpc":"2.0","id":"4","method":"tools/call",
    "params":{"name":"compute_correlation_matrix","arguments":{
      "tickers":["SBER","GAZP","LKOH"],
      "from_date":"2024-11-01",
      "to_date":"2024-11-30"
    }}}' \
  | grep '^data:' | tail -1 | sed 's/^data: //' | jq '.result.structuredContent.data'
```

### Ожидаемый результат

- **Шаг 1:** Список из 5 тикеров индекса IMOEX (например: `"SBER"`, `"GAZP"`, `"LKOH"`, `"YNDX"`, `"GMKN"`)
- **Шаг 2:** Метрики OHLCV:

```json
{
  "total_return_pct": <number>,
  "annualized_volatility": <number>,
  "avg_daily_volume": <number>
}
```

- **Шаг 3:** Портфельные метрики:

```json
{
  "total_return_pct": <number>,
  "annualized_volatility_pct": <number>,
  "max_drawdown_pct": <number>
}
```

- **Шаг 4:** Корреляционная матрица 3×3:

```json
{
  "tickers": ["SBER", "GAZP", "LKOH"],
  "matrix": [
    [1.0, <corr>, <corr>],
    [<corr>, 1.0, <corr>],
    [<corr>, <corr>, 1.0]
  ]
}
```
