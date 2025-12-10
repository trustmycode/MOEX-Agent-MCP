---
id: TASK-2025-062
title: "Фаза PC.1. Поле scenario_type в Plan и логирование"
status: backlog
priority: high
type: feature
estimate: 6h
assignee: @unassigned
created: 2025-12-10
updated: 2025-12-10
parents: [TASK-2025-049]
arch_refs: [ARCH-agent-moex-market-analyst]
risk: low
benefit: "Позволяет явно помечать сценарии плана (включая portfolio_risk) и использовать их в логах и метриках."
audit_log:
  - {date: 2025-12-10, user: "@AI-DocArchitect", action: "created with status backlog"}
---

## Описание

Расширить модель `Plan` полем `scenario_type` и обеспечить его заполнение и логирование для ключевых сценариев агента, чтобы телеметрия могла агрегировать статистику по типам сценариев.

## Критерии приемки

- В модели `Plan` добавлено поле `scenario_type` (строка или Enum) с документированными значениями: как минимум `single_security_overview`, `compare_securities`, `index_risk_scan`, `portfolio_risk`, `portfolio_risk_drill_down`.
- Planner при построении плана заполняет `scenario_type` исходя из распознанного намерения пользователя или выбранного `ScenarioTemplate`.
- `scenario_type` логируется в debug-выводе и телеметрии (см. метрики из задачи PA.3).
- В случае, когда сценарий не может быть распознан однозначно, допускается значение `unknown` или отсутствие поля, что также отражено в документации.

## Определение готовности

- В dev-окружении можно построить отчёт/графики по распределению запросов по `scenario_type`.
- Сценарии `portfolio_risk` и `portfolio_risk_drill_down` корректно помечаются своими типами в логах и метриках.

## Заметки

Поле `scenario_type` используется ScenarioTemplates и advanced-режимом для более точной настройки поведения планировщика и анализа качества.
