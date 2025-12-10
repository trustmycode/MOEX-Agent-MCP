---
id: TASK-2025-072
title: "Фаза PE.5. ScenarioTemplate portfolio_stress_test и метрики"
status: backlog
priority: low
type: feature
estimate: 12h
assignee: @unassigned
created: 2025-12-10
updated: 2025-12-10
parents: [TASK-2025-051]
arch_refs: [ARCH-agent-moex-market-analyst, ARCH-mcp-moex-iss]
risk: medium
benefit: "Подготавливает сценарий portfolio_stress_test поверх будущих advanced risk MCP-инструментов и его метрики успеха."
audit_log:
  - {date: 2025-12-10, user: "@AI-DocArchitect", action: "created with status backlog"}
---

## Описание

Спроектировать ScenarioTemplate `portfolio_stress_test`, который будет использовать будущие MCP-инструменты расширенного риск-анализа для моделирования стресс-сценариев на портфеле и сравнения метрик до/после, а также описать метрики успеха этого сценария.

## Критерии приемки

- В документации и/или коде описан целевой ScenarioTemplate `portfolio_stress_test`:
  - ожидаемый вход (портфель, набор стресс-сценариев, опционально бенчмарк-индекс);
  - шаги сценария (выбор baseline, применение стресс-сценариев, сбор метрик, формирование отчёта);
  - связь с planned MCP-инструментами advanced-риска (`get_risk_factors`, `get_portfolio_var`, `get_stress_test_results`).
- Определены и задокументированы метрики успеха сценария `portfolio_stress_test` (например, скорость выполнения, информативность отчёта, корректность реакции на разные типы стрессов).
- Ясно помечено, что реализация ScenarioTemplate и соответствующих MCP-инструментов является roadmap-задачей и не входит в MVP.

## Определение готовности

- Команда понимает, как сценарий `portfolio_stress_test` будет строиться поверх существующей архитектуры планировщика и MCP, и какие доработки потребуются после появления advanced risk-инструментов.

## Заметки

Эта подзадача связывает работу фаз 6 (портфельные инструменты) и 7 (advanced-риски) с развитием подсистемы планировщика до уровня production-grade.
