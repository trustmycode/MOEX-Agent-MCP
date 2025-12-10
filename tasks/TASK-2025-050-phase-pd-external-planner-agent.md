---
id: TASK-2025-050
title: "Фаза PD. Внешний Planner Agent (roadmap)"
status: backlog
priority: low
type: spike
estimate: 16h
assignee: @unassigned
created: 2025-12-10
updated: 2025-12-10
parents: [TASK-2025-003]
children: [TASK-2025-066, TASK-2025-067]
arch_refs: [ARCH-agent-moex-market-analyst]
risk: medium
benefit: "Определяет контракт и стратегию интеграции вынесенного Planner Agent с fallback в basic-планировщик."
audit_log:
  - {date: 2025-12-10, user: "@AI-DocArchitect", action: "created with status backlog"}
---

## Описание

Спроектировать и задокументировать внешний Planner Agent (A2A-сервис), которому агент может делегировать построение плана, а также реализовать стратегию `ExternalAgentPlanningStrategy` с fallback в `BasicPlanningStrategy` при ошибках/тайм-ауте.

## Критерии приемки

- Подготовлена спецификация Planner Agent (отдельный документ/раздел SPEC), описывающая:
  - входные данные: `user_query`, список tools из `ToolRegistry`, метаданные ScenarioTemplates, `planner.limits`, (опционально) информацию о размере портфеля (`num_tickers`, `MAX_TICKERS_PER_REQUEST`);
  - выход: `Plan` (в формате, совместимом с внутренней моделью агента) и комментарий по сценарию/деградации (например, «ограничено top-10 тикерами»).
- Реализована стратегия `ExternalAgentPlanningStrategy`, которая:
  - по `PLANNER_MODE=external_agent` вызывает внешний Planner Agent по A2A/A2A-подобному контракту;
  - конвертирует его ответ в внутреннюю модель `Plan`/`PlannedStep`;
  - при ошибках/тайм-ауте, несоблюдении лимитов или некорректном плане логирует проблему и аккуратно переключается на `BasicPlanningStrategy`.
- Для external-режима предусмотрены фиче-флаг/конфигурация и защитные ограничения (тайм-ауты, максимальный размер передаваемого контекста), описанные в REQUIREMENTS/ARCHITECTURE.
- Есть прототиповый интеграционный тест с моковым Planner Agent, демонстрирующий успешное построение плана через внешний сервис и корректный fallback в basic при имитированной ошибке.

## Определение готовности

- В архитектурных документах и коде агента зафиксирован чёткий контракт взаимодействия с вынесенным Planner Agent и стратегия его использования.
- Включение `PLANNER_MODE=external_agent` в dev-окружении позволяет отладить цепочку делегирования и fallback, не ломая основной basic-режим.

## Заметки

Фаза PD — roadmap-пункт после хакатона; основная цель на текущем этапе — спецификация и минимальный каркас, а не полноценная прод-реализация внешнего агента.
