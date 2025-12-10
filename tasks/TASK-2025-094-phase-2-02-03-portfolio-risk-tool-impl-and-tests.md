---
id: TASK-2025-094
title: "Фаза 2.2.3. Реализация compute_portfolio_risk_basic и интеграционные тесты"
status: done
priority: high
type: feature
estimate: 10h
assignee: @unassigned
created: 2025-12-10
updated: 2025-12-10
parents: [TASK-2025-077]
arch_refs: [ARCH-mcp-risk-analytics, ARCH-sdk-moex-iss]
risk: medium
benefit: "Делает доступным MCP-инструмент базового портфельного риск-анализа для агента и сценариев portfolio_risk."
audit_log:
  - {date: 2025-12-10, user: "@AI-DocArchitect", action: "created with status backlog"}
  - {date: 2025-12-10, user: "@codex", action: "marked as done after tool implementation and integration tests"}
---

## Описание

Реализовать tool-хендлер `compute_portfolio_risk_basic` в
`risk_analytics_mcp.tools`, используя модели из `TASK-2025-092`,
расчёты из `TASK-2025-093` и `moex_iss_sdk.IssClient` для загрузки
OHLCV, а также написать интеграционные тесты с небольшим тестовым
портфелем.

## Критерии приемки

- Инструмент принимает входные данные через Pydantic-модель, валидирует
  их и загружает OHLCV по каждому тикеру через `IssClient`.
- Для валидного тестового портфеля (5–10 тикеров) инструмент возвращает
  осмысленные значения доходности, волатильности, max drawdown и
  концентрационных метрик без NaN/inf.
- Ошибочные сценарии (невалидные тикеры, слишком длинный период,
  превышение лимита по числу тикеров) корректно отражаются в поле
  `error` с соответствующим `error_type`.
- Интеграционные тесты поднимают MCP локально (или с заглушками данных)
  и проверяют ключевые инварианты ответа.

## Определение готовности

- Агент может вызывать `compute_portfolio_risk_basic` и использовать его
  результат в сценариях `portfolio_risk`/`portfolio_risk_drill_down`.

## Заметки

- Поддержка advanced-метрик (VaR, stress-test) не входит в объём
  данной задачи и оформляется отдельно фазой 7.
