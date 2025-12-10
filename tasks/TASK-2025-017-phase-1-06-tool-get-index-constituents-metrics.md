---
id: TASK-2025-017
title: "Фаза 1.6. Tool get_index_constituents_metrics"
status: done
priority: high
type: feature
estimate: 24h
assignee: @unassigned
created: 2025-12-09
updated: 2025-12-10
parents: [TASK-2025-002]
arch_refs: [ARCH-mcp-moex-iss]
risk: medium
benefit: "Позволяет анализировать состав индекса и основные риски по бумагам через MCP."
audit_log:
  - {date: 2025-12-09, user: "@AI-DocArchitect", action: "created with status backlog"}
  - {date: 2025-12-10, user: "@assistant", action: "marked as done"}
---

## Описание

Реализовать MCP-инструмент `get_index_constituents_metrics`, который по тикеру индекса и дате возвращает состав индекса и агрегированные показатели по бумагам и всему индексу.

## Критерии приемки

- Определены Pydantic-модели входа/выхода, согласованные с JSON Schema в SPEC.
- Инструмент выполняет:
  - маппинг `index_ticker` в внутренний `indexid` с использованием кэша;
  - запрос состава индекса и базовой аналитики через `IssClient`;
  - формирование `data[]` с полями `{ticker, weight_pct, last_price, price_change_pct, sector}`;
  - расчёт `metrics.top5_weight_pct` и `metrics.num_constituents`.
- Интеграционный тест для `IMOEX` на рабочую дату:
  - `data` не пусто;
  - `num_constituents > 0`;
  - `top5_weight_pct` находится в реалистичном диапазоне.

## Определение готовности

- Агент может использовать инструмент для сценариев анализа индекса и подсветки концентрационных рисков.
- Поведение при неизвестном индексе соответствует ошибке `UNKNOWN_INDEX`.

## Заметки

Декомпозиция пункта 1.6 плана архитектора (Фаза 1).
