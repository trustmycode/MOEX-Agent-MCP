# E2E: Тестирование мультиагентной архитектуры

Документ содержит примеры тестирования агентской системы с реальными MCP-серверами.

## 1. Запуск инфраструктуры

### Терминал 1 — moex-iss-mcp (порт 8000)

```bash
cd /Users/Admin/CursorProject/MOEX-Agent-MCP
python -m moex_iss_mcp.main
```

Ожидаемый вывод:
```
============================================================
🌐 ЗАПУСК MCP СЕРВЕРА: moex-iss-mcp
============================================================
🚀 MCP Server: http://0.0.0.0:8000/mcp
============================================================
```

### Терминал 2 — risk-analytics-mcp (порт 8010)

```bash
cd /Users/Admin/CursorProject/MOEX-Agent-MCP
python -m risk_analytics_mcp.main
```

### Проверка серверов (health check)

```bash
curl -s http://localhost:8000/health | jq
curl -s http://localhost:8010/health | jq
```

Ожидаемый ответ для каждого:
```json
{"status": "ok"}
```

---

## 2. Прямые вызовы MCP-серверов (curl)

> **Примечание:** Серверы настроены с `json_response=True`, поэтому ответ приходит в JSON-формате.

### 2.1 get_security_snapshot

```bash
curl -s -X POST http://localhost:8000/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{
    "jsonrpc": "2.0",
    "method": "tools/call",
    "params": {
      "name": "get_security_snapshot",
      "arguments": {"ticker": "SBER", "board": "TQBR"}
    },
    "id": 1
  }' | jq '.result.structuredContent'
```

**Ожидаемый результат:** Данные по акции SBER (цена, объём, изменение)

### 2.2 get_ohlcv_timeseries

```bash
curl -s -X POST http://localhost:8000/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{
    "jsonrpc": "2.0",
    "method": "tools/call",
    "params": {
      "name": "get_ohlcv_timeseries",
      "arguments": {
        "ticker": "SBER",
        "board": "TQBR",
        "from_date": "2024-11-01",
        "to_date": "2024-12-01",
        "interval": "1d"
      }
    },
    "id": 2
  }' | jq '.result.structuredContent.data | length'
```

**Ожидаемый результат:** Количество дневных свечей (~22)

### 2.3 compute_portfolio_risk_basic

```bash
curl -s -X POST http://localhost:8010/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{
    "jsonrpc": "2.0",
    "method": "tools/call",
    "params": {
      "name": "compute_portfolio_risk_basic",
      "arguments": {
        "positions": [
          {"ticker": "SBER", "weight": 0.4},
          {"ticker": "GAZP", "weight": 0.3},
          {"ticker": "LKOH", "weight": 0.3}
        ],
        "from_date": "2024-01-01",
        "to_date": "2024-12-01",
        "rebalance": "buy_and_hold"
      }
    },
    "id": 3
  }' | jq '.result.structuredContent.data'
```

**Ожидаемый результат:** Метрики риска портфеля (volatility, VaR, Sharpe, max_drawdown)

---

## 3. Тестирование через Python (e2e_test.py)

### Запуск интерактивного режима

```bash
cd /Users/Admin/CursorProject/MOEX-Agent-MCP/packages/agent-service
python examples/e2e_test.py
```

### Запуск конкретного теста

```bash
# Все тесты
python examples/e2e_test.py --all

# Только MCP-клиенты
python examples/e2e_test.py --mcp

# Только сабагенты
python examples/e2e_test.py --subagents

# Только оркестратор
python examples/e2e_test.py --orchestrator
```

### Кастомные URL MCP-серверов

```bash
MOEX_ISS_MCP_URL=http://localhost:8000 \
RISK_ANALYTICS_MCP_URL=http://localhost:8010 \
python examples/e2e_test.py
```

---

## 4. Сценарии тестирования агентской системы

### 4.1 Сценарий: portfolio_risk (Сценарий 5)

**Запрос:** "Оцени риск моего портфеля: SBER 40%, GAZP 30%, LKOH 30%"

**Pipeline сабагентов:**
1. `market_data` → получение OHLCV данных
2. `risk_analytics` → расчёт портфельного риска
3. `dashboard` → формирование RiskDashboardSpec
4. `explainer` → генерация текстового отчёта

**Python-тест:**

```python
import asyncio
from agent_service.core import AgentContext, SubagentRegistry
from agent_service.mcp.types import McpConfig
from agent_service.orchestrator.models import A2AInput
from agent_service.orchestrator.orchestrator_agent import OrchestratorAgent
from agent_service.subagents.dashboard import DashboardSubagent
from agent_service.subagents.explainer import ExplainerSubagent
from agent_service.subagents.market_data import MarketDataSubagent
from agent_service.subagents.risk_analytics import RiskAnalyticsSubagent

async def test_portfolio_risk():
    # Конфигурация
    moex_config = McpConfig(name="moex-iss-mcp", url="http://localhost:8000")
    risk_config = McpConfig(name="risk-analytics-mcp", url="http://localhost:8010")
    
    # Регистрация сабагентов
    registry = SubagentRegistry()
    registry.register(MarketDataSubagent(mcp_config=moex_config))
    registry.register(RiskAnalyticsSubagent(mcp_config=risk_config))
    registry.register(ExplainerSubagent())
    registry.register(DashboardSubagent())
    
    # Оркестратор
    orchestrator = OrchestratorAgent(registry=registry, enable_debug=True)
    
    # A2A-запрос
    a2a_input = A2AInput(
        user_query="Оцени риск моего портфеля: SBER 40%, GAZP 30%, LKOH 30%",
        user_role="CFO",
        session_id="test-session-1",
        locale="ru",
    )
    
    # Выполнение
    output = await orchestrator.handle_request(a2a_input)
    
    # Проверки
    assert output.status in ("success", "partial")
    assert output.text  # Есть текстовый отчёт
    print(f"Статус: {output.status}")
    print(f"Сценарий: {output.debug.scenario_type}")
    print(f"Время: {output.debug.total_duration_ms:.0f}ms")
    print(f"Текст: {output.text[:500]}...")

asyncio.run(test_portfolio_risk())
```

**Ожидаемый результат:**
- Статус: `success` или `partial`
- Сценарий: `portfolio_risk`
- Текст: отчёт с метриками (волатильность, VaR, Sharpe, max_drawdown)
- Dashboard: RiskDashboardSpec с metric_cards, tables, alerts

### 4.2 Сценарий: cfo_liquidity (Сценарий 9)

**Запрос:** "Сформируй CFO-отчёт по ликвидности портфеля"

**Pipeline сабагентов:**
1. `risk_analytics` → cfo_liquidity_report
2. `dashboard` → формирование RiskDashboardSpec
3. `explainer` → генерация текстового отчёта

**Ожидаемый результат:**
- Профиль ликвидности по корзинам (0-7d, 8-30d, 31-90d, 90+)
- Концентрации (top1, top3, HHI)
- Стресс-сценарии
- Executive summary

### 4.3 Сценарий: security_overview

**Запрос:** "Дай обзор акции SBER"

**Pipeline сабагентов:**
1. `market_data` → get_security_snapshot + get_ohlcv_timeseries
2. `explainer` → генерация текстового отчёта

**Ожидаемый результат:**
- Текущая цена, объём, изменение за день
- Историческая динамика
- Текстовое описание

### 4.4 Сценарий: issuer_peers_compare

**Запрос:** "Сравни SBER с пирами по банковскому сектору"

**Pipeline сабагентов:**
1. `market_data` → get_security_fundamentals
2. `risk_analytics` → issuer_peers_compare
3. `explainer` → генерация сравнительного отчёта

**Ожидаемый результат:**
- Таблица сравнения с пирами (P/E, ROE, Dividend Yield)
- Ранжирование по метрикам

---

## 5. Тестирование ошибок

### 5.1 Недоступный MCP-сервер

```python
# Остановите moex-iss-mcp и запустите тест
# Ожидание: graceful degradation, понятное сообщение об ошибке
```

### 5.2 Неизвестный тикер

```bash
curl -s -X POST http://localhost:8000/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{
    "jsonrpc": "2.0",
    "method": "tools/call",
    "params": {
      "name": "get_security_snapshot",
      "arguments": {"ticker": "INVALID_TICKER", "board": "TQBR"}
    },
    "id": 100
  }' | jq '.result.structuredContent.error'
```

**Ожидаемый результат:** `error_type: "INVALID_TICKER"`

### 5.3 Неопределённый intent

**Запрос:** "Какая погода в Москве?"

**Ожидаемый результат:** 
- `scenario_type: "unknown"`
- Понятное сообщение: "Не удалось определить тип запроса"

---

## 6. Полезные команды

### Извлечение данных из JSON-ответа

```bash
# Полный результат
| jq '.result.structuredContent'

# Только данные
| jq '.result.structuredContent.data'

# Только ошибка
| jq '.result.structuredContent.error'

# Только метаданные
| jq '.result.structuredContent.metadata'
```

### Проверка всех серверов одной командой

```bash
echo "moex-iss-mcp:"; curl -s http://localhost:8000/health | jq -r '.status'
echo "risk-analytics-mcp:"; curl -s http://localhost:8010/health | jq -r '.status'
```

---

## 7. Структура A2A-ответа

```json
{
  "status": "success",        // success | partial | error
  "text": "...",              // Текстовый отчёт от ExplainerSubagent
  "tables": [                 // Таблицы от RiskAnalyticsSubagent
    {
      "id": "positions",
      "title": "Позиции портфеля",
      "columns": ["Тикер", "Вес, %", "Доходность, %"],
      "rows": [["SBER", "40.0", "12.5"], ...]
    }
  ],
  "dashboard": {              // RiskDashboardSpec от DashboardSubagent
    "metric_cards": [...],
    "tables": [...],
    "alerts": [...]
  },
  "error_message": null,      // Сообщение об ошибке (если есть)
  "debug": {                  // Отладочная информация
    "scenario_type": "portfolio_risk",
    "scenario_confidence": 0.95,
    "pipeline": ["market_data", "risk_analytics", "dashboard", "explainer"],
    "subagent_traces": [
      {"name": "market_data", "status": "success", "duration_ms": 1234.5},
      ...
    ],
    "total_duration_ms": 5678.9
  }
}
```

---

## 8. Чек-лист E2E тестирования

- [ ] MCP-серверы запущены и отвечают на /health
- [ ] Прямые вызовы MCP (curl) работают
- [ ] `e2e_test.py --mcp` — все тесты пройдены
- [ ] `e2e_test.py --subagents` — сабагенты получают реальные данные
- [ ] `e2e_test.py --orchestrator` — полный pipeline работает
- [ ] Кастомный запрос через интерактивный режим
- [ ] Graceful degradation при ошибках MCP

---

## 9. Связанные документы

- [e2e_cfo_liquidity_report.md](../../../tests/e2e_cfo_liquidity_report.md) — примеры CFO-отчёта
- [e2e_suggest_rebalance.sh](../../../tests/e2e_suggest_rebalance.sh) — примеры ребалансировки
- [README.md](./README.md) — краткая инструкция
- [SPEC_risk-analytics-mcp.md](../../../docs/SPEC_risk-analytics-mcp.md) — спецификация risk-analytics-mcp


