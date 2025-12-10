---
id: TASK-2025-039
title: "Фаза 6.1. Tool get_multi_ohlcv_timeseries"
status: backlog
priority: medium
type: feature
estimate: 24h
assignee: @unassigned
created: 2025-12-09
updated: 2025-12-09
parents: [TASK-2025-007]
arch_refs: [ARCH-mcp-moex-iss]
risk: medium
benefit: "Снижает количество MCP-вызовов при сравнении нескольких тикеров, улучшая производительность."
audit_log:
  - {date: 2025-12-09, user: "@AI-DocArchitect", action: "created with status backlog"}
---

## Описание

Реализовать MCP-инструмент `get_multi_ohlcv_timeseries`, принимающий список тикеров и параметры периода, возвращающий объединённый набор тайм-серий и метрик по каждому тикеру.

## Критерии приемки

- Определены входные/выходные модели: вход включает `tickers: [string]` (2–10), `board`, `from_date`, `to_date`, `interval`.
- Реализована валидация:
  - 2–10 тикеров;
  - корректный период и интервал;
  - лимит глубины истории.
- Инструмент выполняет параллельные/последовательные запросы к ISS с учётом rate limit и возвращает:
  - `data[ticker] = timeseries[]`;
  - `metrics[ticker] = {total_return_pct, volatility, avg_volume}`.
- Сценарий сравнения SBER, GAZP, LKOH выполняется одним MCP-вызовом.

## Определение готовности

- Planner может использовать инструмент для многотикерных сравнений без заметного усложнения логики.

## Заметки

Соответствует пункту 6.1 плана архитектора (Фаза 6).

