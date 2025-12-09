---
id: TASK-2025-015
title: "Фаза 1.4. Tool get_security_snapshot"
status: backlog
priority: high
type: feature
estimate: 16h
assignee: @unassigned
created: 2025-12-09
updated: 2025-12-09
parents: [TASK-2025-002]
arch_refs: [ARCH-mcp-moex-iss]
risk: medium
benefit: "Даёт агенту быстрый снимок инструмента (цена, изменение, ликвидность) через MCP."
audit_log:
  - {date: 2025-12-09, user: "@AI-DocArchitect", action: "created with status backlog"}
---

## Описание

Реализовать MCP-инструмент `get_security_snapshot` с Pydantic-моделями входа/выхода, валидацией тикера/борда и расчётом простой внутридневной метрики при наличии данных.

## Критерии приемки

- Определены Pydantic-модели `GetSecuritySnapshotInput` и `GetSecuritySnapshotOutput`, соответствующие JSON Schema в SPEC.
- Инструмент выполняет:
  - валидацию тикера и, при необходимости, борда;
  - вызов `IssClient.get_security_snapshot(...)`;
  - расчёт простой метрики (например, внутридневной волатильности) при наличии достаточных данных;
  - формирование `error` через `ErrorMapper` при любых сбоях.
- Интеграционный тест: валидный тикер/борд → заполненный `metadata` и `data`, `error = null`.

## Определение готовности

- Агент может вызывать `get_security_snapshot` и получать пригодные для отображения данные по инструменту.
- Поведение при ошибках ISS или невалидном тикере предсказуемо и описано в SPEC.

## Заметки

Задача конкретизирует пункт 1.4 плана архитектора (Фаза 1).

