---
id: TASK-2025-022
title: "Фаза 2.3. SessionContext"
status: backlog
priority: high
type: feature
estimate: 8h
assignee: @unassigned
created: 2025-12-09
updated: 2025-12-09
parents: [TASK-2025-003]
arch_refs: [ARCH-agent-moex-market-analyst]
risk: low
benefit: "Даёт единый объект для хранения контекста запроса, плана и результатов tools."
audit_log:
  - {date: 2025-12-09, user: "@AI-DocArchitect", action: "created with status backlog"}
---

## Описание

Реализовать `SessionContext`, который хранит ключевую информацию о запросе пользователя и промежуточных результатах, и обеспечить корректный маппинг из A2A-входа.

## Критерии приемки

- `SessionContext` содержит поля:
  - `user_query`, `locale`, `user_role`;
  - временные метки (`started_at`, `finished_at` при необходимости);
  - `plan`, `tool_results`, список ошибок;
  - технический контекст (ID запроса и т.п. при необходимости).
- Реализован метод `SessionContext.from_a2a(input: A2AInput)`.
- Добавлены unit-тесты, проверяющие корректный перенос данных из A2A-модели в контекст (включая `metadata`).

## Определение готовности

- Все внутренние компоненты агента используют `SessionContext` для обмена данными, не завися от конкретного формата A2A.

## Заметки

Декомпозиция пункта 2.3 плана архитектора (Фаза 2).

