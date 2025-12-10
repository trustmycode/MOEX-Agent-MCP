---
id: TASK-2025-054
title: "Фаза P0.3. Basic-сценарии и smoke-тесты"
status: backlog
priority: high
type: feature
estimate: 8h
assignee: @unassigned
created: 2025-12-10
updated: 2025-12-10
parents: [TASK-2025-046]
arch_refs: [ARCH-agent-moex-market-analyst, ARCH-mcp-moex-iss]
risk: medium
benefit: "Гарантирует поддержку сценариев single_security_overview, compare_securities, index_risk_scan и portfolio_risk в режиме basic."
audit_log:
  - {date: 2025-12-10, user: "@AI-DocArchitect", action: "created with status backlog"}
---

## Описание

Зафиксировать и реализовать минимальные планы для сценариев `single_security_overview`, `compare_securities`, `index_risk_scan` и `portfolio_risk` в режиме `PLANNER_MODE=basic`, а также добавить smoke-тесты, проверяющие, что эти сценарии стабильно отрабатывают в пределах лимитов `planner.limits`.

## Критерии приемки

- В коде/документации описаны типовые планы (последовательность шагов `mcp_call` и финальной LLM-генерации) для:
  - `single_security_overview` (1 тикер);
  - `compare_securities` (2–3 тикера);
  - `index_risk_scan` (анализ индекса);
  - `portfolio_risk` (портфель до `MAX_TICKERS_PER_REQUEST` тикеров).
- Реализованы smoke-тесты, которые в режиме `PLANNER_MODE=basic`:
  - строят план для каждого сценария;
  - выполняют его (с реальными или заглушечными MCP-вызовами);
  - проверяют, что количество шагов и LLM-вызовов не превышает лимиты, а ответ содержит непустой `output.text` и ожидаемые таблицы.
- Для сценария `portfolio_risk` тесты покрывают как малый портфель (<= `MAX_TICKERS_PER_REQUEST`), так и портфель с избытком тикеров, где в basic-режиме применяется ограничение числа бумаг.

## Определение готовности

- Все четыре сценария проходят smoke-тесты, не нарушая заданные лимиты и не требуя ручной настройки конфигурации для демо.
- Эти сценарии могут быть воспроизведены в демо-окружении как часть витрины решения.

## Заметки

В фазе PC сценарии будут формализованы через `ScenarioTemplate` и поле `scenario_type`; текущая задача фокусируется на работоспособности в basic-режиме.
