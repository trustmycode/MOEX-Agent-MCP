---
id: TASK-2025-123
title: "Explainer & Dashboard Subagents"
status: planned
priority: critical
type: feature
estimate: 16h
assignee: @unassigned
created: 2025-12-12
updated: 2025-12-12
parents: [TASK-2025-120]
children: []
arch_refs: [ARCH-agent-moex-market-analyst]
risk: medium
benefit: "Создаёт репортёров — сабагенты для генерации текстового отчёта и JSON-UI дашборда."
supersedes: [TASK-2025-110]
audit_log:
  - {date: 2025-12-12, user: "@AI-Codex", action: "created as critical P0 task for multi-agent MVP (absorbs TASK-110)"}
---

## Описание

Реализовать два сабагента-репортёра, которые формируют финальный ответ пользователю:

### 1. ExplainerSubagent

Генерирует человекочитаемый текстовый отчёт (`output.text`) на основе:
- данных от MarketDataSubagent
- расчётов от RiskAnalyticsSubagent
- роли пользователя (CFO, риск-менеджер, аналитик)
- языка (ru/en)

Использует LLM для генерации текста. **Не выдумывает числа** — только форматирует и объясняет то, что получено из MCP.

### 2. DashboardSubagent

Генерирует структурированный JSON для UI (`output.dashboard`) в формате `RiskDashboardSpec`:
- карточки ключевых метрик
- таблицы позиций
- таблицы стресс-сценариев
- alerts по рискам

**Не использует LLM** — чисто детерминированный маппинг данных в JSON-структуру.

## Критерии приёмки

### ExplainerSubagent

- [ ] Наследуется от `BaseSubagent` (TASK-120)
- [ ] Принимает `AgentContext` с заполненными `intermediate_results` от воркеров
- [ ] Генерирует текст через LLM (GigaChat / GPT) по промпту:
  - Описание метрик портфеля (доходность, волатильность, max drawdown)
  - Интерпретация Var_light и стресс-тестов
  - Рекомендации (если есть suggest_rebalance)
  - Адаптация под роль: CFO — больше про бизнес, риск-менеджер — больше про метрики
- [ ] Промпт явно запрещает «выдумывать числа» — только данные из context
- [ ] Поддержка русского языка (приоритет) и английского
- [ ] Возвращает `SubagentResult` с `data.text: str`

### DashboardSubagent

- [ ] Наследуется от `BaseSubagent` (TASK-120)
- [ ] Маппит данные из `context.intermediate_results` в `RiskDashboardSpec`:
  - `metric_cards[]` — ключевые метрики (return, volatility, var_light, max_drawdown)
  - `tables[]` — позиции портфеля, стресс-сценарии
  - `alerts[]` — превышение концентраций, высокий VaR
- [ ] Формат `RiskDashboardSpec` соответствует `docs/SPEC_risk_dashboard_agi_ui.md`
- [ ] **Детерминированная логика** — никакого LLM, только код
- [ ] Возвращает `SubagentResult` с `data.dashboard: RiskDashboardSpec`

### Общее

- [ ] Оба сабагента зарегистрированы в `SubagentRegistry`
- [ ] Тесты на генерацию текста (mock LLM) и dashboard JSON

## Определение готовности

- Для сценария `portfolio_risk`:
  - ExplainerSubagent генерирует осмысленный текст на русском
  - DashboardSubagent возвращает валидный `RiskDashboardSpec`
- A2A-ответ содержит оба поля: `output.text` и `output.dashboard`
- Web-UI может отрендерить dashboard без доработок

## Структура файлов

```
packages/agent-service/src/agent_service/subagents/
├── __init__.py
├── explainer.py      # ExplainerSubagent
└── dashboard.py      # DashboardSubagent

packages/agent-service/src/agent_service/models/
└── dashboard_spec.py # RiskDashboardSpec (Pydantic model)
```

## Зависимости

- TASK-120 (BaseSubagent, AgentContext)
- TASK-121 (данные от MarketData/RiskAnalytics сабагентов)
- `docs/SPEC_risk_dashboard_agi_ui.md` — спецификация JSON-формата

## RiskDashboardSpec (краткая схема)

```python
class MetricCard(BaseModel):
    id: str
    title: str
    value: str
    change: Optional[str]
    status: Literal["normal", "warning", "critical"]

class TableSpec(BaseModel):
    id: str
    title: str
    columns: list[str]
    rows: list[list[str]]

class Alert(BaseModel):
    id: str
    severity: Literal["info", "warning", "critical"]
    message: str

class RiskDashboardSpec(BaseModel):
    metric_cards: list[MetricCard]
    tables: list[TableSpec]
    alerts: list[Alert]
```

## Заметки

Эта задача поглощает TASK-2025-110 (Risk Dashboard и DashboardSubagent), которая была помечена как дубликат.

ExplainerSubagent заменяет потребность в RAG для MVP — LLM использует свои встроенные знания для объяснения метрик. RAG можно добавить позже (TASK-111, hold).
