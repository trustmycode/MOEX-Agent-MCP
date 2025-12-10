---
id: TASK-2025-097
title: "Фаза 2.3.3. Тесты и обработка ошибок для compute_correlation_matrix"
status: backlog
priority: medium
type: chore
estimate: 6h
assignee: @unassigned
created: 2025-12-10
updated: 2025-12-10
parents: [TASK-2025-078]
arch_refs: [ARCH-mcp-risk-analytics, ARCH-sdk-moex-iss]
risk: low
benefit: "Гарантирует предсказуемое поведение compute_correlation_matrix в ошибочных сценариях и покрытие тестами."
audit_log:
  - {date: 2025-12-10, user: "@AI-DocArchitect", action: "created with status backlog"}
---

## Описание

Расширить набор тестов для `compute_correlation_matrix`, покрыв
ошибочные сценарии (невалидные тикеры, проблемы с данными, превышение
лимита по числу тикеров) и убедиться, что инструмент всегда возвращает
структурированные ошибки.

## Критерии приемки

- Добавлены тесты, проверяющие:
  - поведение при `MAX_TICKERS_FOR_CORRELATION + 1` тикерах;
  - реакцию на исключения SDK (например, `InvalidTickerError`,
    `DateRangeTooLargeError`, `IssTimeoutError`);
  - корректную обработку ситуаций с недостаточным числом наблюдений
    для оценки корреляции.
- В коде инструмента при ошибках из SDK и расчётов гарантированно
  формируется объект `error` с `error_type` и человекочитаемым
  `message`, а матрица либо пустая, либо опущена.

## Определение готовности

- Любое изменение поведения инструмента в ошибочных сценариях будет
  обнаружено тестами, а сценарии деградации поведения задокументированы.

## Заметки

- Детали текстов ошибок могут быть уточнены в SPEC risk-analytics-mcp
  (`TASK-2025-079`).

