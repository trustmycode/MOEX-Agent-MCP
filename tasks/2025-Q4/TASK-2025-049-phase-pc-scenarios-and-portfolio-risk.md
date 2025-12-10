---
id: TASK-2025-049
title: "Фаза PC. Сценарии, шаблоны и portfolio_risk"
status: backlog
priority: high
type: feature
estimate: 32h
assignee: @unassigned
created: 2025-12-10
updated: 2025-12-10
parents: [TASK-2025-003, TASK-2025-007]
arch_refs: [ARCH-agent-moex-market-analyst, ARCH-mcp-moex-iss]
risk: medium
benefit: "Формализует сценарии агента через ScenarioTemplate и обеспечивает контролируемое поведение portfolio_risk для больших портфелей."
audit_log:
  - {date: 2025-12-10, user: "@AI-DocArchitect", action: "created with status backlog"}
---

## Описание

Добавить в модель плана явное поле `scenario_type`, реализовать Python-шаблоны сценариев (`ScenarioTemplate`) для ключевых кейсов (`single_security_overview`, `compare_securities`, `index_risk_scan`, `portfolio_risk`, `portfolio_risk_drill_down`) и зафиксировать поведение сценария `portfolio_risk` для больших портфелей (50+ бумаг) с шагом `limit_portfolio` и честной деградацией.

## Критерии приемки

- Модель `Plan` расширена полем `scenario_type` (строка/Enum), принимающим как минимум значения:
  - `single_security_overview`;
  - `compare_securities`;
  - `index_risk_scan`;
  - `portfolio_risk`;
  - `portfolio_risk_drill_down`;
  - (опционально) `portfolio_stress_test` для roadmap.
- Для каждого из сценариев `compare_securities`, `index_risk_scan`, `portfolio_risk`, `portfolio_risk_drill_down` реализован `ScenarioTemplate` (Python-модель/класс), генерирующий типовой `Plan` из набора `PlannedStep`:
  - `compare_securities` — шаги `get_ohlcv_timeseries`/`get_multi_ohlcv_timeseries` по каждому тикеру и агрегация;
  - `index_risk_scan` — `get_index_constituents_metrics` и, при необходимости, дополнительные вызовы для топ-бумаг;
  - `portfolio_risk` — последовательность шагов `parse_portfolio` → `limit_portfolio` → сбор OHLCV по выбранным бумагам → агрегирование метрик портфеля → формирование таблиц и текста;
  - `portfolio_risk_drill_down` — сценарий drill-down по top-N риск-вкладчикам на основе результата `portfolio_risk`.
- Для `portfolio_risk` реализовано поведение для больших портфелей:
  - входные данные (портфель) парсятся из свободного текста, таблицы или списка тикеров; собираются все тикеры/веса (в т.ч. 50+);
  - шаг `limit_portfolio` использует `MAX_TICKERS_PER_REQUEST` из `planner.limits` и формирует `analyzed_tickers` и `tail_tickers`;
  - если у бумаг есть веса — выбираются top-N по весу, иначе — первые N тикеров из списка;
  - анализ (загрузка тайм-серий и расчёт метрик) выполняется только по `analyzed_tickers`, а хвост агрегируется в категорию «прочие».
- В итоговом отчёте по `portfolio_risk` обязательно присутствуют:
  - явное упоминание общего числа бумаг в портфеле и количества детально рассмотренных позиций (N);
  - строка "прочие" в таблице с суммарной долей хвоста и упрощёнными характеристиками;
  - текстовое пояснение того, что часть портфеля агрегирована из-за технических ограничений и лимита `MAX_TICKERS_PER_REQUEST`.
- В REQUIREMENTS/SPEC/ARCHITECTURE добавлен раздел с ограничениями сценария `portfolio_risk` (максимальное число детально анализируемых тикеров, поведение для больших портфелей, сценарий `portfolio_risk_drill_down` как надстройка).

## Определение готовности

- В debug-выводе агента по сценариям `portfolio_risk` и `portfolio_risk_drill_down` видны `scenario_type`, применённый шаблон сценария и факт ограничения портфеля (`limited_to_top_n=true`, `original_num_tickers`, `analyzed_tickers_count`).
- Для портфеля с 50+ бумагами в тестах стабильно получается отчёт с top-N детально разобранными позициями, строкой «прочие» и корректными агрегированными метриками портфеля.
- Остальные сценарии (`single_security_overview`, `compare_securities`, `index_risk_scan`) используют ScenarioTemplates, а их планы и smoke-тесты синхронизированы с документацией.

## Заметки

Задача тесно связана с фазами P0/PA (лимиты и каркас планировщика) и фазой 6 (MCP-инструменты для портфеля) и формализует поведение portfolio_risk как осознанное бизнес-ограничение, а не «невозможность» системы.
