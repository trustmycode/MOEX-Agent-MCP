---
id: TASK-2025-110
title: "Risk Dashboard и DashboardSubagent"
status: backlog
priority: medium
type: feature
estimate: 24h
assignee: @unassigned
created: 2025-12-11
updated: 2025-12-11
parents: [TASK-2025-003, TASK-2025-006]
children: []
arch_refs: [ARCH-agent-moex-market-analyst]
risk: medium
benefit: "Даёт структурированный Risk Dashboard (JSON) для сценариев portfolio_risk и cfo_liquidity_report, готовый к использованию в Web-UI / AGI UI."
audit_log:
  - {date: 2025-12-11, user: "@AI-Codex", action: "created with status backlog"}
---

## Описание

Реализовать внутри агента `moex-market-analyst-agent` сабагент `DashboardSubagent`, который:

- принимает структурированный ответ `risk-analytics-mcp.compute_portfolio_risk_basic` (и в перспективе CFO-отчёта);
- маппит поля `per_instrument`, `portfolio_metrics`, `concentration_metrics`, `stress_results`, `var_light` в `RiskDashboardSpec` согласно `docs/SPEC_risk_dashboard_agi_ui.md`;
- добавляет `output.dashboard` в A2A-ответ агента и обеспечивает совместимость с Web-UI / AGI UI (backend tool rendering `type="risk_dashboard"`).

Фокус — реализация для сценариев 7/9 (`portfolio_risk`, `cfo_liquidity_report`) с возможностью дальнейшего расширения.

## Критерии приемки

- В коде агента реализован модуль/класс `DashboardSubagent` (или эквивалент), который:
  - принимает нормализованные данные от `RiskAnalyticsSubagent` (или thin-обёртки над MCP-ответами);
  - формирует объект `RiskDashboardSpec` строго в соответствии со схемой из `docs/SPEC_risk_dashboard_agi_ui.md`;
  - возвращает его в вызывающий слой без участия LLM.
- A2A-ответ агента расширен полем `output.dashboard`, заполненным для сценария `portfolio_risk` (минимум):
  - карточки ключевых метрик портфеля (доходность, волатильность, max drawdown, Var_light);
  - таблица позиций;
  - таблица стресс-сценариев;
  - alerts по концентрациям и Var_light.
- Web-UI (или простой тестовый клиент) может:
  - вызвать сценарий `portfolio_risk_basic`;
  - получить A2A-ответ и на основе `output.dashboard` отрисовать базовый Risk Cockpit (без дополнительной бизнес-логики, только через data_ref).
- Документация (ARCHITECTURE / SPEC_risk_dashboard_agi_ui.md) обновлена при необходимости и не противоречит фактической реализации.

## Определение готовности

- Для тестового портфеля вызов агента в сценарии `portfolio_risk_basic` возвращает:
  - корректный `output.text`;
  - заполненный `output.dashboard`, валидируемый по JSON Schema `RiskDashboardSpec`;
  - схему можно использовать в Web-UI без ручной доработки.
- Команда подтверждает, что Risk Dashboard покрывает ключевые потребности сценариев 7/9 и может быть расширен без ломающих изменений.

