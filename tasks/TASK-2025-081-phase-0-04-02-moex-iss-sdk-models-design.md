---
id: TASK-2025-081
title: "Фаза 0.4.2. Проектирование моделей moex_iss_sdk.models"
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
benefit: "Формирует единый набор Pydantic-моделей для работы с данными MOEX ISS в MCP и risk-analytics-mcp."
audit_log:
  - {date: 2025-12-10, user: "@AI-DocArchitect", action: "created with status backlog"}
---

## Описание

Спроектировать Pydantic-модели в модуле `moex_iss_sdk.models` для
ключевых сущностей (`SecuritySnapshot`, `OhlcvBar`,
`IndexConstituent`, `DividendRecord` и др.), опираясь на выводы
`TASK-2025-080` и текущий SPEC MCP.

Модели должны покрывать все поля, реально используемые доменной
логикой MCP и планируемым `risk-analytics-mcp`, но при этом оставаться
устойчивыми к расширению ISS-ответов.

## Критерии приемки

- В файле `moex_iss_sdk/models.py` определены и задокументированы
  Pydantic-модели:
  - `SecuritySnapshot`;
  - `OhlcvBar`;
  - `IndexConstituent`;
  - `DividendRecord`;
  - при необходимости дополнительные вспомогательные типы.
- Поля моделей согласованы с JSON Schema из
  `docs/SPEC_moex-iss-mcp.md` (имена и типы полей не противоречат
  SPEC).
- Модели используются в черновых сигнатурах методов `IssClient` в
  `client.py` (без полной реализации логики).

## Определение готовности

- Задачи `TASK-2025-074` и `TASK-2025-075` могут использовать модели
  из `moex_iss_sdk.models` без необходимости добавлять новые типы под
  уже описанные в SPEC сценарии.

## Заметки

- При проектировании учитывать, что те же модели будут использоваться
  и в `risk-analytics-mcp` для построения портфельных рядов и
  расчёта корреляций.

