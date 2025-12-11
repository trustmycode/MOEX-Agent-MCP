# TASK-2025-113: Smoke‑кейсы для compute_portfolio_risk_basic (stress + Var_light)

## Статус

- Статус: planned
- Приоритет: P1
- Компонент: risk-analytics-mcp
- Связанные сценарии: portfolio_risk (7), cfo_liquidity_report (9)

## Контекст

В TASK-2025-077 и TASK-2025-103 реализован инструмент
`risk-analytics-mcp.compute_portfolio_risk_basic` с поддержкой:

- агрегатов портфеля (`aggregates.asset_class_weights`, `fx_exposure_weights`);
- фиксированных стресс-сценариев (`equity_-10_fx_+20`, `rates_+300bp`, …);
- лёгкого Var_light (`var_config.confidence_level`, `horizon_days`).

В папке `cases.md` начали появляться «ручные» curl-примеры, но нет
формальной задачи, которая фиксирует:

- эталонные smoke‑кейсы для stress + Var_light;
- ожидаемую структуру ответа (что именно должен увидеть аналитик);
- связь этих примеров со сценариями 7/9.

Без отдельной задачи есть риск, что примеры в `cases.md` разъедутся с
фактическим контрактом MCP и Acceptance Criteria по сценарию 7.

## Цель

Оформить и зафиксировать 2–3 эталонных smoke‑кейса вызова
`compute_portfolio_risk_basic` (с включёнными stress‑сценариями и
Var_light) в виде задачи и документации, чтобы:

- любой разработчик/аналитик мог быстро проверить работу risk‑MCP curl‑ом;
- эти кейсы использовались в демо и регрессионных проверках для сценариев 7/9.

## Объём работ

### In scope

- Описать 2–3 ключевых кейса в терминах curl‑вызовов:
  - базовый портфель 2–3 акций (например, `SBER`, `GAZP`, `LKOH`) без агрегатов,
    только Var_light;
  - расширенный кейс с агрегатами и stress‑сценариями, например:
    ```bash
    curl -s -X POST http://localhost:8010/mcp \
      -H "Content-Type: application/json" \
      -H "Accept: application/json, text/event-stream" \
      -d '{
        "jsonrpc": "2.0",
        "id": "test-stress-1",
        "method": "tools/call",
        "params": {
          "name": "compute_portfolio_risk_basic",
          "arguments": {
            "positions": [
              {"ticker": "SBER", "weight": 0.6},
              {"ticker": "VTBR", "weight": 0.4}
            ],
            "from_date": "2024-10-01",
            "to_date": "2024-11-30",
            "rebalance": "buy_and_hold",
            "aggregates": {
              "asset_class_weights": {"equity": 1.0},
              "fx_exposure_weights": {"RUB": 0.8, "USD": 0.2}
            },
            "stress_scenarios": ["equity_-10_fx_+20", "rates_+300bp"],
            "var_config": {
              "confidence_level": 0.95,
              "horizon_days": 1
            }
          }
        }
      }'
    ```
- Для каждого кейса явно описать ожидаемые элементы ответа
  (high‑level, без жёстких чисел):
  - в `metadata` — корректные даты, список тикеров, выбранные stress‑сценарии;
  - в `data.portfolio_metrics` — ненулевые `total_return_pct`,
    `annualized_volatility_pct`, `max_drawdown_pct`;
  - в `data.stress_results[]` — наличие записей для `equity_-10_fx_+20`
    и `rates_+300bp` с разумными знаками P&L;
  - в `data.var_light` — `method="parametric_normal"`, переданные
    `confidence_level` и `horizon_days`;
  - `error: null`.
- Вынести эти кейсы в отдельный раздел `cases.md` (или новый
  `CASES_portfolio_risk.md`) с пометкой, что это эталонные smoke‑тесты.
- Сослаться на них из `docs/SCENARIOS_PORTFOLIO_RISK.md` в разделе
  Scenario 7 как на «быстрый способ ручной проверки».

### Out of scope

- Добавление новых параметров в `compute_portfolio_risk_basic` —
  используются уже реализованные поля.
- Любые изменения алгоритмов stress‑сценариев или Var_light (это покрыто
  TASK-2025-103).

## Acceptance Criteria

- [ ] В `cases.md` (или отдельном файле в корне/`docs/`) описано минимум
      два curl‑примера вызова `compute_portfolio_risk_basic`:
      базовый и расширенный (с aggregates + stress + Var_light).
- [ ] Для каждого примера текстом зафиксировано, какие части ответа
      нужно визуально проверить (наличие блоков `portfolio_metrics`,
      `stress_results`, `var_light`, отсутствие `error`).
- [ ] Документ `docs/SCENARIOS_PORTFOLIO_RISK.md` содержит ссылку на
      эти кейсы как на рекомендованные smoke‑проверки для сценариев 7/9.
- [ ] Команда может использовать эти curl‑кейсы для демонстрации работы
      risk‑MCP без дополнительных настроек (при наличии доступа к ISS).

## Зависимости и связи

- Зависит от:
  - TASK-2025-077 — реализация инструмента `compute_portfolio_risk_basic`;
  - TASK-2025-103 — реализация стресс‑сценариев и Var_light.
- Поддерживает:
  - TASK-2025-104 — планировщик P0 по сценарию 7
    (`portfolio_risk`) — даёт быстрый smoke‑чек MCP‑слоя;
  - TASK-2025-105 — демонстрационные кейсы для отчётов CFO по рискам.

