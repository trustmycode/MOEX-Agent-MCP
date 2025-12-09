---
id: TASK-2025-019
title: "Фаза 1.8. Синхронизация SPEC и tools.json"
status: backlog
priority: high
type: chore
estimate: 4h
assignee: @unassigned
created: 2025-12-09
updated: 2025-12-09
parents: [TASK-2025-002]
arch_refs: [ARCH-mcp-moex-iss]
risk: low
benefit: "Обеспечивает согласованность JSON Schema, SPEC и tools.json для регистрации MCP."
audit_log:
  - {date: 2025-12-09, user: "@AI-DocArchitect", action: "created with status backlog"}
---

## Описание

Привести SPEC и `tools.json` в соответствие с фактическими Pydantic-моделями и реализованными MCP-инструментами, подготовив артефакты к регистрации MCP в Evolution AI Agents.

## Критерии приемки

- JSON Schema во всех разделах SPEC совпадают с текущими моделями кода для:
  - `get_security_snapshot`;
  - `get_ohlcv_timeseries`;
  - `get_index_constituents_metrics`.
- Файл `tools.json` описывает все реализованные инструменты с корректными ссылками на схемы, описаниями (EN) и именами.
- Выполнена пробная валидация `tools.json` средствами платформы или схемой AI Agents (при доступности).

## Определение готовности

- MCP можно зарегистрировать в Evolution AI Agents без ручного исправления схем.
- Любые изменения моделей в будущем будут сопровождаться обновлением SPEC/`tools.json` по понятной процедуре.

## Заметки

Задача соответствует пункту 1.8 плана архитектора (Фаза 1).

