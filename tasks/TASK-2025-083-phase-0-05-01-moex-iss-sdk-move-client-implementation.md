---
id: TASK-2025-083
title: "Фаза 0.5.1. Перенос реализации IssClient в moex_iss_sdk"
status: backlog
priority: high
type: feature
estimate: 8h
assignee: @unassigned
created: 2025-12-10
updated: 2025-12-10
parents: [TASK-2025-074]
arch_refs: [ARCH-sdk-moex-iss, ARCH-mcp-moex-iss]
risk: medium
benefit: "Выделяет HTTP-клиент MOEX ISS в общий пакет moex_iss_sdk, устраняя дублирование кода и упрощая сопровождение."
audit_log:
  - {date: 2025-12-10, user: "@AI-DocArchitect", action: "created with status backlog"}
---

## Описание

Перенести существующую реализацию HTTP-клиента MOEX ISS из пакета
`moex_iss_mcp.iss` в модуль `moex_iss_sdk.client`, адаптировав её под
интерфейс `IssClient`, определённый в `TASK-2025-082`.

Необходимо вынести логику построения URL, параметров запросов,
обработки HTTP-ответов и базовых ретраев, сохранив текущее поведение
MCP при обращении к ISS.

## Критерии приемки

- В `moex_iss_sdk.client` реализован класс `IssClient`, использующий
  HTTP-клиент (например, `httpx`/`requests`) для вызовов MOEX ISS
  с учётом настроек `MOEX_ISS_BASE_URL`, `MOEX_ISS_TIMEOUT_SECONDS`
  и `MOEX_ISS_RATE_LIMIT_RPS` (без кэша и расширенных исключений —
  они реализуются в других задачах).
- Старый модуль клиента ISS в `moex-iss-mcp` либо удалён, либо сводится
  к тонкой обёртке вокруг `moex_iss_sdk.IssClient` (без собственной
  сетевой логики).
- Существующие тесты формирования URL и базовой обработки ответов
  адаптированы к новому расположению кода (в SDK) и проходят успешно.

## Определение готовности

- Поиск по репозиторию показывает, что HTTP-вызовы к MOEX ISS
  сконцентрированы в `moex_iss_sdk.client.IssClient`.
- Поведение MCP по успешным и ошибочным запросам ISS не изменилось
  (по результатам smoke-тестов и сравнения ответов).

## Заметки

- Поддержку кэша и расширенных исключений следует реализовывать в
  рамках задач `TASK-2025-075`, `TASK-2025-086`–`TASK-2025-088`.

