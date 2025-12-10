---
id: TASK-2025-025
title: "Фаза 2.6. ResponseFormatter"
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
benefit: "Формирует человекочитаемый текст ответа и таблицы на основе результатов MCP и (опционально) RAG."
audit_log:
  - {date: 2025-12-09, user: "@AI-DocArchitect", action: "created with status backlog"}
---

## Описание

Реализовать `ResponseFormatter`, который на основе `SessionContext.tool_results` и (опционально) RAG-данных строит поля `output.text`, `output.tables[]` и `output.debug`, не выдумывая чисел.

## Критерии приемки

- `build_final_response(ctx)`:
  - формирует промпт к LLM с включением необходимых числовых данных из MCP-ответов;
  - генерирует `output.text` с бизнес-ориентированным резюме на русском;
  - формирует одну или несколько таблиц `output.tables[]` с ключевыми метриками.
- Для сценария сравнения SBER/GAZP:
  - в ответе есть текстовое резюме и таблица с основными показателями по каждому тикеру;
  - данные в тексте и таблицах соответствуют числам из MCP-ответов.
- При включённом флаге debug формируется `output.debug` с планом и информацией о tool-вызовах.

## Определение готовности

- Результирующий JSON-ответ агента готов для отображения в UI и использования в отчётах.

## Заметки

Соответствует пункту 2.6 плана архитектора (Фаза 2).

