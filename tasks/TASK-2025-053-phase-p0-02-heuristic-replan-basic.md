---
id: TASK-2025-053
title: "Фаза P0.2. Heuristic re-plan в basic-режиме"
status: backlog
priority: high
type: feature
estimate: 8h
assignee: @unassigned
created: 2025-12-10
updated: 2025-12-10
parents: [TASK-2025-046]
arch_refs: [ARCH-agent-moex-market-analyst]
risk: medium
benefit: "Добавляет один шаг heuristic re-plan для типовых ошибок MCP в режиме PLANNER_MODE=basic."
audit_log:
  - {date: 2025-12-10, user: "@AI-DocArchitect", action: "created with status backlog"}
---

## Описание

Реализовать метод `BasicPlanningStrategy.replan(...)`, который использует лимиты из `planner.limits` и простые эвристики для корректировки плана при типовых ошибках MCP (`DATE_RANGE_TOO_LARGE`, `TOO_MANY_TICKERS`, `RATE_LIMIT`) с жёстким ограничением в одну попытку re-plan.

## Критерии приемки

- В `BasicPlanningStrategy` реализован метод `replan(ctx, exec_result_or_error)` (либо эквивалентный интерфейс), который:
  - при ошибке `DATE_RANGE_TOO_LARGE` сокращает период до `MAX_DAYS_PER_SECURITY` и обновляет соответствующие шаги плана;
  - при ошибке `TOO_MANY_TICKERS` ограничивает список тикеров до `MAX_TICKERS_PER_REQUEST` (top-N по весу, если веса известны, либо первые N тикеров);
  - при `RATE_LIMIT` уменьшает параллелизм/дробит запросы либо меняет параметры так, чтобы снизить нагрузку.
- Количество попыток heuristic re-plan ограничено `MAX_REPLAN_ATTEMPTS_BASIC`, и стратегия не входит в бесконечные циклы.
- В debug-выводе и логах явно видно применение heuristic re-plan: какая ошибка сработала, какие параметры были изменены (даты, число тикеров, параллелизм).

## Определение готовности

- Для тестовых сценариев с заведомо слишком широким периодом или большим портфелем basic-планировщик после одной попытки heuristic re-plan выдаёт работоспособный план, укладывающийся в лимиты.
- В случае невосстанавливаемых ошибок (например, неизвестный тикер) heuristic re-plan не скрывает проблему и возвращает контролируемый отказ.

## Заметки

В последующих фазах (PB) heuristic re-plan будет переведён на работу поверх `PlanExecutionResult`; текущая задача фокусируется на минимальном рабочем поведении для хакатона.
