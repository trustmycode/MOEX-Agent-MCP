---
id: TASK-2025-082
title: "Фаза 0.4.3. Интерфейс moex_iss_sdk.IssClient и документация"
status: backlog
priority: high
type: feature
estimate: 6h
assignee: @unassigned
created: 2025-12-10
updated: 2025-12-10
parents: [TASK-2025-073]
arch_refs: [ARCH-sdk-moex-iss, ARCH-mcp-moex-iss]
risk: medium
benefit: "Фиксирует стабильный интерфейс IssClient и базовую документацию по использованию moex_iss_sdk в MCP."
audit_log:
  - {date: 2025-12-10, user: "@AI-DocArchitect", action: "created with status backlog"}
---

## Описание

Спроектировать и задокументировать публичный интерфейс
`moex_iss_sdk.IssClient` в файле `client.py`, используя результаты
`TASK-2025-080` и модели из `TASK-2025-081`.

Необходимо определить сигнатуры методов, договориться о поведении по
умолчанию (тайм-ауты, базовый URL, кэширование) и оформить docstring'и
так, чтобы MCP-сервисы могли использовать SDK без чтения внутреннего
кода.

## Критерии приемки

- В `moex_iss_sdk/client.py` объявлен класс `IssClient` с методами
  как минимум:
  - `get_security_snapshot(ticker, board) -> SecuritySnapshot`;
  - `get_ohlcv_series(ticker, board, from_date, to_date, interval) -> list[OhlcvBar]`;
  - `get_index_constituents(index_ticker, as_of_date) -> list[IndexConstituent]`;
  - `get_security_dividends(ticker, from_date, to_date) -> list[DividendRecord]`.
- У методов есть docstring'и, описывающие:
  - назначение метода;
  - параметры и возвращаемые значения;
  - возможные исключения уровня SDK.
- В `ARCH-sdk-moex-iss-v1.md` при необходимости уточнён раздел
  «Поведение» в части публичных методов `IssClient`.

## Определение готовности

- Задачи `TASK-2025-074` и `TASK-2025-075` могут реализовывать логику
  клиента и кэша, не меняя сигнатуры методов `IssClient`.

## Заметки

- При проектировании интерфейса учитывать, что SDK может использоваться
  не только в MCP текущего репозитория, но и во внешних проектах.

