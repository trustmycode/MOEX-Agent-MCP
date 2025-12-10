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
depends_on: [ARCH-mcp-moex-iss]
referenced_by: []
---

## Контекст

AI-агент `moex-market-analyst-agent` — основной компонент решения, который принимает A2A‑запросы бизнес‑пользователей (CFO, риск‑менеджер, аналитик), вызывает Foundation Models и MCP‑серверы и формирует человекочитаемые отчёты по российскому фондовому рынку.

Агент разворачивается в Cloud.ru Evolution AI Agents и использует Evolution Foundation Models через API `https://foundation-models.api.cloud.ru/v1/`.

## Структура

Основные подкомпоненты агента соответствуют C4 L3/L4:

- A2A‑адаптер (`a2a_api.py`, `A2ARequestHandler`) — HTTP/A2A‑слой, валидация JSON, создание `SessionContext`.
- Менеджер сессии (`SessionContext`) — хранение запроса, локали, роли пользователя, плана, результатов tool‑вызовов и ошибок.
- Подсистема планирования (`Planner` + `PlanningStrategy`) — LLM‑планирование последовательности вызовов MCP‑инструментов и финальной генерации отчёта, поддерживающее стратегии `BasicPlanningStrategy` (дефолт), `AdvancedPlanningStrategy` (LLM-assisted re-plan) и `ExternalAgentPlanningStrategy` (delegation, roadmap).
- Клиент FM (`LlmClient`) — обёртка над Foundation Models API с поддержкой выбора модели по окружению и fallback‑логики.
- Реестр инструментов (`ToolRegistry`, `ToolSpec`) — единый источник правды о доступных MCP‑tools (имя, сервер, описание, cost/risk‑ранги, experimental/enable‑флаги).
- MCP‑клиент (`McpClient`) и оркестратор (`ToolOrchestrator`) — вызов `moex-iss-mcp` и других MCP, агрегация результатов и обработка ошибок, формирование `PlanExecutionResult` / `ExecutedStep` для re-plan.
- Формирователь ответа (`ResponseFormatter`) — построение `output.text`, `output.tables` и отладочного блока `output.debug`.
- Адаптер телеметрии — интеграция с Phoenix / OTEL / Prometheus.

Основные переменные окружения:

- `AGENT_NAME`, `AGENT_DESCRIPTION`, `AGENT_VERSION`, `AGENT_SYSTEM_PROMPT`.
- `LLM_API_BASE=https://foundation-models.api.cloud.ru/v1`.
- `LLM_MODEL_MAIN`, `LLM_MODEL_FALLBACK`, `LLM_MODEL_DEV`.
- `ENVIRONMENT` (`dev`/`prod`) для выбора модели.
- `MCP_URL` со списком MCP‑серверов (`moex-iss-mcp`, опционально RAG MCP).
- Флаги наблюдаемости (`ENABLE_PHOENIX`, `ENABLE_MONITORING`, `OTEL_ENDPOINT` и т.п.).

## Поведение

Базовый поток обработки запроса:

1. A2A‑адаптер принимает HTTP‑запрос `input.messages[]`, валидирует его и создаёт `SessionContext`.
2. `Planner` на основе последнего сообщения пользователя и контекста формирует `Plan` с шагами `mcp_call` и финальной генерацией отчёта, указывая `scenario_type` (например, `single_security_overview`, `compare_securities`, `index_risk_scan`, `portfolio_risk`, `portfolio_risk_drill_down`) и используя соответствующий `ScenarioTemplate`.
3. `ToolOrchestrator` выполняет план, используя `McpClient.call_tool(...)` для вызова инструментов MCP (`get_security_snapshot`, `get_ohlcv_timeseries`, `get_index_constituents_metrics` и, по мере развития, портфельные инструменты), и формирует структурированный `PlanExecutionResult`.
4. `ResponseFormatter` собирает структурированные данные и вызывает `LlmClient` для генерации итогового текста, строго опираясь на данные MCP (без выдуманных чисел).
5. Агент возвращает A2A‑ответ с полями `output.text`, `output.tables`, `output.debug`.

Обработка ошибок:

- Ошибки MCP‑инструментов отображаются в человекочитаемый текст с сохранением технических деталей в `output.debug`.
- При transient‑ошибках основной модели используется fallback‑логика: для `ENVIRONMENT=prod` основной моделью является `LLM_MODEL_MAIN` (Qwen3‑235B), при сбоях используется `LLM_MODEL_FALLBACK` (gpt‑oss‑120b); в `ENVIRONMENT=dev` — `LLM_MODEL_DEV` (GigaChat3‑10B).
- Для типовых ошибок инструментов (`DATE_RANGE_TOO_LARGE`, `TOO_MANY_TICKERS`, `RATE_LIMIT` и др.) basic‑стратегия планировщика выполняет один heuristic re-plan (сужение периода, ограничение числа тикеров, снижение параллелизма) в пределах лимитов `planner.limits`; advanced‑стратегия может дополнительно вызывать LLM для перепланирования с учётом `PlanExecutionResult`.

Сценарии и поведение для больших портфелей:

- Планировщик поддерживает явно выраженные сценарии через `ScenarioTemplate` с полем `scenario_type`, включая:\n  - `single_security_overview`;\n  - `compare_securities`;\n  - `index_risk_scan`;\n  - `portfolio_risk`;\n  - `portfolio_risk_drill_down` (drill-down по вкладчикам риска).\n- Для `portfolio_risk` план включает шаги:\n  - парсинг портфеля из текста/таблиц/списков тикеров; \n  - `limit_portfolio`, ограничивающий число детально анализируемых бумаг до `MAX_TICKERS_PER_REQUEST` (top-N по весу либо первые N тикеров);\n  - сбор временных рядов и расчёт агрегированных метрик портфеля;\n  - формирование табличного и текстового вывода с отдельной строкой «прочие» для хвоста портфеля.\n- В отчёте по `portfolio_risk` агент честно проговаривает деградацию для больших портфелей (например, «портфель содержит 53 инструмента, детально рассмотрены 10 крупнейших позиций, остальные агрегированы в категорию \\\"прочие\\\" из‑за технических ограничений»).

## Эволюция

### Планируемые изменения

- Интеграция RAG MCP для методологий и гайдов (Phase 1), добавление шага `rag_search` в планировщик и включение выдержек в `output.text`.
- Поддержка дополнительных MCP‑инструментов портфельного анализа (`get_multi_ohlcv_timeseries`, `get_portfolio_metrics`) и сценариев «вот мой портфель, оцени риск».
- Эволюция планировщика в полноценную подсистему LLM‑планирования: стратегии `Basic/Advanced/ExternalAgentPlanningStrategy`, cost-aware планирование, `PlanValidator`, feedback‑loop и, в перспективе, вынесенный Planner Agent.
- Подготовка и поддержка Agent Card для публикации агента в каталоге Evolution AI Agents.
- Расширение поддержки web‑UI (одностраничный дашборд) поверх A2A‑контракта.

### История

- v1 (2025‑12‑09): зафиксирован целевой дизайн агента по результатам анализа требований, C4‑диаграмм и SPEC.

