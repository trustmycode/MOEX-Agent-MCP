# TASK-2025-109: SPEC и tools.json для issuer_peers_compare

## Статус

- Статус: done
- Приоритет: P0.5
- Компонент: risk-analytics-mcp
- Связанные сценарии: issuer_peers_compare (5)

## Контекст

Инструмент `issuer_peers_compare` (TASK-2025-108) должен быть доступен
агенту и другим системам через единый MCP-контракт. Для этого необходимо
формально описать его входы/выходы в SPEC-документации и добавить
описание в `tools.json` для `risk-analytics-mcp`, по аналогии с уже
существующими инструментами (`compute_portfolio_risk_basic`,
`compute_correlation_matrix`, TASK-2025-079).

Без отдельной задачи на SPEC и `tools.json` высок риск рассинхронизации
между кодом, документацией и конфигурацией MCP в Evolution AI Agents.

## Цель

Сформализовать контракт MCP-инструмента `issuer_peers_compare` в виде
JSON Schema и записей в `tools.json`, чтобы агент мог использовать его
через `ToolRegistry` и платформа Evolution AI Agents — регистрировать и
валидировать MCP без ручных правок.

## Объём работ

### In scope

- Подготовка JSON Schema для входа `IssuerPeersCompareInput`:
  - идентификаторы эмитента (одно или несколько полей: `ticker`, `isin`, `issuer_id`);
  - опциональные фильтры (сектор/отрасль, индекс, `max_peers`);
  - базовые ограничения и валидация (обязательность хотя бы одного идентификатора, диапазон `max_peers`).

- Подготовка JSON Schema для выхода `IssuerPeersCompareReport`:
  - секция `metadata` (идентификаторы базового эмитента, источник данных, период/дата отчётности);
  - секция `base_issuer` (ключевые фундаментальные и рыночные метрики);
  - секция `peers[]` (массив строк с аналогичным набором полей);
  - секция `ranking`/`percentiles` (для ключевых метрик);
  - секция `flags[]` (overvalued/undervalued, high_leverage и др. — при наличии);
  - секция `error` (совместимая с общими правилами `error_type` в MCP).

- Обновление SPEC-документации для `risk-analytics-mcp`:
  - отдельный подраздел, описывающий назначение `issuer_peers_compare`,
    его входы/выходы и примеры JSON-запроса/ответа;
  - описание поддерживаемых значений `error_type` для этого инструмента
    (`INVALID_TICKER`, `NO_PEERS_FOUND`, `NO_FUNDAMENTAL_DATA`, `UNKNOWN`).

- Обновление `tools.json` для `risk-analytics-mcp`:
  - добавление записи с полями `name`, `description` (EN),
    `input_schema`, `output_schema` для `issuer_peers_compare`;
  - проверка формата и, по возможности, валидация средствами платформы
    Evolution AI Agents или локального валидатора схем.

### Out of scope

- Реализация самой бизнес-логики `issuer_peers_compare` (это задача
  TASK-2025-108).
- Расширенные варианты отчёта (например, разные режимы группировки или
  сложные многоуровневые структуры данных) — в MVP достаточно одного
  согласованного формата отчёта.

## Acceptance Criteria

- [x] В SPEC-документе для `risk-analytics-mcp` (или отдельном разделе)
      задокументированы JSON Schema `IssuerPeersCompareInput` и
      `IssuerPeersCompareReport`, включая описания полей и примеры.
- [x] В `tools.json` для `risk-analytics-mcp` добавлена запись
      `issuer_peers_compare` с корректными ссылками на схемы входа/выхода
      и понятным EN-описанием назначения инструмента.
- [x] Локальная или платформенная валидация `tools.json` проходит без
      ошибок; MCP можно зарегистрировать в Evolution AI Agents без
      ручных правок по этому инструменту.
- [x] Агент (через `ToolRegistry` или аналог) может получить метаданные
      `issuer_peers_compare` из `tools.json` и использовать их при
      планировании сценария 5.

## Зависимости и связи

- Зависит от:
  - TASK-2025-079 — общая SPEC и `tools.json` для `risk-analytics-mcp`.
  - TASK-2025-108 — определение доменной модели входа/выхода на уровне
    Pydantic (фактические поля могут подсказывать структуру схем).
- Поддерживает:
  - TASK-2025-104 — планировщик P0 по сценарию 5 (использует схемы
    для построения `ScenarioTemplate`).
  - TASK-2025-107 — демо-сценарии и сторителлинг по issuer_peers_compare.
