---
id: ARCH-agent-moex-market-analyst
title: "AI-агент moex-market-analyst-agent"
type: component
layer: application
owner: @team-moex-agent
version: v1
status: current
created: 2025-12-09
updated: 2025-12-10
tags: [ai-agent, a2a, foundation-models, moex]
depends_on: [ARCH-mcp-moex-iss, ARCH-mcp-risk-analytics]
referenced_by: []
---

## Контекст

AI-агент `moex-market-analyst-agent` — основной компонент решения, который
принимает A2A‑запросы бизнес‑пользователей (CFO, риск‑менеджер, аналитик),
использует Foundation Models и MCP‑серверы и формирует человекочитаемые
отчёты по российскому рынку Мосбиржи.

Агент разворачивается в Cloud.ru Evolution AI Agents и вызывает Evolution
Foundation Models через API `https://foundation-models.api.cloud.ru/v1/`. Все
рыночные данные (котировки, история, индексы) он получает **только** через
MCP‑слои (`moex-iss-mcp`, `risk-analytics-mcp`), а не напрямую к MOEX ISS.

Три ключевых бизнес‑сценария, которые должен поддерживать агент (см.
`docs/SCENARIOS_PORTFOLIO_RISK.md`):

- **5. `issuer_peers_compare`** — сравнительный анализ эмитента с пирами по
  мультипликаторам и риску.
- **7. `portfolio_risk`** — портфельный риск‑анализ и предложения
  ребалансировки.
- **9. `cfo_liquidity_report`** — отчёт CFO по ликвидности и устойчивости
  портфеля с несколькими стресс‑сценариями.

## Структура (P0: базовый агент и планировщик)

Основные подкомпоненты агента в MVP (P0) соответствуют C4 L3/L4 и требованиям
из `docs/ARCHITECTURE.md` и `docs/REQUIREMENTS_moex-market-analyst-agent.md`:

- **A2A‑адаптер** (`a2a_api.py`, `A2ARequestHandler`)
  - Принимает HTTP/A2A‑запросы, валидирует JSON по A2A‑схемам из
    `docs/SPEC_moex-iss-mcp.md`.
  - Создаёт `SessionContext` и передаёт управление сервису агента.

- **Менеджер сессии** (`SessionContext`)
  - Хранит `user_query`, `locale`, `user_role`, временные метки.
  - Содержит текущий `Plan`, результаты вызовов MCP (`tool_results`) и список
    ошибок.

- **Планировщик (P0)** (`Planner` + `BasicPlanningStrategy`)
  - В режиме `PLANNER_MODE=basic` строит детерминированный `Plan` из простых
    шагов (`mcp_call`, финальная генерация отчёта) для сценариев:
    - `single_security_overview`;
    - `compare_securities`;
    - `index_risk_scan`;
    - `portfolio_risk` (включая `portfolio_risk_drill_down`);
    - `issuer_peers_compare`;
    - `cfo_liquidity_report`.
  - Использует `ScenarioTemplate` (см. `docs/SCENARIOS_PORTFOLIO_RISK.md`) с
    полем `scenario_type`, набором entry‑фраз (`entrypoints`) и списком
    `required_tools` / `optional_tools`.
  - Учитывает лимиты из конфигурации `planner.limits`:
    `MAX_LLM_CALLS_PER_REQUEST`, `MAX_PLAN_STEPS_BASIC`,
    `MAX_REPLAN_ATTEMPTS_BASIC`, `MAX_DAYS_PER_SECURITY`,
    `MAX_TICKERS_PER_REQUEST`, `HARD_TOKEN_BUDGET_PER_REQUEST`.

- **Клиент Foundation Models** (`LlmClient`)
  - Обёртка над API `https://foundation-models.api.cloud.ru/v1/`.
  - Поддерживает выбор модели по `ENVIRONMENT` (`dev`/`prod`) и FALLBACK‑логику
    (MAIN/FALLBACK/DEV), как описано в задачах `TASK-2025-001` и
    `TASK-2025-003`.

- **Клиент MCP и оркестратор** (`McpClient`, `ToolOrchestrator`)
  - Вызывает инструменты MCP на `moex-iss-mcp` и `risk-analytics-mcp` по URI из
    `MCP_URL`.
  - В P0‑версии возвращает сводку результатов вызовов и ошибки, достаточные
    для формирования отчёта и простого heuristic re-plan.

- **Формирователь ответа** (`ResponseFormatter`)
  - Собирает табличные и числовые данные из `SessionContext.tool_results`.
  - Строит `output.text` через LLM на основе реальных данных MCP (без
    «выдуманных» чисел).
  - Формирует `output.tables[]` и (по флагу) `output.debug` (план, tool_calls,
    диагностическая информация).

- **Телеметрия**
  - Логирование запросов/ответов (без секретов и персональных данных).
  - Экспорт базовых метрик (число A2A‑запросов, ошибки MCP, латентность).

Основные переменные окружения агента:

- `AGENT_NAME`, `AGENT_DESCRIPTION`, `AGENT_VERSION`, `AGENT_SYSTEM_PROMPT`.
- `LLM_API_BASE=https://foundation-models.api.cloud.ru/v1`.
- `LLM_MODEL_MAIN`, `LLM_MODEL_FALLBACK`, `LLM_MODEL_DEV`, `ENVIRONMENT`.
- `MCP_URL` — список MCP‑серверов (`moex-iss-mcp`, `risk-analytics-mcp`,
  опционально RAG MCP).
- Флаги наблюдаемости (`ENABLE_PHOENIX`, `ENABLE_MONITORING`,
  `PHOENIX_ENDPOINT`, `OTEL_ENDPOINT`, `OTEL_SERVICE_NAME` и т.п.).

## Поведение в сценариях 5/7/9 (P0)

### Общий поток обработки запроса

1. A2A‑адаптер принимает входной JSON (`input.messages[]`, `metadata`),
   валидирует его и создаёт `SessionContext`.
2. `Planner` на основе последнего сообщения пользователя и контекста
   определяет `scenario_type` (5/7/9 или базовый сценарий тикера/индекса) и
   выбирает подходящий `ScenarioTemplate`.
3. Для выбранного сценария формируется `Plan` — упорядоченный список шагов
   `mcp_call` и финальной генерации отчёта.
4. `ToolOrchestrator` выполняет шаги `mcp_call` через `McpClient` и сохраняет
   результаты в `SessionContext.tool_results`.
5. `ResponseFormatter` строит итоговый `output.text` и `output.tables[]`,
   опираясь на результаты MCP и персону пользователя (аналитик / риск‑менеджер
   / CFO).
6. Агент возвращает A2A‑ответ с полями `output.text`, `output.tables`,
   `output.debug`.

### Сценарий 5 — `issuer_peers_compare`

- Планировщик определяет намерение пользователя как `issuer_peers_compare` по
  типичным фразам («сравни эмитента с пирами», «как Сбер выглядит относительно
  пиров по мультипликаторам» и т.п.).
- В P0‑версии допускаются два варианта реализации цепочки:
  - через комбинацию инструментов `moex-iss-mcp` + внутреннюю логику агента
    (минимальный вариант для хакатона);
  - либо через специализированные инструменты `risk-analytics-mcp`,
    рассчитывающие фундаментальные метрики по пирами (target‑state согласно
    `SCENARIOS_PORTFOLIO_RISK.md`).
- Агент формирует таблицу пиров с ключевыми метриками (P/E, EV/EBITDA,
  ROE, NetDebt/EBITDA, див. доходность) и текстовый вывод для аналитика.

### Сценарий 7 — `portfolio_risk`

- Планировщик выбирает `scenario_type = "portfolio_risk"` по фразам вида
  «проанализируй риски портфеля», «оцени риск портфеля» и т.п.
- Типовой план P0:
  1. Шаг парсинга портфеля из текста/таблицы/списка тикеров в структуру
     `PortfolioRiskInput`.
  2. Шаг `limit_portfolio` (ограничение числа детально анализируемых бумаг до
     `MAX_TICKERS_PER_REQUEST`, например 30; выбор top-N по весу или первых N
     тикеров).
  3. MCP‑вызов `risk-analytics-mcp.analyze_portfolio_risk`.
  4. (Опционально) вызов `risk-analytics-mcp.suggest_rebalance`.
  5. Генерация отчёта с таблицами по top‑позициям и агрегированной строкой
     «прочие» для хвоста портфеля.
- В отчёте агент явно указывает общее число бумаг и число детально
  рассмотренных позиций, а также факт агрегации хвоста.

### Сценарий 9 — `cfo_liquidity_report`

- Планировщик выбирает `scenario_type = "cfo_liquidity_report"` по запросам
  CFO («сделай отчёт по ликвидности портфеля», «покажи, выдержим ли стресс
  X»).
- План P0:
  1. Парсинг портфеля и параметров горизонта/сценариев.
  2. MCP‑вызов `risk-analytics-mcp.build_cfo_liquidity_report`.
  3. Генерация отчёта в стиле executive summary с фокусом на ликвидности,
     валютной позиции, рисках рефинансирования и ковенантах.

## Обработка ошибок и лимитов

- Все ошибки MCP нормализуются в виде `error_type`/`message`/`details` и
  отображаются пользователю в человекочитаемом виде, при этом детали могут
  сохраняться в `output.debug`.
- Для типовых ошибок данных (`INVALID_TICKER`, `DATE_RANGE_TOO_LARGE`,
  `TOO_MANY_TICKERS`, `UNKNOWN_INDEX`) basic‑планировщик может выполнить один
  heuristic re-plan (сужение периода, ограничение числа тикеров) в рамках
  `MAX_REPLAN_ATTEMPTS_BASIC`.
- При transient‑ошибках LLM клиент использует fallback‑модель, не нарушая
  A2A‑контракт.

## Эволюция (PA–PE, roadmap)

В задачах фаз PA–PE (`TASK-2025-047`–`TASK-2025-051`) планируется развитие
планировщика и интеграции агента:

- Введение интерфейса `PlanningStrategy` и нескольких стратегий:
  - `BasicPlanningStrategy` (текущий P0‑режим);
  - `AdvancedPlanningStrategy` (LLM‑assisted re-plan на основе
    `PlanExecutionResult`);
  - `ExternalAgentPlanningStrategy` (делегирование построения плана
    вынесенному Planner Agent).
- Введение `ToolRegistry` как единого реестра MCP‑инструментов, читающего
  метаданные из `tools.json` (`moex-iss-mcp`, `risk-analytics-mcp` и, в
  будущем, других сервисов).
- Переход ко второму поколению re-plan (PB): структура `ExecutedStep` и
  `PlanExecutionResult`, cost-aware планирование и более точная обработка
  ошибок (`RATE_LIMIT`, сложные портфели и др.).
- Добавление `PlanValidator` и YAML‑DSL для сценариев, позволяющих описывать
  `ScenarioTemplate` вне кода и эволюционировать сценарии без рефакторинга
  агента.
- Интеграция RAG‑MCP для методологических пояснений и обоснований, без
  вмешательства в числовые результаты MCP‑инструментов.

Все эти изменения не меняют базовый A2A‑контракт агента, а расширяют и
улучшают качество планирования, контроль стоимости и объяснимость решений в
сценариях 5/7/9.
