---
id: TASK-2025-121
title: "MarketData & RiskAnalytics Subagents"
status: planned
priority: critical
type: feature
estimate: 16h
assignee: @unassigned
created: 2025-12-12
updated: 2025-12-12
parents: [TASK-2025-120]
children: []
arch_refs: [ARCH-agent-moex-market-analyst, ARCH-mcp-moex-iss, ARCH-mcp-risk-analytics]
risk: medium
benefit: "Создаёт рабочие сабагенты для вызова MCP-инструментов — основной механизм получения данных и расчётов."
audit_log:
  - {date: 2025-12-12, user: "@AI-Codex", action: "created as critical P0 task for multi-agent MVP"}
---

## Описание

Реализовать два ключевых сабагента-воркера, которые вызывают MCP-серверы и возвращают структурированные данные:

### 1. MarketDataSubagent

Отвечает за взаимодействие с `moex-iss-mcp`:
- `get_security_snapshot` — текущие данные по бумаге
- `get_ohlcv_timeseries` — исторические котировки
- `get_index_constituents_metrics` — состав и метрики индекса
- `get_security_fundamentals` — фундаментальные данные (P/E, EPS, div yield)

### 2. RiskAnalyticsSubagent

Отвечает за взаимодействие с `risk-analytics-mcp`:
- `compute_portfolio_risk_basic` — базовый портфельный риск
- `compute_correlation_matrix` — матрица корреляций
- `suggest_rebalance` — рекомендации по ребалансировке
- `cfo_liquidity_report` — CFO-отчёт
- `issuer_peers_compare` — сравнение эмитента с пирами (TASK-108)

## Критерии приёмки

### MarketDataSubagent

- [ ] Наследуется от `BaseSubagent` (TASK-120)
- [ ] Реализует `execute(context)` с логикой:
  - анализ `context.user_query` или `context.scenario_type`
  - выбор нужных MCP-инструментов
  - вызов `moex-iss-mcp` через HTTP/MCP-клиент
  - обработка ошибок (INVALID_TICKER, RATE_LIMIT, etc.)
  - возврат `SubagentResult` с данными
- [ ] Встроенные лимиты в промпт/логику:
  - не более 5-10 тикеров за один вызов
  - период данных ≤ 365 дней
  - обработка `TOO_MANY_TICKERS` с выбором top-N по весу
- [ ] Тесты на основные сценарии (snapshot, timeseries, fundamentals)

### RiskAnalyticsSubagent

- [ ] Наследуется от `BaseSubagent` (TASK-120)
- [ ] Реализует `execute(context)` для сценариев:
  - `portfolio_risk` → вызов `compute_portfolio_risk_basic`
  - `portfolio_correlation` → вызов `compute_correlation_matrix`
  - `rebalance` → вызов `suggest_rebalance`
  - `cfo_report` → вызов `cfo_liquidity_report`
  - `issuer_compare` → вызов `issuer_peers_compare`
- [ ] Обработка ошибок MCP и возврат понятных сообщений
- [ ] Тесты на основные сценарии

### Общее

- [ ] Оба сабагента зарегистрированы в `SubagentRegistry`
- [ ] Конфигурация URL MCP-серверов через ENV (`MOEX_ISS_MCP_URL`, `RISK_ANALYTICS_MCP_URL`)

## Определение готовности

- Оркестратор (TASK-122) может вызвать `MarketDataSubagent` и `RiskAnalyticsSubagent` и получить данные
- Сабагенты корректно обрабатывают ошибки MCP и не падают при недоступности сервисов
- Логирование показывает, какие MCP-вызовы были сделаны

## Структура файлов

```
packages/agent-service/src/agent_service/subagents/
├── __init__.py
├── market_data.py      # MarketDataSubagent
└── risk_analytics.py   # RiskAnalyticsSubagent
```

## Зависимости

- TASK-120 (BaseSubagent, AgentContext)
- TASK-077 (compute_portfolio_risk_basic) ✅ done
- TASK-101 (suggest_rebalance) ✅ done
- TASK-105 (cfo_liquidity_report) ✅ done
- TASK-108 (issuer_peers_compare) — planned, можно делать параллельно

## Заметки

Лимиты (не более 5 тикеров и т.п.) теперь встраиваются в логику сабагентов или их промпты, а не в общий планировщик (как было в отменённой TASK-046).
