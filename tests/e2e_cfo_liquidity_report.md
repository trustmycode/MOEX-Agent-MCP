# E2E: CFO Liquidity Report (Сценарий 9)

Документ содержит примеры вызовов инструмента `build_cfo_liquidity_report` через MCP API.

## 1. Запуск сервера

```bash
cd /Users/Admin/CursorProject/moex-agentic-system
python -m risk_analytics_mcp.main
```

Сервер будет доступен на `http://localhost:8010`

> **Важно:** FastMCP возвращает Server-Sent Events (SSE). 
> Результат находится в последней строке `data:` — используем `grep` + `tail` для извлечения.

---

## 2. Проверка работоспособности

### Health check

```bash
curl -s http://localhost:8010/health | jq
```

Ожидаемый ответ:
```json
{"status": "ok"}
```

---

## 3. Пример 1: Базовый CFO-отчёт для диверсифицированного портфеля

**Ситуация:** Портфель из 6 акций, преимущественно ликвидных.

```bash
curl -s -X POST http://localhost:8010/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{
    "jsonrpc": "2.0",
    "method": "tools/call",
    "params": {
      "name": "build_cfo_liquidity_report",
      "arguments": {
        "positions": [
          {"ticker": "SBER", "weight": 0.25, "asset_class": "equity", "liquidity_bucket": "0-7d", "currency": "RUB"},
          {"ticker": "GAZP", "weight": 0.20, "asset_class": "equity", "liquidity_bucket": "0-7d", "currency": "RUB"},
          {"ticker": "LKOH", "weight": 0.15, "asset_class": "equity", "liquidity_bucket": "0-7d", "currency": "RUB"},
          {"ticker": "ROSN", "weight": 0.15, "asset_class": "equity", "liquidity_bucket": "8-30d", "currency": "RUB"},
          {"ticker": "VTBR", "weight": 0.10, "asset_class": "equity", "liquidity_bucket": "0-7d", "currency": "RUB"},
          {"ticker": "YNDX", "weight": 0.15, "asset_class": "equity", "liquidity_bucket": "0-7d", "currency": "RUB"}
        ],
        "from_date": "2024-01-01",
        "to_date": "2024-12-01",
        "base_currency": "RUB",
        "total_portfolio_value": 50000000.0,
        "horizon_months": 12
      }
    },
    "id": 1
  }' | grep '^data:' | tail -1 | sed 's/^data: //' | jq '.result.structuredContent.data'
```

**Ожидаемый результат:**
- Профиль ликвидности: 85% в корзине 0-7d, 15% в 8-30d
- Концентрации: top1 25%, top3 60%, HHI ~0.17
- Стресс-сценарии: base_case, equity_-10_fx_+20, rates_+300bp
- Executive summary со статусом "healthy" или "adequate"

---

## 4. Пример 2: Портфель с валютной экспозицией

**Ситуация:** 50% портфеля в USD-активах, высокий валютный риск.

```bash
curl -s -X POST http://localhost:8010/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{
    "jsonrpc": "2.0",
    "method": "tools/call",
    "params": {
      "name": "build_cfo_liquidity_report",
      "arguments": {
        "positions": [
          {"ticker": "SBER", "weight": 0.30, "asset_class": "equity", "liquidity_bucket": "0-7d", "currency": "RUB"},
          {"ticker": "GAZP", "weight": 0.20, "asset_class": "equity", "liquidity_bucket": "0-7d", "currency": "RUB"},
          {"ticker": "AAPL", "weight": 0.25, "asset_class": "equity", "liquidity_bucket": "0-7d", "currency": "USD"},
          {"ticker": "MSFT", "weight": 0.25, "asset_class": "equity", "liquidity_bucket": "0-7d", "currency": "USD"}
        ],
        "from_date": "2024-01-01",
        "to_date": "2024-12-01",
        "base_currency": "RUB",
        "total_portfolio_value": 100000000.0
      }
    },
    "id": 2
  }' | grep '^data:' | tail -1 | sed 's/^data: //' | jq '.result.structuredContent.data'
```

**Ожидаемый результат:**
- `currency_exposure.fx_risk_pct`: 50% (USD экспозиция)
- Рекомендация по хеджированию валютного риска (priority: medium)
- Стресс-сценарий equity_-10_fx_+20 покажет значительное влияние на P&L

---

## 5. Пример 3: Портфель с облигациями и дюрацией

**Ситуация:** 50% в облигациях, дюрация 5 лет.

```bash
curl -s -X POST http://localhost:8010/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{
    "jsonrpc": "2.0",
    "method": "tools/call",
    "params": {
      "name": "build_cfo_liquidity_report",
      "arguments": {
        "positions": [
          {"ticker": "SBER", "weight": 0.25, "asset_class": "equity", "liquidity_bucket": "0-7d", "currency": "RUB"},
          {"ticker": "GAZP", "weight": 0.15, "asset_class": "equity", "liquidity_bucket": "0-7d", "currency": "RUB"},
          {"ticker": "SU26238RMFS4", "weight": 0.30, "asset_class": "fixed_income", "liquidity_bucket": "8-30d", "currency": "RUB"},
          {"ticker": "RU000A1062M5", "weight": 0.20, "asset_class": "credit", "liquidity_bucket": "31-90d", "currency": "RUB"},
          {"ticker": "LQDT", "weight": 0.10, "asset_class": "cash", "liquidity_bucket": "0-7d", "currency": "RUB"}
        ],
        "from_date": "2024-01-01",
        "to_date": "2024-12-01",
        "base_currency": "RUB",
        "total_portfolio_value": 200000000.0,
        "aggregates": {
          "fixed_income_duration_years": 5.0,
          "credit_spread_duration_years": 3.0
        },
        "stress_scenarios": ["base_case", "rates_+300bp", "credit_spreads_+150bp"]
      }
    },
    "id": 3
  }' | grep '^data:' | tail -1 | sed 's/^data: //' | jq '.result.structuredContent.data'
```

**Ожидаемый результат:**
- `duration_profile.portfolio_duration_years`: 5.0
- `duration_profile.fixed_income_weight_pct`: 50% (fixed_income + credit)
- Стресс-сценарий rates_+300bp покажет значительное влияние из-за высокой дюрации
- Рекомендация по снижению дюрации (если > 5 лет)

---

## 6. Пример 4: Портфель с ковенант-чеками

**Ситуация:** Низкая быстрая ликвидность (60%), лимит ковенанта 70%.

```bash
curl -s -X POST http://localhost:8010/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{
    "jsonrpc": "2.0",
    "method": "tools/call",
    "params": {
      "name": "build_cfo_liquidity_report",
      "arguments": {
        "positions": [
          {"ticker": "SBER", "weight": 0.60, "asset_class": "equity", "liquidity_bucket": "0-7d", "currency": "RUB"},
          {"ticker": "GAZP", "weight": 0.20, "asset_class": "equity", "liquidity_bucket": "8-30d", "currency": "RUB"},
          {"ticker": "LKOH", "weight": 0.20, "asset_class": "equity", "liquidity_bucket": "31-90d", "currency": "RUB"}
        ],
        "from_date": "2024-01-01",
        "to_date": "2024-12-01",
        "base_currency": "RUB",
        "total_portfolio_value": 75000000.0,
        "covenant_limits": {
          "min_liquidity_ratio": 0.70
        }
      }
    },
    "id": 4
  }' | grep '^data:' | tail -1 | sed 's/^data: //' | jq '.result.structuredContent.data'
```

**Ожидаемый результат:**
- `liquidity_profile.quick_ratio_pct`: 60% (только SBER в 0-7d)
- При стрессе возможно нарушение ковенанта
- `stress_scenarios[*].covenant_breaches`: список нарушений с code "LIQUIDITY_RATIO"
- Рекомендация высокого приоритета по увеличению ликвидности
- `executive_summary.overall_liquidity_status`: "warning" или "critical"

---

## 7. Пример 5: Концентрированный портфель

**Ситуация:** Всего 2 позиции по 50% — максимальная концентрация.

```bash
curl -s -X POST http://localhost:8010/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{
    "jsonrpc": "2.0",
    "method": "tools/call",
    "params": {
      "name": "build_cfo_liquidity_report",
      "arguments": {
        "positions": [
          {"ticker": "SBER", "weight": 0.50, "asset_class": "equity", "liquidity_bucket": "0-7d", "currency": "RUB"},
          {"ticker": "GAZP", "weight": 0.50, "asset_class": "equity", "liquidity_bucket": "0-7d", "currency": "RUB"}
        ],
        "from_date": "2024-01-01",
        "to_date": "2024-12-01",
        "base_currency": "RUB"
      }
    },
    "id": 5
  }' | grep '^data:' | tail -1 | sed 's/^data: //' | jq '.result.structuredContent.data'
```

**Ожидаемый результат:**
- `concentration_profile.top1_weight_pct`: 50%
- `concentration_profile.hhi`: 0.50 (очень высокая концентрация)
- Рекомендация высокого приоритета по снижению концентрации
- `executive_summary.key_risks`: включает "Высокая концентрация в отдельных позициях"

---

## 8. Пример 6: CFO-отчёт для пенсионного фонда

**Ситуация:** Консервативный портфель с жёсткими лимитами.

```bash
curl -s -X POST http://localhost:8010/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{
    "jsonrpc": "2.0",
    "method": "tools/call",
    "params": {
      "name": "build_cfo_liquidity_report",
      "arguments": {
        "positions": [
          {"ticker": "SBER", "weight": 0.10, "asset_class": "equity", "liquidity_bucket": "0-7d", "currency": "RUB"},
          {"ticker": "GAZP", "weight": 0.10, "asset_class": "equity", "liquidity_bucket": "0-7d", "currency": "RUB"},
          {"ticker": "SU26238RMFS4", "weight": 0.25, "asset_class": "fixed_income", "liquidity_bucket": "8-30d", "currency": "RUB"},
          {"ticker": "SU26240RMFS0", "weight": 0.25, "asset_class": "fixed_income", "liquidity_bucket": "8-30d", "currency": "RUB"},
          {"ticker": "LQDT", "weight": 0.30, "asset_class": "cash", "liquidity_bucket": "0-7d", "currency": "RUB"}
        ],
        "from_date": "2024-01-01",
        "to_date": "2024-12-01",
        "base_currency": "RUB",
        "total_portfolio_value": 500000000.0,
        "horizon_months": 12,
        "aggregates": {
          "fixed_income_duration_years": 3.0
        },
        "covenant_limits": {
          "min_liquidity_ratio": 0.30,
          "min_current_ratio": 1.5
        }
      }
    },
    "id": 6
  }' | grep '^data:' | tail -1 | sed 's/^data: //' | jq '.result.structuredContent.data'
```

**Ожидаемый результат:**
- `liquidity_profile.quick_ratio_pct`: 50% (акции + cash в 0-7d)
- Низкая концентрация (HHI < 0.2)
- `executive_summary.overall_liquidity_status`: "healthy"
- Минимум рекомендаций (портфель сбалансирован)

---

## 9. Сценарии ошибок

### Пустой портфель

```bash
curl -s -X POST http://localhost:8010/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{
    "jsonrpc": "2.0",
    "method": "tools/call",
    "params": {
      "name": "build_cfo_liquidity_report",
      "arguments": {
        "positions": [],
        "from_date": "2024-01-01",
        "to_date": "2024-12-01"
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
      "name": "build_cfo_liquidity_report",
      "arguments": {
        "positions": [
          {"ticker": "SBER", "weight": 0.30, "asset_class": "equity"},
          {"ticker": "GAZP", "weight": 0.30, "asset_class": "equity"}
        ],
        "from_date": "2024-01-01",
        "to_date": "2024-12-01"
      }
    },
    "id": 101
  }' | grep '^data:' | tail -1 | sed 's/^data: //' | jq
```

**Ожидаемый результат:** Ошибка `VALIDATION_ERROR`

---

## 10. Полезные команды

### Базовая команда (извлечение JSON из SSE)

```bash
# Шаблон: добавьте в конец любого curl-запроса
| grep '^data:' | tail -1 | sed 's/^data: //' | jq
```

### Просмотр только профиля ликвидности

```bash
... | grep '^data:' | tail -1 | sed 's/^data: //' | jq '.result.structuredContent.data.liquidity_profile'
```

### Просмотр только стресс-сценариев

```bash
... | grep '^data:' | tail -1 | sed 's/^data: //' | jq '.result.structuredContent.data.stress_scenarios'
```

### Просмотр executive summary

```bash
... | grep '^data:' | tail -1 | sed 's/^data: //' | jq '.result.structuredContent.data.executive_summary'
```

### Просмотр рекомендаций

```bash
... | grep '^data:' | tail -1 | sed 's/^data: //' | jq '.result.structuredContent.data.recommendations'
```

### Форматированный вывод рекомендаций

```bash
... | grep '^data:' | tail -1 | sed 's/^data: //' | jq -r '.result.structuredContent.data.recommendations[] | "[\(.priority | ascii_upcase)] \(.category): \(.title)"'
```

---

## 11. Быстрый тест (копируй и вставляй)

```bash
# Сценарий: Диверсифицированный портфель акций
curl -s -X POST http://localhost:8010/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{"jsonrpc":"2.0","method":"tools/call","params":{"name":"build_cfo_liquidity_report","arguments":{"positions":[{"ticker":"SBER","weight":0.25,"asset_class":"equity","liquidity_bucket":"0-7d","currency":"RUB"},{"ticker":"GAZP","weight":0.25,"asset_class":"equity","liquidity_bucket":"0-7d","currency":"RUB"},{"ticker":"LKOH","weight":0.25,"asset_class":"equity","liquidity_bucket":"0-7d","currency":"RUB"},{"ticker":"ROSN","weight":0.25,"asset_class":"equity","liquidity_bucket":"0-7d","currency":"RUB"}],"from_date":"2024-01-01","to_date":"2024-12-01","base_currency":"RUB","total_portfolio_value":10000000}},"id":1}' \
  | grep '^data:' | tail -1 | sed 's/^data: //' | jq '.result.structuredContent.data'
```

---

## 12. Структура JSON-ответа

```json
{
  "metadata": {
    "as_of": "2025-01-15T10:30:00Z",
    "from_date": "2024-01-01",
    "to_date": "2024-12-01",
    "horizon_months": 12,
    "base_currency": "RUB",
    "total_portfolio_value": 50000000.0,
    "positions_count": 6
  },
  "liquidity_profile": {
    "buckets": [...],
    "quick_ratio_pct": 85.0,
    "short_term_ratio_pct": 100.0
  },
  "duration_profile": {
    "portfolio_duration_years": null,
    "fixed_income_weight_pct": 0.0
  },
  "currency_exposure": {
    "by_currency": [...],
    "fx_risk_pct": 0.0
  },
  "concentration_profile": {
    "top1_weight_pct": 25.0,
    "top3_weight_pct": 60.0,
    "top5_weight_pct": 85.0,
    "hhi": 0.17,
    "by_asset_class": [...]
  },
  "risk_metrics": {
    "total_return_pct": 12.5,
    "annualized_volatility_pct": 22.3,
    "max_drawdown_pct": -15.2,
    "var_light": {...}
  },
  "stress_scenarios": [...],
  "recommendations": [...],
  "executive_summary": {
    "overall_liquidity_status": "healthy",
    "key_risks": [...],
    "key_strengths": [...],
    "action_items": [...]
  },
  "error": null
}
```

---

## 13. Человекочитаемый отчёт для CFO (Markdown)

На основе JSON-ответа агент формирует отчёт в формате:

```markdown
# Отчёт CFO по ликвидности портфеля

**Дата формирования:** 15 января 2025 г.  
**Период анализа:** 01.01.2024 — 01.12.2024  
**Стоимость портфеля:** 50 000 000 ₽

## Executive Summary

**Статус ликвидности:** 🟢 Здоровый

### Ключевые риски
- Потенциальные потери до 6% при стресс-сценарии "Падение акций на 10%"

### Сильные стороны
- Высокий уровень ликвидности: 85% активов реализуемы в течение 7 дней
- Хорошая диверсификация портфеля

## Профиль ликвидности

| Корзина   | Доля    | Стоимость        | Инструменты           |
|-----------|---------|------------------|-----------------------|
| 0-7 дней  | 85.0%   | 42 500 000 ₽     | SBER, GAZP, LKOH...   |
| 8-30 дней | 15.0%   | 7 500 000 ₽      | ROSN                  |
| 31-90 дней| 0.0%    | 0 ₽              | —                     |
| 90+ дней  | 0.0%    | 0 ₽              | —                     |

**Коэффициент быстрой ликвидности (0-7d):** 85.0%  
**Краткосрочная ликвидность (0-30d):** 100.0%

## Стресс-сценарии

| Сценарий                    | P&L       | P&L (₽)       | Ликвидность после |
|-----------------------------|-----------|---------------|-------------------|
| Базовый                     | 0.0%      | 0 ₽           | 100.0%            |
| Падение акций -10%, FX +20% | -6.0%     | -3 000 000 ₽  | 94.0%             |
| Рост ставок +300 bps        | 0.0%      | 0 ₽           | 100.0%            |

## Рекомендации

1. **[Средний приоритет]** Концентрация: Индекс HHI (0.17) указывает на умеренную концентрацию.
   - *Действие:* Рассмотреть увеличение числа позиций для улучшения диверсификации.

---
*Отчёт сформирован автоматически системой risk-analytics-mcp v0.1.0*
```

---

## 14. Связанные документы

- [SPEC_risk-analytics-mcp.md](../docs/SPEC_risk-analytics-mcp.md) — спецификация MCP-сервера
- [SCENARIOS_PORTFOLIO_RISK.md](../docs/SCENARIOS_PORTFOLIO_RISK.md) — описание сценариев 5/7/9
- [TASK-2025-105](../tasks/TASK-2025-105-cfo-liquidity-report.md) — задача на реализацию
- [e2e_suggest_rebalance_curl.md](./e2e_suggest_rebalance_curl.md) — аналогичные примеры для suggest_rebalance
