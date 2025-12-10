---
id: TASK-2025-084
title: "Фаза 0.5.2. Интеграция moex_iss_sdk в moex-iss-mcp"
status: backlog
priority: high
type: feature
estimate: 6h
assignee: @unassigned
created: 2025-12-10
updated: 2025-12-10
parents: [TASK-2025-074]
arch_refs: [ARCH-sdk-moex-iss, ARCH-mcp-moex-iss]
risk: medium
benefit: "Переводит инструменты moex-iss-mcp на использование общего IssClient из moex_iss_sdk."
audit_log:
  - {date: 2025-12-10, user: "@AI-DocArchitect", action: "created with status backlog"}
---

## Описание

Заменить использование внутреннего клиента ISS в `moex-iss-mcp` на
`moex_iss_sdk.IssClient` во всех местах, где MCP-инструменты обращаются
к MOEX ISS.

Необходимо скорректировать инициализацию клиента (конфиг, DI) и
передачу зависимостей в обработчики tools, не меняя их внешнего
контракта.

## Критерии приемки

- Все инструменты MCP (`get_security_snapshot`,
  `get_ohlcv_timeseries`, `get_index_constituents_metrics`) получают
  данные через `moex_iss_sdk.IssClient`.
- Конфигурация `McpConfig` создаёт и передаёт экземпляр `IssClient`
  с использованием тех же переменных окружения, что и раньше
  (`MOEX_ISS_BASE_URL`, `MOEX_ISS_TIMEOUT_SECONDS`,
  `MOEX_ISS_RATE_LIMIT_RPS`).
- Локальный запуск MCP и существующие интеграционные тесты подтверждают,
  что функциональность инструментов не изменилась.

## Определение готовности

- В коде `moex-iss-mcp` отсутствуют прямые обращения к старому клиенту
  ISS; все вызовы проходят через SDK.

## Заметки

- Маппинг исключений SDK в `ToolErrorModel` реализуется и тестируется в
  задачах фазы 0.6 (`TASK-2025-075`, `TASK-2025-086`–`TASK-2025-088`).

