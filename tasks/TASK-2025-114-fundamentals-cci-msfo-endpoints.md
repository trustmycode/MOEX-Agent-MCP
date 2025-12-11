# TASK-2025-114: Расширенный фундаментал (CCI/MSFO) через moex_iss_sdk для issuer_peers_compare

## Статус

- Статус: planned
- Приоритет: P0.5
- Компонент: moex_iss_sdk + risk-analytics-mcp
- Связанные сценарии: issuer_peers_compare (5), portfolio_risk (7), cfo_liquidity_report (9)

## Контекст

В текущем MVP `FundamentalsDataProvider` (`MoexIssFundamentalsProvider`) опирается на:

- snapshot `/marketdata` для цены и сырого набора полей;
- `/securities/{ticker}.json` для ISIN/ISSUESIZE/валюты номинала;
- `/securities/{ticker}/dividends.json` для дивидендной доходности.

Для большинства бумаг ISS не отдаёт стабильные мультипликаторы и CFO‑метрики
через `marketdata`, поэтому в `IssuerFundamentals` поля:

- `revenue`, `ebitda`, `net_income`, `total_debt`, `total_equity`,
- производные `pe_ratio`, `ev_to_ebitda`, `debt_to_ebitda`, `roe_pct`

часто остаются `null`. В результате инструмент `issuer_peers_compare` может
ранжировать эмитента только по дивидендной доходности, а поля P/E,
EV/EBITDA, NetDebt/EBITDA, ROE и связанные флаги почти всегда пустые.

Чтобы сценарий 5 действительно отвечал требованиям (сравнение по ключевым
мультипликаторам и рентабельности), нужен отдельный источник отчётных
метрик — CCI/MSFO или аналогичный JSON‑поток MOEX — и полноценная
интеграция в `moex_iss_sdk` и `FundamentalsDataProvider`.

## Цель

Добавить в `moex_iss_sdk` поддержку JSON‑эндпоинтов MOEX с CCI/MSFO
отчётностью, распарсить базовые финансовые и долговые метрики и
прокинуть их через доменную модель `IssuerFundamentals`, чтобы:

- `issuer_peers_compare` мог рассчитывать и ранжировать:
  - P/E, EV/EBITDA, NetDebt/EBITDA, ROE;
- будущие сценарии по ликвидности/ковенантам (7/9) имели доступ к
  устойчивому набору CFO‑метрик.

## Объём работ

### In scope

- Исследовать доступные публичные JSON‑источники MOEX с отчётностью:
  - CCI/MSFO или иные таблицы с ключевыми финансовыми показателями;
  - выбрать стабильный минимум полей для MVP (LTM/последний отчётный период).
- Расширить `moex_iss_sdk`:
  - добавить новые билдеры в `moex_iss_sdk.endpoints` для выбранных CCI/MSFO‑ресурсов;
  - реализовать методы `IssClient`, возвращающие типизированные модели
    (например, `IssuerFinancials` / `IssuerMetricsSnapshot`), с аккуратной
    обработкой ошибок (InvalidTicker, 5xx, timeout);
  - добавить модели и парсинг (аналогично `SecurityInfo`, `IndexConstituent`):
    - `revenue`,
    - `ebitda` / `ebit`,
    - `net_income`,
    - `total_debt` и, по возможности, `net_debt`,
    - `total_equity`,
    - производные мультипликаторы, если они уже есть в JSON.
- Интегрировать новые данные в `FundamentalsDataProvider`:
  - расширить `MoexIssFundamentalsProvider._load_from_iss`, чтобы:
    - при наличии отчётных JSON‑метрик заполнять поля `revenue`,
      `ebitda`, `net_income`, `total_debt`, `net_debt`, `total_equity`;
    - считать/перезаписывать производные:
      - `pe_ratio = price / EPS` (где EPS = net_income / shares_outstanding),
      - `ev_to_ebitda = enterprise_value / ebitda`,
      - `debt_to_ebitda = net_debt / ebitda`,
      - `roe_pct = net_income / total_equity * 100`;
  - не ломать существующее поведение: при отсутствии CCI/MSFO метрики
    остаются `null`, как сейчас.
- Обновить `issuer_peers_compare` (TASK-2025-108/109) на уровне SPEC/доков:
  - явно указать, какие поля `IssuerFundamentals` теперь гарантируются
    при наличии CCI/MSFO;
  - описать, что ранжирование и флаги опираются на «расширенный» источник
    фундаментала, если он доступен.
- Написать юнит‑тесты:
  - snapshot‑тесты для новых методов `IssClient` с сохранёнными CCI/MSFO
    JSON‑ответами;
  - тесты для `MoexIssFundamentalsProvider`, проверяющие заполнение
    `revenue`, `ebitda`, `net_income`, `total_debt`, `net_debt`,
    `total_equity`, а также корректный расчёт P/E, EV/EBITDA,
    NetDebt/EBITDA и ROE;
  - минимальный тест для `issuer_peers_compare_core`, который на
    синтетических данных гарантирует, что ранжирование по P/E и ROE
    больше не `null`.

### Out of scope

- Полная нормализация отчётности MSFO vs РСБУ и конвертация валют /
  мультивалютные отчёты — достаточно фиксированного набора полей для РФ
  blue chips в MVP.
- Поддержка нескольких внешних провайдеров фундаментала (коммерческие
  API) — остаёмся на MOEX ISS + CCI/MSFO.
- Любые изменения в алгоритмах стресс‑сценариев и Var_light (это
  покрыто TASK-2025-103).

## Acceptance Criteria

- [ ] В `moex_iss_sdk` реализованы и протестированы методы клиента для
      получения отчётных CCI/MSFO‑данных по тикеру.
- [ ] Модель `IssuerFundamentals` в `risk_analytics_mcp.models` заполняется
      не только ценой/дивидендами, но и базовыми CFO‑метриками
      (`revenue`, `ebitda`, `net_income`, `total_debt`/`net_debt`,
      `total_equity`) и производными (P/E, EV/EBITDA, NetDebt/EBITDA, ROE).
- [ ] Инструмент `issuer_peers_compare` на синтетических или snapshot‑данных
      демонстрирует ненулевое ранжирование по P/E, EV/EBITDA,
      NetDebt/EBITDA и ROE, а флаги (OVERVALUED/UNDERVALUED,
      HIGH_LEVERAGE, LOW_ROE и т.п.) ставятся на основе этих метрик.
- [ ] Существующие тесты для `MoexIssFundamentalsProvider` и
      `issuer_peers_compare` проходят; добавленные тесты покрывают новые
      ветки логики.
- [ ] Документация (`docs/SPEC_risk-analytics-mcp.md` и, при необходимости,
      отдельный SPEC для фундаментала) обновлена и явно указывает, какие
      метрики гарантируются при включённом CCI/MSFO‑источнике.

## Зависимости и связи

- Зависит от:
  - TASK-2025-073 / TASK-2025-080–088 — архитектура и существующие
    модели/эндпоинты `moex_iss_sdk`;
  - TASK-2025-102 — базовый `FundamentalsDataProvider` и
    `MoexIssFundamentalsProvider`;
  - TASK-2025-108 — реализация логики `issuer_peers_compare`;
  - TASK-2025-109 — SPEC и `tools.json` для `issuer_peers_compare`.
- Поддерживает:
  - TASK-2025-104 — сценарий 5 (issuer_peers_compare) с полноценным
    сравнением по мультипликаторам и ROE;
  - TASK-2025-105 — расширенные CFO‑отчёты и ковенант‑чекеры в сценарии 9;
  - потенциальные будущие задачи по кредитным/ковенантным метрикам.

