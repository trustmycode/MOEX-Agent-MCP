---
id: TASK-2025-122
title: "Orchestrator Agent (Router)"
status: planned
priority: critical
type: feature
estimate: 20h
assignee: @unassigned
created: 2025-12-12
updated: 2025-12-12
parents: [TASK-2025-120]
children: []
arch_refs: [ARCH-agent-moex-market-analyst]
risk: high
benefit: "Создаёт центральный компонент мультиагентной системы — маршрутизатор запросов к сабагентам."
supersedes: [TASK-2025-104]
audit_log:
  - {date: 2025-12-12, user: "@AI-Codex", action: "created as critical P0 task for multi-agent MVP"}
---

## Описание

Реализовать `OrchestratorAgent` — центральный агент, который:
1. Принимает пользовательский запрос (A2A Input)
2. Классифицирует intent и выбирает сценарий
3. Вызывает нужные сабагенты в правильном порядке
4. Агрегирует результаты
5. Передаёт в ExplainerSubagent / DashboardSubagent для формирования ответа
6. Возвращает A2A Output

## Контекст

Заменяет старый монолитный `Planner` + `ToolOrchestrator`. Вместо жёстких `ScenarioTemplate` (отменённая TASK-104) оркестратор динамически решает, какие сабагенты вызвать, на основе:
- user_query
- user_role (CFO, риск-менеджер, аналитик)
- доступных сабагентов в Registry

## Критерии приёмки

### Intent Classification

- [ ] Реализован метод `classify_intent(query: str, role: str) -> ScenarioType`:
  - `portfolio_risk` — анализ риска портфеля
  - `cfo_liquidity` — CFO-отчёт по ликвидности
  - `issuer_compare` — сравнение эмитента с пирами
  - `security_overview` — обзор одной бумаги
  - `securities_compare` — сравнение нескольких бумаг
  - `index_scan` — анализ индекса
- [ ] Классификация на основе LLM-промпта или простых правил (keywords + role)

### Orchestration Flow

- [ ] Для каждого `ScenarioType` определён pipeline сабагентов:
  ```
  portfolio_risk:
    1. MarketDataSubagent (get prices, weights)
    2. RiskAnalyticsSubagent (compute_portfolio_risk_basic)
    3. ExplainerSubagent (generate text)
    4. DashboardSubagent (generate JSON-UI)
  
  cfo_liquidity:
    1. RiskAnalyticsSubagent (cfo_liquidity_report)
    2. ExplainerSubagent
    3. DashboardSubagent
  
  issuer_compare:
    1. MarketDataSubagent (get fundamentals)
    2. RiskAnalyticsSubagent (issuer_peers_compare)
    3. ExplainerSubagent
  ```
- [ ] Оркестратор последовательно вызывает сабагентов, передавая `AgentContext`
- [ ] При ошибке сабагента — логирует и возвращает понятную ошибку (не падает)

### A2A Integration

- [ ] `OrchestratorAgent.handle_request(a2a_input: A2AInput) -> A2AOutput`
- [ ] Формирует `AgentContext` из `A2AInput`
- [ ] После выполнения pipeline формирует `A2AOutput`:
  - `output.text` — от ExplainerSubagent
  - `output.tables` — от RiskAnalyticsSubagent (если есть)
  - `output.dashboard` — от DashboardSubagent (если есть)
  - `output.debug` — метаданные (какие сабагенты вызывались, timing)

### Error Handling

- [ ] Если сабагент вернул `status: "error"`, оркестратор:
  - логирует ошибку
  - пытается продолжить с доступными данными (graceful degradation)
  - или возвращает пользователю понятное сообщение «Не удалось выполнить запрос»
- [ ] Timeout на каждый сабагент (30s default)

## Определение готовности

- Оркестратор успешно обрабатывает демо-запросы по сценариям 5/7/9:
  - «Оцени риск моего портфеля: SBER 40%, GAZP 30%, LKOH 30%»
  - «Сформируй отчёт для CFO по ликвидности портфеля»
  - «Сравни SBER с пирами по банковскому сектору»
- A2A-ответ содержит текст и (для 7/9) dashboard JSON
- Логи показывают полный trace: intent → subagents called → result

## Структура файлов

```
packages/agent-service/src/agent_service/orchestrator/
├── __init__.py
├── orchestrator_agent.py     # OrchestratorAgent
├── intent_classifier.py      # classify_intent()
└── pipelines.py              # scenario → subagent pipelines
```

## Зависимости

- TASK-120 (BaseSubagent, AgentContext, Registry) — **блокер**
- TASK-121 (MarketDataSubagent, RiskAnalyticsSubagent)
- TASK-123 (ExplainerSubagent, DashboardSubagent)

## Заметки

Делать в последнюю очередь после 120/121/123, так как оркестратор связывает всё вместе. Можно начать с простого hardcoded pipeline для одного сценария (portfolio_risk), потом добавить остальные.
