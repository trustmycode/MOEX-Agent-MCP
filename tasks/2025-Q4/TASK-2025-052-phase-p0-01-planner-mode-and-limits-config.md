---
id: TASK-2025-052
title: "Фаза P0.1. PLANNER_MODE и блок planner.limits"
status: backlog
priority: high
type: chore
estimate: 8h
assignee: @unassigned
created: 2025-12-10
updated: 2025-12-10
parents: [TASK-2025-046]
arch_refs: [ARCH-agent-moex-market-analyst]
risk: low
benefit: "Добавляет явный режим PLANNER_MODE=basic и конфигурационный блок planner.limits для управления сложностью запросов."
audit_log:
  - {date: 2025-12-10, user: "@AI-DocArchitect", action: "created with status backlog"}
---

## Описание

Добавить в конфигурацию агента режим планировщика `PLANNER_MODE` (по умолчанию `basic`) и блок настроек `planner.limits`, откуда basic-планировщик будет читать лимиты по шагам плана, числу LLM-вызовов, глубине истории и количеству тикеров в портфеле.

## Критерии приемки

- В коде конфигурации агента (`Config` или аналог) присутствует поле `planner_mode` с возможными значениями `basic`, `advanced`, `external_agent`; при отсутствии значения в окружении используется `basic`.
- Реализован блок настроек `planner.limits` (в виде секции в конфиге/ENV), содержащий параметры как минимум:
  - `MAX_LLM_CALLS_PER_REQUEST`;
  - `MAX_PLAN_STEPS_BASIC`;
  - `MAX_REPLAN_ATTEMPTS_BASIC`;
  - `MAX_DAYS_PER_SECURITY`;
  - `MAX_TICKERS_PER_REQUEST`;
  - `HARD_TOKEN_BUDGET_PER_REQUEST`.
- Планировщик в режиме `basic` читает значения из `planner.limits` (через единый объект конфигурации) и не использует жёстко зашитые константы.
- В REQUIREMENTS/ARCHITECTURE отражён факт наличия `PLANNER_MODE` и блока `planner.limits` с описанием их назначения.

## Определение готовности

- При запуске агента с разными значениями `PLANNER_MODE` режим планировщика определяется только конфигурацией, без перекомпиляции/ручных правок кода.
- Из unit-/интеграционных тестов видно, что изменения лимитов в `planner.limits` реально влияют на максимальное количество шагов плана и число LLM-вызовов для basic-режима.

## Заметки

Дальнейшие подзадачи фазы P0 используют этот конфигурационный блок для реализации heuristic re-plan и сценариев `portfolio_risk`.
