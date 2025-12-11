# E2E Сценарии для suggest_rebalance (curl)

## Подготовка

Запустите MCP-сервер:

```bash
cd /Users/Admin/CursorProject/MOEX-Agent-MCP
python -m risk_analytics_mcp.main
```

Сервер будет доступен на `http://localhost:8010`

> **Важно:** FastMCP возвращает Server-Sent Events (SSE). 
> Результат находится в последней строке `data:` — используем `grep` + `tail` для извлечения.

---

## Проверка работоспособности

### Health check

```bash
curl -s http://localhost:8010/health | jq
```

Ожидаемый ответ:
```json
{"status": "ok"}
```

---

## Сценарий 1: Снижение концентрации в одной акции

**Ситуация:** SBER занимает 45% портфеля, лимит — 25%

```bash
curl -s -X POST http://localhost:8010/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{
    "jsonrpc": "2.0",
    "method": "tools/call",
    "params": {
      "name": "suggest_rebalance",
      "arguments": {
        "positions": [
          {"ticker": "SBER", "current_weight": 0.45, "asset_class": "equity"},
          {"ticker": "GAZP", "current_weight": 0.20, "asset_class": "equity"},
          {"ticker": "LKOH", "current_weight": 0.15, "asset_class": "equity"},
          {"ticker": "ROSN", "current_weight": 0.10, "asset_class": "equity"},
          {"ticker": "GMKN", "current_weight": 0.10, "asset_class": "equity"}
        ],
        "total_portfolio_value": 10000000,
        "risk_profile": {
          "max_single_position_weight": 0.25,
          "max_turnover": 0.30
        }
      }
    },
    "id": 1
  }' | grep '^data:' | tail -1 | sed 's/^data: //' | jq '.result.structuredContent.data'
```

**Ожидаемый результат:**
- SBER снижен до ~25%
- Есть сделка SELL SBER
- `concentration_issues_resolved` >= 1

---

## Сценарий 2: Концентрация по эмитенту (Сбербанк)

**Ситуация:** SBER + SBERP = 40%, лимит на эмитента — 25%

```bash
curl -s -X POST http://localhost:8010/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{
    "jsonrpc": "2.0",
    "method": "tools/call",
    "params": {
      "name": "suggest_rebalance",
      "arguments": {
        "positions": [
          {"ticker": "SBER", "current_weight": 0.25, "asset_class": "equity", "issuer": "SBERBANK"},
          {"ticker": "SBERP", "current_weight": 0.15, "asset_class": "equity", "issuer": "SBERBANK"},
          {"ticker": "GAZP", "current_weight": 0.20, "asset_class": "equity", "issuer": "GAZPROM"},
          {"ticker": "LKOH", "current_weight": 0.20, "asset_class": "equity", "issuer": "LUKOIL"},
          {"ticker": "ROSN", "current_weight": 0.20, "asset_class": "equity", "issuer": "ROSNEFT"}
        ],
        "total_portfolio_value": 5000000,
        "risk_profile": {
          "max_single_position_weight": 0.30,
          "max_issuer_weight": 0.25,
          "max_turnover": 0.30
        }
      }
    },
    "id": 2
  }' | grep '^data:' | tail -1 | sed 's/^data: //' | jq '.result.structuredContent.data'
```

**Ожидаемый результат:**
- Сумма SBER + SBERP <= 25%
- Есть сделки SELL для позиций Сбербанка

---

## Сценарий 3: Целевая аллокация 60/40

**Ситуация:** Акции 80%, облигации 20%. Цель: 60/40.

```bash
curl -s -X POST http://localhost:8010/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{
    "jsonrpc": "2.0",
    "method": "tools/call",
    "params": {
      "name": "suggest_rebalance",
      "arguments": {
        "positions": [
          {"ticker": "SBER", "current_weight": 0.30, "asset_class": "equity"},
          {"ticker": "GAZP", "current_weight": 0.30, "asset_class": "equity"},
          {"ticker": "LKOH", "current_weight": 0.20, "asset_class": "equity"},
          {"ticker": "OFZ26", "current_weight": 0.10, "asset_class": "fixed_income"},
          {"ticker": "OFZ29", "current_weight": 0.10, "asset_class": "fixed_income"}
        ],
        "total_portfolio_value": 10000000,
        "risk_profile": {
          "max_single_position_weight": 0.30,
          "max_equity_weight": 0.60,
          "max_turnover": 0.30,
          "target_asset_class_weights": {
            "equity": 0.60,
            "fixed_income": 0.40
          }
        }
      }
    },
    "id": 3
  }' | grep '^data:' | tail -1 | sed 's/^data: //' | jq '.result.structuredContent.data'
```

**Ожидаемый результат:**
- Доля акций снижена к 60%
- Доля облигаций увеличена к 40%
- `asset_class_issues_resolved` >= 1

---

## Сценарий 4: Консервативная ребалансировка (низкий оборот)

**Ситуация:** Инвестор хочет минимизировать издержки. Оборот: 5%.

```bash
curl -s -X POST http://localhost:8010/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{
    "jsonrpc": "2.0",
    "method": "tools/call",
    "params": {
      "name": "suggest_rebalance",
      "arguments": {
        "positions": [
          {"ticker": "SBER", "current_weight": 0.35, "asset_class": "equity"},
          {"ticker": "GAZP", "current_weight": 0.25, "asset_class": "equity"},
          {"ticker": "LKOH", "current_weight": 0.20, "asset_class": "equity"},
          {"ticker": "OFZ", "current_weight": 0.20, "asset_class": "fixed_income"}
        ],
        "total_portfolio_value": 3000000,
        "risk_profile": {
          "max_single_position_weight": 0.25,
          "max_turnover": 0.05
        }
      }
    },
    "id": 4
  }' | grep '^data:' | tail -1 | sed 's/^data: //' | jq '.result.structuredContent.data'
```

**Ожидаемый результат:**
- `total_turnover` <= 5%
- Есть `warnings` о неустранённых нарушениях

---

## Сценарий 5: Квартальная ребалансировка CFO

**Ситуация:** Большой портфель с разными классами активов.

```bash
curl -s -X POST http://localhost:8010/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{
    "jsonrpc": "2.0",
    "method": "tools/call",
    "params": {
      "name": "suggest_rebalance",
      "arguments": {
        "positions": [
          {"ticker": "SBER", "current_weight": 0.25, "asset_class": "equity"},
          {"ticker": "GAZP", "current_weight": 0.20, "asset_class": "equity"},
          {"ticker": "LKOH", "current_weight": 0.15, "asset_class": "equity"},
          {"ticker": "OFZ26", "current_weight": 0.15, "asset_class": "fixed_income"},
          {"ticker": "OFZ29", "current_weight": 0.10, "asset_class": "fixed_income"},
          {"ticker": "USDRUB", "current_weight": 0.10, "asset_class": "fx"},
          {"ticker": "MONEY", "current_weight": 0.05, "asset_class": "cash"}
        ],
        "total_portfolio_value": 50000000,
        "risk_profile": {
          "max_single_position_weight": 0.20,
          "max_equity_weight": 0.50,
          "max_fx_weight": 0.15,
          "max_turnover": 0.20,
          "target_asset_class_weights": {
            "equity": 0.45,
            "fixed_income": 0.35,
            "fx": 0.10,
            "cash": 0.10
          }
        }
      }
    },
    "id": 5
  }' | grep '^data:' | tail -1 | sed 's/^data: //' | jq '.result.structuredContent.data'
```

**Ожидаемый результат:**
- Оборот <= 20%
- Сделки с `estimated_value` в рублях

---

## Сценарий 6: Пенсионный фонд (жёсткие нормативы)

**Ситуация:** Не более 10% в одной акции, не более 40% в акциях.

```bash
curl -s -X POST http://localhost:8010/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{
    "jsonrpc": "2.0",
    "method": "tools/call",
    "params": {
      "name": "suggest_rebalance",
      "arguments": {
        "positions": [
          {"ticker": "SBER", "current_weight": 0.15, "asset_class": "equity"},
          {"ticker": "GAZP", "current_weight": 0.15, "asset_class": "equity"},
          {"ticker": "LKOH", "current_weight": 0.10, "asset_class": "equity"},
          {"ticker": "ROSN", "current_weight": 0.10, "asset_class": "equity"},
          {"ticker": "OFZ26", "current_weight": 0.20, "asset_class": "fixed_income"},
          {"ticker": "OFZ29", "current_weight": 0.20, "asset_class": "fixed_income"},
          {"ticker": "CORP", "current_weight": 0.10, "asset_class": "fixed_income"}
        ],
        "total_portfolio_value": 100000000,
        "risk_profile": {
          "max_single_position_weight": 0.10,
          "max_equity_weight": 0.40,
          "max_turnover": 0.15
        }
      }
    },
    "id": 6
  }' | grep '^data:' | tail -1 | sed 's/^data: //' | jq '.result.structuredContent.data'
```

**Ожидаемый результат:**
- Позиции стремятся к <= 10%
- Акции стремятся к <= 40%

---

## Сценарий 7: Небольшой портфель розничного инвестора

**Ситуация:** Начинающий инвестор с портфелем 10,000 ₽

```bash
curl -s -X POST http://localhost:8010/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{
    "jsonrpc": "2.0",
    "method": "tools/call",
    "params": {
      "name": "suggest_rebalance",
      "arguments": {
        "positions": [
          {"ticker": "SBER", "current_weight": 0.60, "asset_class": "equity"},
          {"ticker": "GAZP", "current_weight": 0.25, "asset_class": "equity"},
          {"ticker": "LKOH", "current_weight": 0.15, "asset_class": "equity"}
        ],
        "total_portfolio_value": 10000,
        "risk_profile": {
          "max_single_position_weight": 0.35,
          "max_turnover": 0.40
        }
      }
    },
    "id": 7
  }' | grep '^data:' | tail -1 | sed 's/^data: //' | jq '.result.structuredContent.data'
```

**Ожидаемый результат:**
- SBER снижен с 60% до ~35%
- Сделки в небольших суммах (сотни/тысячи рублей)

---

## Сценарии ошибок

### Пустой портфель

```bash
curl -s -X POST http://localhost:8010/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{
    "jsonrpc": "2.0",
    "method": "tools/call",
    "params": {
      "name": "suggest_rebalance",
      "arguments": {
        "positions": []
      }
    },
    "id": 100
  }' | grep '^data:' | tail -1 | sed 's/^data: //' | jq
```

**Ожидаемый результат:** Ошибка валидации

---

### Веса не суммируются к 1

```bash
curl -s -X POST http://localhost:8010/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{
    "jsonrpc": "2.0",
    "method": "tools/call",
    "params": {
      "name": "suggest_rebalance",
      "arguments": {
        "positions": [
          {"ticker": "SBER", "current_weight": 0.30, "asset_class": "equity"},
          {"ticker": "GAZP", "current_weight": 0.30, "asset_class": "equity"}
        ]
      }
    },
    "id": 101
  }' | grep '^data:' | tail -1 | sed 's/^data: //' | jq
```

**Ожидаемый результат:** Ошибка `VALIDATION_ERROR`

---

### Одна позиция с невыполнимым лимитом

```bash
curl -s -X POST http://localhost:8010/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{
    "jsonrpc": "2.0",
    "method": "tools/call",
    "params": {
      "name": "suggest_rebalance",
      "arguments": {
        "positions": [
          {"ticker": "SBER", "current_weight": 1.0, "asset_class": "equity"}
        ],
        "risk_profile": {
          "max_single_position_weight": 0.25
        }
      }
    },
    "id": 102
  }' | grep '^data:' | tail -1 | sed 's/^data: //' | jq '.result.structuredContent'
```

**Ожидаемый результат:** 
- `error: null` (best-effort)
- `warnings` с информацией о нарушениях
- `target_weights.SBER = 1.0` (некуда перераспределить)

---

## Полезные команды

### Базовая команда (извлечение JSON из SSE)

```bash
# Шаблон: добавьте в конец любого curl-запроса
| grep '^data:' | tail -1 | sed 's/^data: //' | jq
```

### Просмотр только целевых весов

```bash
... | grep '^data:' | tail -1 | sed 's/^data: //' | jq '.result.structuredContent.data.target_weights'
```

### Просмотр только сделок

```bash
... | grep '^data:' | tail -1 | sed 's/^data: //' | jq '.result.structuredContent.data.trades'
```

### Просмотр сводки

```bash
... | grep '^data:' | tail -1 | sed 's/^data: //' | jq '.result.structuredContent.data.summary'
```

### Форматированный вывод сделок

```bash
... | grep '^data:' | tail -1 | sed 's/^data: //' | jq -r '.result.structuredContent.data.trades[] | "\(.side | ascii_upcase) \(.ticker): \(.weight_delta * 100 | round)% (\(.estimated_value // 0 | round) ₽)"'
```

---

## Быстрый тест (копируй и вставляй)

```bash
# Сценарий 1: Снижение концентрации SBER 45% → 25%
curl -s -X POST http://localhost:8010/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{"jsonrpc":"2.0","method":"tools/call","params":{"name":"suggest_rebalance","arguments":{"positions":[{"ticker":"SBER","current_weight":0.45,"asset_class":"equity"},{"ticker":"GAZP","current_weight":0.20,"asset_class":"equity"},{"ticker":"LKOH","current_weight":0.15,"asset_class":"equity"},{"ticker":"ROSN","current_weight":0.10,"asset_class":"equity"},{"ticker":"GMKN","current_weight":0.10,"asset_class":"equity"}],"total_portfolio_value":10000000,"risk_profile":{"max_single_position_weight":0.25,"max_turnover":0.30}}},"id":1}' \
  | grep '^data:' | tail -1 | sed 's/^data: //' | jq '.result.structuredContent.data'
```
