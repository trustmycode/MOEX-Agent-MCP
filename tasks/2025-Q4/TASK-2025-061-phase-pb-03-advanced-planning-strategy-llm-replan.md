---
id: TASK-2025-061
title: "Фаза PB.3. AdvancedPlanningStrategy и LLM-assisted re-plan"
status: backlog
priority: medium
type: feature
estimate: 16h
assignee: @unassigned
created: 2025-12-10
updated: 2025-12-10
parents: [TASK-2025-048]
arch_refs: [ARCH-agent-moex-market-analyst]
risk: medium
benefit: "Добавляет экспериментальную стратегию планировщика с LLM-assisted re-plan и fallback в basic."
audit_log:
  - {date: 2025-12-10, user: "@AI-DocArchitect", action: "created with status backlog"}
---

## Описание

Реализовать стратегию `AdvancedPlanningStrategy`, которая поверх `PlanExecutionResult` использует LLM для перепланирования в сложных случаях (например, большие портфели в `portfolio_risk`), соблюдая жёсткие лимиты на количество re-plan и всегда имея fallback в basic-режим.

## Критерии приемки

- Реализован класс `AdvancedPlanningStrategy`, активируемый только при `PLANNER_MODE=advanced` и/или отдельном фиче-флаге.
- Метод `replan(...)` в advanced-стратегии:
  - формирует компактный контекст для LLM (сокращённый исходный план, `PlanExecutionResult`, активные лимиты из `planner.limits`, сведения о размере портфеля и лимите top-N);
  - вызывает Qwen3-235B через `LlmClient` для предложения нового плана;
  - валидирует полученный `Plan` (количество шагов, отсутствие циклов, соблюдение лимитов);
  - ограничивает число попыток LLM-assisted re-plan `MAX_REPLAN_ATTEMPTS_ADVANCED`.
- При ошибках LLM, нарушении лимитов или некорректном плане advanced-стратегия записывает соответствующее событие в логи/метрики и откатывается к heuristic re-plan basic-режима.
- Для сценария `portfolio_risk` с 30+ тикерами реализован интеграционный тест, демонстрирующий успешное использование LLM-assisted re-plan (например, изменение плана для более эффективного дробления запросов или перераспределения шагов).

## Определение готовности

- Advanced-режим можно включить в dev-окружении для демонстрационного сценария, при этом при его отключении или сбоях поведение системы возвращается к basic-режиму без регрессий.
- Метрики отражают долю запросов, в которых был задействован advanced re-plan, и частоту fallback-ов.

## Заметки

Advanced-режим рассматривается как бонус/roadmap-функция, не обязательная для базовой сдачи хакатона.
