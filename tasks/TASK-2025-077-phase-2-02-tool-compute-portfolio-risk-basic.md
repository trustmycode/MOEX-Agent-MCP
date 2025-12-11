---
id: TASK-2025-077
title: "Фаза 2.2. Tool compute_portfolio_risk_basic"
status: done
priority: high
type: feature
estimate: 24h
assignee: @unassigned
created: 2025-12-10
updated: 2025-12-10
parents: [TASK-2025-007]
children: [TASK-2025-092, TASK-2025-093, TASK-2025-094]
arch_refs: [ARCH-mcp-risk-analytics, ARCH-sdk-moex-iss]
risk: medium
benefit: "Добавляет базовый портфельный риск-анализ в отдельный MCP-сервер, разгружая агента и moex-iss-mcp."
audit_log:
  - {date: 2025-12-10, user: "@AI-DocArchitect", action: "created with status backlog"}
---

## Описание

Реализовать MCP-инструмент `compute_portfolio_risk_basic` в
`risk-analytics-mcp`, который по списку позиций и периоду рассчитывает
пер-инструментные и агрегированные метрики риска портфеля.

Задача соответствует пункту 2.2 плана архитектора.

## Критерии приемки

- Определены Pydantic-модели входа/выхода:
  - вход: массив `positions[{ticker, weight}]`, `from_date`,
    `to_date`, `rebalance` (`"buy_and_hold"` или `"monthly"`);
  - выход: `per_instrument[]`, `portfolio_metrics`,
    `concentration_metrics`, `error` (по аналогии с SPEC MCP).
- Инструмент использует `moex_iss_sdk.IssClient` для загрузки OHLCV по
  каждому тикеру и модуль `calculations` для:
  - расчёта рядов доходностей;
  - вычисления доходности и волатильности портфеля;
  - оценки max drawdown;
  - расчёта концентрационных показателей (top-N, HHI и т.п.).
- Реализована обработка типовых ошибок (неизвестный тикер, слишком
  длинный период, превышение лимитов по числу тикеров) с маппингом на
  `error_type` (`INVALID_TICKER`, `DATE_RANGE_TOO_LARGE`,
  `TOO_MANY_TICKERS`).
- Есть интеграционный тест с небольшим тестовым портфелем (5–10 бумаг),
  проверяющий, что возвращаемые метрики выглядят разумно и не содержат
  NaN/inf.

## Определение готовности

- Агент (или отдельный тестовый клиент) может вызвать
  `compute_portfolio_risk_basic` и получить структурированный ответ
  с портфельными метриками, пригодный для отображения в отчётах и UI.

## Заметки

- Расширенные метрики (VaR, stress-test, детальная beta) остаются в
  roadmap и описываются в задачах фазы 7 (`TASK-2025-043`,
  `TASK-2025-044`, `TASK-2025-072`).

