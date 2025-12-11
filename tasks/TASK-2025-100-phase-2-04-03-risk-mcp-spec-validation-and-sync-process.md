---
id: TASK-2025-100
title: "Фаза 2.4.3. Валидация SPEC/tools.json и процесс синхронизации risk-analytics-mcp"
status: done
priority: medium
type: chore
estimate: 6h
assignee: @unassigned
created: 2025-12-10
updated: 2025-12-10
parents: [TASK-2025-079]
arch_refs: [ARCH-mcp-risk-analytics]
risk: low
benefit: "Обеспечивает согласованность Pydantic-моделей, JSON Schema и tools.json для risk-analytics-mcp и описывает процесс их обновления."
audit_log:
  - {date: 2025-12-10, user: "@AI-DocArchitect", action: "created with status backlog"}
  - {date: 2025-12-10, user: "@codex", action: "marked as done after documenting validation/sync process and adding schema/tools checks"}
---

## Описание

Проверить согласованность Pydantic-моделей, JSON Schema и `tools.json`
для `risk-analytics-mcp`, описать и задокументировать процесс их
синхронизации при изменениях в коде MCP.

## Критерии приемки

- Выполнена ручная или автоматизированная валидация:
  - соответствия JSON Schema Pydantic-моделям;
  - корректности ссылок в `tools.json` на схемы;
  - общего формата `tools.json` для платформы Evolution AI Agents.
- В SPEC или отдельной dev-документации описан процесс:
  - как вносить изменения в модели;
  - как обновлять JSON Schema и `tools.json`;
  - как проверять согласованность (набор команд/скриптов).

## Определение готовности

- Любое изменение моделей MCP может быть проведено по понятной процедуре
  без расхождений между кодом и артефактами для платформы.

## Заметки

- При наличии времени можно добавить простой скрипт/CI-проверку для
  автоматической валидации схем.
