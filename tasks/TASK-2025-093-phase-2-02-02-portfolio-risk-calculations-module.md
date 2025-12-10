---
id: TASK-2025-093
title: "Фаза 2.2.2. Модуль расчётов для compute_portfolio_risk_basic"
status: backlog
priority: high
type: feature
estimate: 8h
assignee: @unassigned
created: 2025-12-10
updated: 2025-12-10
parents: [TASK-2025-077]
arch_refs: [ARCH-mcp-risk-analytics, ARCH-sdk-moex-iss]
risk: medium
benefit: "Выделяет чистые функции расчёта доходностей, волатильности, max drawdown и концентрации для портфеля."
audit_log:
  - {date: 2025-12-10, user: "@AI-DocArchitect", action: "created with status backlog"}
---

## Описание

Реализовать в `risk_analytics_mcp.calculations` функции, выполняющие
основные численные расчёты для `compute_portfolio_risk_basic`:
ряды доходностей по тикерам, агрегирование портфельных доходностей,
расчёт волатильности, max drawdown и концентрационных метрик.

## Критерии приемки

- В модуле `returns.py` реализованы функции для построения рядов
  дневных доходностей по OHLCV-данным из `moex_iss_sdk`.
- В модуле `portfolio_metrics.py` реализованы функции для расчёта:
  - портфельной доходности за период;
  - волатильности портфеля;
  - max drawdown;
  - концентрационных показателей (top-N, HHI и т.п.).
- Функции принимают на вход структуры, построенные на базе моделей
  SDK (`OhlcvBar`) и входной модели портфеля, и не зависят от MCP.
- Написаны unit-тесты для расчётов на синтетических данных.

## Определение готовности

- Инструмент `compute_portfolio_risk_basic` (`TASK-2025-094`) может
  использовать модуль `calculations` как "чёрный ящик" для численных
  операций.

## Заметки

- Более сложные метрики (VaR, stress-test, advanced beta) планируются
  в задачах фазы 7 и могут расширять модуль расчётов в будущем.

