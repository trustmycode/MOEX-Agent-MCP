---
id: TASK-2025-074
title: "Фаза 0.5. Вынесение IssClient из moex-iss-mcp в moex_iss_sdk"
status: backlog
priority: high
type: feature
estimate: 16h
assignee: @unassigned
created: 2025-12-10
updated: 2025-12-10
parents: [TASK-2025-002]
children: [TASK-2025-083, TASK-2025-084, TASK-2025-085]
arch_refs: [ARCH-sdk-moex-iss, ARCH-mcp-moex-iss]
risk: medium
benefit: "Убирает дублирование HTTP-клиента MOEX ISS, перенося его реализацию в общий пакет moex_iss_sdk."
audit_log:
  - {date: 2025-12-10, user: "@AI-DocArchitect", action: "created with status backlog"}
---

## Описание

Перенести существующий HTTP-клиент MOEX ISS и логику rate limiting из
внутреннего пакета `moex-iss-mcp.iss` в `moex_iss_sdk.IssClient`,
а затем обновить все инструменты MCP так, чтобы они использовали
только SDK вместо прямого доступа к ISS.

Задача соответствует пункту 0.2 плана архитектора («Вынести существующий
ISS-клиент из moex-iss-mcp в SDK»).

## Критерии приемки

- В `moex_iss_sdk.client.IssClient` реализованы HTTP-вызовы к MOEX ISS
  (URL, параметры, парсинг JSON) с учётом настроек
  `MOEX_ISS_BASE_URL`, `MOEX_ISS_RATE_LIMIT_RPS`,
  `MOEX_ISS_TIMEOUT_SECONDS`.
- В `moex-iss-mcp` больше нет собственного клиента ISS: все обращения
  к ISS идут через `moex_iss_sdk.IssClient`.
- Unit-тесты для формирования URL и обработки типовых ответов/ошибок
  перенесены/добавлены в модуль SDK.
- Запуск MCP локально подтверждает, что инструменты
  `get_security_snapshot`, `get_ohlcv_timeseries`,
  `get_index_constituents_metrics` работают через SDK без регрессий по
  функциональности.

## Определение готовности

- Код `moex-iss-mcp` не содержит прямых HTTP-вызовов к ISS; поиск по
  репозиторию показывает использование только `moex_iss_sdk.IssClient`.
- Все существующие тесты MCP проходят после миграции на SDK.

## Заметки

- Если к моменту выполнения задачи клиент ISS ещё не реализован
  внутри MCP, реализация может быть сразу сделана в виде SDK, без
  промежуточного шага.

