---
id: TASK-2025-063
title: "Фаза PC.2. ScenarioTemplate для базовых сценариев"
status: backlog
priority: high
type: feature
estimate: 12h
assignee: @unassigned
created: 2025-12-10
updated: 2025-12-10
parents: [TASK-2025-049]
arch_refs: [ARCH-agent-moex-market-analyst, ARCH-mcp-moex-iss]
risk: medium
benefit: "Оформляет ключевые сценарии агента как формальные Python-шаблоны с предсказуемыми планами."
audit_log:
  - {date: 2025-12-10, user: "@AI-DocArchitect", action: "created with status backlog"}
---

## Описание

Ввести абстракцию `ScenarioTemplate` и реализовать шаблоны для сценариев `compare_securities` и `index_risk_scan`, а также базовый вариант `portfolio_risk` без поддержки больших портфелей, чтобы планы для этих сценариев были формализованы и легко тестируемы.

## Критерии приемки

- Определён интерфейс/базовый класс `ScenarioTemplate`, отвечающий за построение типового `Plan` по входному контексту (`SessionContext`, распарсенный запрос и т.п.).
- Реализованы шаблоны:
  - `CompareSecuritiesScenarioTemplate` — шаги `get_ohlcv_timeseries`/`get_multi_ohlcv_timeseries` по каждому тикеру → агрегация результатов → финальная LLM-генерация отчёта;
  - `IndexRiskScanScenarioTemplate` — `get_index_constituents_metrics` (и, при необходимости, дополнительные запросы) → вычисление агрегатов → финальная генерация отчёта;
  - базовый `PortfolioRiskScenarioTemplate` для портфелей, не превышающих `MAX_TICKERS_PER_REQUEST`.
- Planner при распознавании соответствующего сценария делегирует построение плана выбранному `ScenarioTemplate`.
- Для каждого шаблона есть unit-/интеграционные тесты, проверяющие структуру генерируемого плана.

## Определение готовности

- Планы для ключевых сценариев становятся стабильными и предсказуемыми, а изменения ScenarioTemplates отслеживаются тестами.
- Поддержка больших портфелей для `portfolio_risk` выносится в отдельную подзадачу (PC.3).

## Заметки

Дальнейшая доработка `portfolio_risk` для больших портфелей и сценарий `portfolio_risk_drill_down` реализуются в соседних подзадачах фазы PC.
