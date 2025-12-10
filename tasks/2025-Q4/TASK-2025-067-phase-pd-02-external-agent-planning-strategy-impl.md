---
id: TASK-2025-067
title: "Фаза PD.2. ExternalAgentPlanningStrategy и fallback"
status: backlog
priority: low
type: feature
estimate: 8h
assignee: @unassigned
created: 2025-12-10
updated: 2025-12-10
parents: [TASK-2025-050]
arch_refs: [ARCH-agent-moex-market-analyst]
risk: medium
benefit: "Добавляет стратегию планировщика, делегирующую построение плана внешнему Planner Agent с безопасным fallback в basic."
audit_log:
  - {date: 2025-12-10, user: "@AI-DocArchitect", action: "created with status backlog"}
---

## Описание

Реализовать стратегию `ExternalAgentPlanningStrategy`, которая по конфигурации делегирует построение плана внешнему Planner Agent по A2A-контракту, и обеспечить корректный fallback в `BasicPlanningStrategy` при ошибках или тайм-аутах внешнего сервиса.

## Критерии приемки

- Реализован класс `ExternalAgentPlanningStrategy`, использующий спецификацию из задачи PD.1 для формирования запросов к внешнему Planner Agent и преобразования его ответа во внутреннюю модель `Plan`.
- В конфигурации предусмотрены настройки внешнего Planner Agent (URL, тайм-ауты, аутентификация) и фиче-флаг/режим `PLANNER_MODE=external_agent`.
- При недоступности внешнего Planner Agent, тайм-ауте, нарушении контракта или некорректном плане стратегия:
  - логирует проблему и увеличивает соответствующие метрики;
  - возвращает управление `BasicPlanningStrategy`, которая строит план локально.
- Существуют интеграционные тесты с моковым Planner Agent, демонстрирующие успешный путь делегирования и путь fallback.

## Определение готовности

- Режим `PLANNER_MODE=external_agent` может быть включён в dev-окружении без риска нарушить базовый сценарий: при любых проблемах внешнего сервиса система продолжает работать на basic-планировщике.

## Заметки

Эта функциональность относится к roadmap и может быть реализована частично (с моками) в рамках хакатона, с прицелом на последующее выведение в прод.
