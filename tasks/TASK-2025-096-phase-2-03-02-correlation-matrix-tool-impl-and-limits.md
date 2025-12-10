---
id: TASK-2025-096
title: "Фаза 2.3.2. Реализация compute_correlation_matrix и лимиты по тикерам"
status: backlog
priority: high
type: feature
estimate: 8h
assignee: @unassigned
created: 2025-12-10
updated: 2025-12-10
parents: [TASK-2025-078]
arch_refs: [ARCH-mcp-risk-analytics, ARCH-sdk-moex-iss]
risk: medium
benefit: "Добавляет рабочий MCP-инструмент расчёта матрицы корреляций с контролем числа тикеров."
audit_log:
  - {date: 2025-12-10, user: "@AI-DocArchitect", action: "created with status backlog"}
---

## Описание

Реализовать tool-хендлер `compute_correlation_matrix` в
`risk_analytics_mcp.tools`, использующий `moex_iss_sdk.IssClient`
для загрузки OHLCV, модуль `correlation` (`TASK-2025-095`) для
расчёта матрицы и соблюдающий лимит `MAX_TICKERS_FOR_CORRELATION`.

## Критерии приемки

- Инструмент валидирует вход (`tickers[]`, `from_date`, `to_date`) и
  проверяет, что длина списка тикеров не превышает
  `MAX_TICKERS_FOR_CORRELATION`; при превышении возвращает ошибку
  с `error_type = "TOO_MANY_TICKERS"`.
- Для допустимого числа тикеров инструмент:
  - загружает OHLCV через `IssClient`;
  - строит ряды доходностей;
  - вызывает модуль `correlation` для построения матрицы;
  - возвращает `tickers[]`, `matrix[][]`, `metadata`, `error=null`.
- Интеграционный тест на 3–10 тикерах подтверждает корректную форму
  матрицы и отсутствие NaN/inf.

## Определение готовности

- Сценарий `portfolio_risk_drill_down` может использовать
  `compute_correlation_matrix` для анализа top-N бумаг портфеля.

## Заметки

- Конкретное значение лимита и поведение при больших портфелях
  согласуется с задачами фазы PC (`TASK-2025-064`).

