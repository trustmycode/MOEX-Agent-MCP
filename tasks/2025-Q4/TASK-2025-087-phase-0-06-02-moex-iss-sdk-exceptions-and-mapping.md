---
id: TASK-2025-087
title: "Фаза 0.6.2. Исключения moex_iss_sdk и маппинг ошибок для MCP"
status: backlog
priority: high
type: feature
estimate: 6h
assignee: @unassigned
created: 2025-12-10
updated: 2025-12-10
parents: [TASK-2025-075]
arch_refs: [ARCH-sdk-moex-iss, ARCH-mcp-moex-iss]
risk: medium
benefit: "Вводит нормализованный набор исключений SDK и единый маппинг в error_type MCP, упрощая обработку ошибок."
audit_log:
  - {date: 2025-12-10, user: "@AI-DocArchitect", action: "created with status backlog"}
---

## Описание

Определить и реализовать специализированные исключения в
`moex_iss_sdk.exceptions` (`InvalidTickerError`,
`DateRangeTooLargeError`, `TooManyTickersError`, `IssTimeoutError`,
`IssServerError`, `UnknownIssError`) и настроить маппинг этих
исключений в `ToolErrorModel.error_type` на стороне MCP.

## Критерии приемки

- В `moex_iss_sdk.exceptions` объявлены перечисленные классы
  исключений с понятными сообщениями и, при необходимости, полем
  `details`.
- `IssClient` выбрасывает соответствующие исключения SDK при:
  - неверном тикере или борде;
  - превышении допустимого диапазона дат;
  - превышении лимита по количеству тикеров;
  - тайм-ауте запроса;
  - ответах 5xx или непредвиденных ошибках.
- В `moex-iss-mcp` и `risk-analytics-mcp` реализован `ErrorMapper`,
  который конвертирует исключения SDK в значения `error_type`
  (`INVALID_TICKER`, `DATE_RANGE_TOO_LARGE`, `TOO_MANY_TICKERS`,
  `ISS_TIMEOUT`, `ISS_5XX`, `UNKNOWN`) в `ToolErrorModel`.

## Определение готовности

- Интеграционные тесты для типовых негативных сценариев (ошибки
  тикера, диапазона дат, тайм-аут) подтверждают корректную
  классификацию ошибок на уровне MCP.

## Заметки

- Детальные требования к ошибкам по датам и индексам задаются
  задачами фазы 0 (`TASK-2025-010`, `TASK-2025-011`) и должны
  учитываться при реализации маппинга.

