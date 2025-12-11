# TASK-2025-105: Отчёт CFO по ликвидности (`cfo_liquidity_report`) и A2A-JSON

## Статус

- Статус: **done** ✅
- Приоритет: P0.5
- Компонент: risk-analytics-mcp + бизнес-агент
- Связанные сценарии: cfo_liquidity_report (9), portfolio_risk (7)
- Дата завершения: 2025-12-11

## Контекст

Сценарий 9 — «упаковка» портфельного риска под потребности CFO. Нужен структурированный A2A-JSON (`CfoLiquidityReport`), который будет понятен Evolution AI Agents и другим агентам, и человекочитаемый отчёт (Markdown/HTML) поверх него.

## Цель

Реализовать end-to-end сценарий `cfo_liquidity_report`, который использует ядро `portfolio_risk`, формирует структурированный JSON-отчёт и отдаёт агенту основу для executive summary.

## Объём работ

### In scope

- Описание и фиксация контракта `CfoLiquidityReport`:
  - ключевые секции (ликвидность портфеля, дюрация, валютный разрез, концентрации, стресс-сценарии),
  - поля для рекомендаций (например, «уменьшить долю длинных ОФЗ»).
- Расширение MCP:
  - реализация tool (или режима) для формирования `CfoLiquidityReport` поверх вычислений `portfolio_risk`,
  - переиспользование всех метрик и стрессов из TASK-2025-103.
- Логика агента:
  - генерация Markdown-/HTML-отчёта для CFO на основе `CfoLiquidityReport`,
  - адаптация языка и акцентов под CFO-персону (фокус на ликвидности, cash-flow, рисках рефинансирования).
- Примеры:
  - минимум 1–2 готовых JSON-примера отчёта,
  - пример человека-читаемого отчёта, использующий эти JSON.

### Out of scope

- Генерация PDF/BI-дэшбордов.
- Глубокий анализ ковенант и кредитных договоров.

## Acceptance Criteria

- [x] Контракт `CfoLiquidityReport` зафиксирован в виде схемы (например, JSON Schema) и используется в коде MCP.
- [x] MCP может вернуть валидный `CfoLiquidityReport` для тестового портфеля.
- [x] Агент строит стабильный Markdown-/HTML-отчёт для CFO на основе полученного JSON.
- [x] В репозитории есть примеры JSON-ответов и финальных отчётов для демо.
- [x] В документации описано, как запустить сценарий `cfo_liquidity_report` end-to-end.

## Реализация

### Созданные файлы

1. **JSON Schema** (контракты):
   - `docs/schemas/cfo_liquidity_report_input.json` — схема входных данных
   - `docs/schemas/cfo_liquidity_report_output.json` — схема выходного отчёта

2. **Pydantic-модели** (`risk_analytics_mcp/models/__init__.py`):
   - `CfoLiquidityPosition` — позиция портфеля с характеристиками ликвидности
   - `CovenantLimits` — лимиты ковенант для проверки
   - `CfoLiquidityReportInput` — входные данные для MCP-tool
   - `LiquidityBucket`, `LiquidityProfile` — профиль ликвидности
   - `DurationProfile` — профиль дюрации
   - `CurrencyExposure`, `CurrencyExposureItem` — валютная экспозиция
   - `CfoConcentrationProfile` — концентрации
   - `CfoRiskMetrics` — метрики риска
   - `CfoStressScenarioResult`, `CovenantBreach` — результаты стресс-сценариев
   - `CfoRecommendation` — рекомендации
   - `CfoExecutiveSummary` — executive summary
   - `CfoLiquidityReport` — финальный отчёт

3. **Расчётная логика** (`risk_analytics_mcp/calculations/cfo_liquidity.py`):
   - `build_liquidity_profile()` — профиль ликвидности по корзинам
   - `build_duration_profile()` — профиль дюрации
   - `build_currency_exposure()` — валютная структура
   - `build_concentration_profile()` — концентрации
   - `build_cfo_stress_scenarios()` — стресс-сценарии с ковенант-чеками
   - `build_recommendations()` — генерация рекомендаций
   - `build_executive_summary()` — формирование executive summary

4. **MCP-tool** (`risk_analytics_mcp/tools/cfo_liquidity_report.py`):
   - `build_cfo_liquidity_report()` — асинхронный MCP-инструмент
   - `build_cfo_liquidity_report_core()` — синхронная версия для тестов

5. **Примеры и документация**:
   - `tests/e2e_cfo_liquidity_report.md` — примеры curl-запросов и ответов
   - `docs/SPEC_risk-analytics-mcp.md` — обновлена спецификация (секция 2.5)

### Ключевые секции отчёта

1. **liquidity_profile** — распределение по корзинам ликвидности (0-7d, 8-30d, 31-90d, 90d+)
2. **duration_profile** — дюрация fixed income части
3. **currency_exposure** — валютная структура с FX-риском
4. **concentration_profile** — top1/3/5, HHI, распределение по классам активов
5. **risk_metrics** — доходность, волатильность, VaR
6. **stress_scenarios** — base_case + 3 стресс-сценария с ковенант-чеками
7. **recommendations** — приоритизированные рекомендации с категориями
8. **executive_summary** — статус ликвидности, ключевые риски, действия

### Запуск

```bash
# Запуск сервера
uv run python -m risk_analytics_mcp.main

# Пример вызова
curl -X POST http://localhost:8001/mcp \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"build_cfo_liquidity_report","arguments":{...}}}'
```

Подробные примеры — см. `tests/e2e_cfo_liquidity_report.md`.


