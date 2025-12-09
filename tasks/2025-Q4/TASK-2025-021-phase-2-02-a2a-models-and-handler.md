---
id: TASK-2025-021
title: "Фаза 2.2. A2A-модели и A2ARequestHandler"
status: backlog
priority: high
type: feature
estimate: 16h
assignee: @unassigned
created: 2025-12-09
updated: 2025-12-09
parents: [TASK-2025-003]
arch_refs: [ARCH-agent-moex-market-analyst]
risk: medium
benefit: "Формализует вход/выход агента по протоколу A2A и точку входа обработки запросов."
audit_log:
  - {date: 2025-12-09, user: "@AI-DocArchitect", action: "created with status backlog"}
---

## Описание

Определить Pydantic-модели `A2AInput` и `A2AOutput` по JSON Schema из SPEC и реализовать обработчик `A2ARequestHandler.handle_request`, который валидирует вход, создаёт `SessionContext` и передаёт управление в core-сервис агента.

## Критерии приемки

- Модели `A2AInput`/`A2AOutput` соответствуют A2A JSON Schema (вход: `input.messages[]`, `metadata`; выход: `output.text`, `output.tables[]`, `output.debug`).
- `A2ARequestHandler.handle_request(...)` выполняет:
  - валидацию входа и формирование понятных ошибок при некорректном JSON;
  - преобразование данных в `SessionContext.from_a2a(...)`;
  - вызов основного сервиса агента;
  - логирование входа/выхода в адаптер телеметрии (без секретов).
- Есть локальный endpoint, который принимает/отдаёт A2A JSON и проходит валидацию против схем.

## Определение готовности

- Любой внешний клиент AI Agents может вызывать агента по A2A-контракту, опираясь на схемы.
- A2A-слой изолирован от бизнес-логики агента и легко тестируется.

## Заметки

Задача конкретизирует пункт 2.2 плана архитектора (Фаза 2).

