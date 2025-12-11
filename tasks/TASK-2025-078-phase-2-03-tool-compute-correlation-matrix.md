---
id: TASK-2025-078
title: "Фаза 2.3. Tool compute_correlation_matrix"
status: done
priority: high
type: feature
estimate: 20h
assignee: @unassigned
created: 2025-12-10
updated: 2025-12-10
parents: [TASK-2025-007]
children: [TASK-2025-095, TASK-2025-096, TASK-2025-097]
arch_refs: [ARCH-mcp-risk-analytics, ARCH-sdk-moex-iss]
risk: medium
benefit: "Добавляет инструмент для расчёта матрицы корреляций между бумагами, используемый в сценариях portfolio_risk и drill-down."
audit_log:
  - {date: 2025-12-10, user: "@AI-DocArchitect", action: "created with status backlog"}
---

## Описание

Реализовать MCP-инструмент `compute_correlation_matrix` в
`risk-analytics-mcp`, который по списку тикеров и периоду строит
матрицу корреляций дневных доходностей.

Задача соответствует пункту 2.3 плана архитектора и входит в scope
хакатона как обязательная.

## Критерии приемки

- Определены Pydantic-модели входа/выхода:
  - вход: `tickers[]`, `from_date`, `to_date`;
  - выход: объект с полями `tickers[]`, `matrix[][]`, `metadata`,
    `error`.
- Введён лимит `MAX_TICKERS_FOR_CORRELATION` (например, 15–20 тикеров);
  при превышении инструмент возвращает нормализованную ошибку с
  `error_type = "TOO_MANY_TICKERS"` и человекочитаемым сообщением.
- Расчёт корреляций основан на дневных доходностях, полученных через
  `moex_iss_sdk.IssClient.get_ohlcv_series(...)` и модуль
  `calculations.correlation`.
- Интеграционный тест на 3–10 тикерах показывает корректную
  симметричную матрицу с единицами на диагонали и значениями в
  диапазоне [-1, 1].

## Определение готовности

- Сценарий агента `portfolio_risk_drill_down` может вызывать
  `compute_correlation_matrix` для top-N бумаг портфеля и использовать
  результат в отчётах.

## Заметки

- Для больших портфелей подсценарии и ограничения по числу тикеров
  описываются в задачах фазы PC (`TASK-2025-049`, `TASK-2025-064`).

