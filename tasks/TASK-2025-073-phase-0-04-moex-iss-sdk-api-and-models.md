---
id: TASK-2025-073
title: "Фаза 0.4. Проектирование API moex_iss_sdk"
status: done
priority: high
type: feature
estimate: 12h
assignee: @unassigned
created: 2025-12-10
updated: 2025-06-06
parents: [TASK-2025-002]
children: [TASK-2025-080, TASK-2025-081, TASK-2025-082]
arch_refs: [ARCH-sdk-moex-iss, ARCH-mcp-moex-iss]
risk: medium
benefit: "Определяет единый, стабильный API IssClient и модели данных, убирая дублирование HTTP-клиентов MOEX ISS в MCP."
audit_log:
  - {date: 2025-12-10, user: "@AI-DocArchitect", action: "created with status backlog"}
  - {date: 2025-06-06, user: "@AI-Codex", action: "status changed to done"}
---

## Описание

Спроектировать публичный интерфейс `moex_iss_sdk.IssClient` и набор
основных Pydantic-моделей (`SecuritySnapshot`, `OhlcvBar`,
`IndexConstituent`, `DividendRecord`), на которые будут опираться
MCP-серверы `moex-iss-mcp` и `risk-analytics-mcp`.

Задача соответствует пункту 0.1 плана архитектора («Спроектировать API
moex_iss_sdk»).

## Критерии приемки

- В репозитории создан пакет `moex_iss_sdk` с файлами `__init__.py`,
  `client.py`, `models.py`, `endpoints.py`, `exceptions.py`,
  `utils.py` (без обязательной полной реализации логики).
- Определён и задокументирован (docstring + type hints) публичный
  интерфейс `IssClient` с методами как минимум:
  - `get_security_snapshot(ticker, board) -> SecuritySnapshot`;
  - `get_ohlcv_series(ticker, board, from_date, to_date, interval) -> list[OhlcvBar]`;
  - `get_index_constituents(index_ticker, as_of_date) -> list[IndexConstituent]`;
  - `get_security_dividends(ticker, from_date, to_date) -> list[DividendRecord]`.
- Pydantic-модели для указанных сущностей определены и покрывают поля,
  необходимые текущему SPEC MCP (`SPEC_moex-iss-mcp.md`) и плану
  по `risk-analytics-mcp`.
- Сформированы базовые докстринги и комментарии, объясняющие назначение
  методов и моделей, чтобы остальные задачи могли опираться на этот API
  без изменений контракта.

## Определение готовности

- Команда MCP подтверждает, что интерфейс `IssClient` и модели данных
  покрывают все потребности текущих и ближайших задач по MCP.
- Задачи по реализации клиента, кэша и исключений (`TASK-2025-074`,
  `TASK-2025-075`) могут выполняться, не меняя публичные сигнатуры
  методов и имена моделей.

## Заметки

- Конкретные детали реализации HTTP-запросов, кэша и обработки ошибок
  выносятся в следующие задачи фазы 0 (`TASK-2025-074`,
  `TASK-2025-075`).
- При необходимости расширения API в будущем рекомендуется добавлять
  новые методы, не изменяя уже использующиеся сигнатуры.
