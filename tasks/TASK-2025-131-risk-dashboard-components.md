---
id: TASK-2025-131
title: "Библиотека компонентов Risk Dashboard (Generative UI)"
status: backlog
priority: high
type: feature
estimate: 16h
assignee: @unassigned
created: 2025-12-12
updated: 2025-12-12
parents: [TASK-2025-130]
children: [TASK-2025-132]
arch_refs: [SPEC_risk_dashboard_agi_ui]
risk: medium
benefit: "Набор 'глупых' React-компонентов, которые умеют рендерить JSON-схему RiskDashboardSpec."
audit_log:
  - {date: 2025-12-12, user: "@AI-Architect", action: "created"}
---

## Описание

Реализовать набор React-компонентов, соответствующих спецификации `RiskDashboardSpec`. Эти компоненты будут использоваться системой Generative UI для отрисовки ответа агента.

## Контекст

Агент (`DashboardSubagent`) возвращает JSON. Фронтенд должен превратить этот JSON в красивый дашборд. Мы используем подход "Slot-based" или "Component Map": JSON говорит "покажи график типа bar", мы рендерим компонент `BarChart`.

## Ссылки на документацию фреймворков

https://docs.ag-ui.com/introduction
https://docs.ag-ui.com/drafts/generative-ui
https://www.copilotkit.ai/

## Критерии приёмки

### Базовые компоненты
- [ ] `MetricCard`: отображает title, value, unit, change, и цвет в зависимости от severity (info/warning/critical).
- [ ] `AlertBlock`: отображает список предупреждений с иконками.
- [ ] `RiskTable`: универсальная таблица, принимающая `columns` и `rows` из спецификации.

### Графики (используя Recharts или Tremor)
- [ ] `EquityChart`: Линейный график стоимости портфеля.
- [ ] `AllocationChart`: Bar chart или Pie chart для весов/секторов.

### Композитный компонент (RiskCockpit)
- [ ] Реализован компонент `RiskCockpit`, который принимает проп `data: RiskDashboardSpec`.
- [ ] Логика layout:
  - Сверху: `metadata` (дата, валюта).
  - Далее: Grid из `MetricCards`.
  - Далее: `Alerts` (если есть).
  - Далее: Графики и Таблицы (в 2 колонки или табы).

### Storybook / Test Page
- [ ] Создана тестовая страница с захардкоженным JSON из `SPEC_risk_dashboard_agi_ui.md` для проверки верстки.

## Определение готовности

- Компонент `<RiskCockpit data={mockData} />` корректно рендерит полный дашборд риска.
- Верстка адаптивна и выглядит профессионально (финансовый стиль).

## Структура файлов

```text
apps/web/components/risk-dashboard/
├── RiskCockpit.tsx       # Entry point
├── MetricCard.tsx
├── AlertBlock.tsx
├── charts/
│   ├── EquityChart.tsx
│   └── AllocationChart.tsx
└── tables/
    └── RiskTable.tsx
```
