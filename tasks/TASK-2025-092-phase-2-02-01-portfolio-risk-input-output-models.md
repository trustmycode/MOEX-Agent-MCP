---
id: TASK-2025-092
title: "Фаза 2.2.1. Модели входа/выхода для compute_portfolio_risk_basic"
status: done
priority: high
type: feature
estimate: 6h
assignee: @unassigned
created: 2025-12-10
updated: 2025-12-10
parents: [TASK-2025-077]
arch_refs: [ARCH-mcp-risk-analytics, ARCH-sdk-moex-iss]
risk: medium
benefit: "Формализует контракт инструмента compute_portfolio_risk_basic через Pydantic-модели, согласованные с планируемым SPEC."
audit_log:
  - {date: 2025-12-10, user: "@AI-DocArchitect", action: "created with status backlog"}
  - {date: 2025-12-10, user: "@codex", action: "marked as done after model implementation and tests"}
---

## Описание

Определить Pydantic-модели входа и выхода для инструмента
`compute_portfolio_risk_basic` в `risk_analytics_mcp.models`, опираясь
на архитектурный план и требования к метрикам портфеля.

## Критерии приемки

- Созданы модели:
  - `PortfolioPositionsInput` (или аналог) с полями `positions[]`,
    `from_date`, `to_date`, `rebalance`;
  - `PortfolioRiskPerInstrument`, `PortfolioMetrics`,
    `ConcentrationMetrics`;
  - обёртка выходной модели с полями `per_instrument[]`,
    `portfolio_metrics`, `concentration_metrics`, `error`.
- Модели согласованы с черновым SPEC risk-analytics-mcp (будет
  оформлен в `TASK-2025-079`) и не противоречат общему стилю SPEC
  `moex-iss-mcp`.
- Добавлены базовые валидации (например, сумма весов, допустимые
  значения `rebalance`).

## Определение готовности

- Реализация инструмента (`TASK-2025-093`) может использовать модели
  без их изменений.

## Заметки

- При необходимости часть моделей может быть переиспользована в
  других инструментах портфельного анализа в будущем.
