# Risk Analytics MCP Server

MCP сервер для расчёта метрик риска портфелей, ребалансировки и корреляционных матриц на основе данных MOEX.

## Описание

Сервер предоставляет инструменты для анализа рисков портфелей, ребалансировки, расчёта корреляций между инструментами и оценки стресс-сценариев.

## Возможности

- **compute_portfolio_risk_basic** - расчёт базовых метрик риска портфеля
- **compute_correlation_matrix** - вычисление матрицы корреляций доходностей
- **issuer_peers_compare** - сравнение эмитента с пирами по мультипликаторам
- **suggest_rebalance** - предложение по ребалансировке портфеля

## Требования

- Python 3.12+
- Зависимости из `pyproject.toml`

## Переменные окружения

### Обязательные переменные

Все переменные опциональны, так как есть значения по умолчанию.

### Необязательные переменные

- `RISK_MCP_PORT` или `PORT` - Порт сервера (по умолчанию: 8010)
- `RISK_MCP_HOST` или `HOST` - Хост сервера (по умолчанию: 0.0.0.0)
- `RISK_MAX_PORTFOLIO_TICKERS` - Максимальное количество тикеров в портфеле (по умолчанию: 50)
- `RISK_MAX_CORRELATION_TICKERS` - Максимальное количество тикеров для корреляционной матрицы (по умолчанию: 20)
- `RISK_MAX_LOOKBACK_DAYS` или `MOEX_ISS_MAX_LOOKBACK_DAYS` - Максимальный период истории в днях (по умолчанию: 365)
- `RISK_ENABLE_MONITORING` или `ENABLE_MONITORING` - Включить мониторинг (по умолчанию: false)
- `RISK_OTEL_ENDPOINT` или `OTEL_ENDPOINT` - OpenTelemetry endpoint (опционально)
- `RISK_OTEL_SERVICE_NAME` или `OTEL_SERVICE_NAME` - Имя сервиса для OpenTelemetry (по умолчанию: risk-analytics-mcp)

## Deploy to Evolution

- **rawEnvs**:  
  - `RISK_MCP_PORT` / `PORT` — например `8010`  
  - `RISK_MCP_HOST` / `HOST` — например `0.0.0.0`  
  - `RISK_MAX_PORTFOLIO_TICKERS` — например `50`  
  - `RISK_MAX_CORRELATION_TICKERS` — например `20`  
  - `RISK_MAX_LOOKBACK_DAYS` или `MOEX_ISS_MAX_LOOKBACK_DAYS` — например `365`  
  - `RISK_ENABLE_MONITORING` / `ENABLE_MONITORING` — `false`/`true`  
  - `RISK_OTEL_ENDPOINT` / `OTEL_ENDPOINT`, `RISK_OTEL_SERVICE_NAME` / `OTEL_SERVICE_NAME` — при необходимости трейсов  
  - `MOEX_ISS_MCP_URL` — например `http://moex-iss-mcp:8000`
- **secretEnvs**:  
  - `LLM_API_KEY` — если MCP напрямую обращается к LLM/FMs.
- **Порты**: HTTP `8010` (экспонируется `EXPOSE 8010` в Dockerfile).
- **Команда запуска**: `python -m risk_analytics_mcp.main`.

## Локальный запуск

1. Установите зависимости:
```bash
uv sync
```

2. Создайте файл `.env` (опционально):
```bash
cp .env.example .env
# Отредактируйте .env файл при необходимости
```

3. Запустите сервер:
```bash
uv run python -m risk_analytics_mcp.main
```

Сервер будет доступен по адресу `http://localhost:8010/mcp`

## Использование инструментов

### `compute_portfolio_risk_basic` - Вычислить метрики риска портфеля

Рассчитывает метрики риска, доходности, концентрации и стресс-сценарии для указанного портфеля.

**Параметры:**
- `positions` (list, обязательный) - Список позиций портфеля с тикерами и весами
- `from_date` (str, обязательный) - Начальная дата периода в формате YYYY-MM-DD
- `to_date` (str, обязательный) - Конечная дата периода в формате YYYY-MM-DD
- `rebalance` (str, опциональный) - Стратегия ребалансировки: 'buy_and_hold' или 'monthly' (по умолчанию: 'buy_and_hold')
- `aggregates` (dict, опциональный) - Агрегированные характеристики портфеля для стресс-сценариев
- `stress_scenarios` (list, опциональный) - Список идентификаторов стресс-сценариев
- `var_config` (dict, опциональный) - Параметры для расчёта VaR

**Возвращает:**
- Метрики по каждому инструменту
- Агрегированные метрики портфеля
- Концентрационные метрики
- Результаты стресс-сценариев
- VaR (Value at Risk)

**Пример:**
```python
result = await compute_portfolio_risk_basic(
    positions=[
        {"ticker": "SBER", "weight": 0.5},
        {"ticker": "GAZP", "weight": 0.5}
    ],
    from_date="2024-01-01",
    to_date="2024-12-31",
    rebalance="buy_and_hold",
    ctx=ctx
)
```

### `compute_correlation_matrix` - Вычислить матрицу корреляций

Рассчитывает корреляционную матрицу доходностей для списка инструментов.

**Параметры:**
- `tickers` (list, обязательный) - Список тикеров для построения матрицы (минимум 2)
- `from_date` (str, обязательный) - Начальная дата периода в формате YYYY-MM-DD
- `to_date` (str, обязательный) - Конечная дата периода в формате YYYY-MM-DD

**Возвращает:**
- Матрицу корреляций между инструментами
- Метаданные расчёта (метод, количество наблюдений)

**Пример:**
```python
result = await compute_correlation_matrix(
    tickers=["SBER", "GAZP", "LKOH"],
    from_date="2024-01-01",
    to_date="2024-12-31",
    ctx=ctx
)
```

### `suggest_rebalance` - Предложить ребалансировку портфеля

Формирует детерминированное предложение по ребалансировке с учётом ограничений по классам активов, концентрации и обороту.

**Параметры:**
- `positions` (list, обязательный) - Список текущих позиций портфеля с весами
- `total_portfolio_value` (float, опциональный) - Общая стоимость портфеля для расчёта сделок в валюте
- `risk_profile` (dict, опциональный) - Целевой профиль риска с ограничениями:
  - `max_single_position_weight` - Максимальная доля одной позиции (по умолчанию: 0.25)
  - `max_issuer_weight` - Максимальная доля одного эмитента (по умолчанию: 0.30)
  - `max_turnover` - Максимальный оборот (по умолчанию: 0.50)
  - `max_equity_weight` - Максимальная доля акций (по умолчанию: 1.0)
  - `target_asset_class_weights` - Целевые веса по классам активов

**Возвращает:**
- Целевые веса по тикерам после ребалансировки
- Список предлагаемых сделок (buy/sell) с оценкой стоимости
- Сводку: оборот, количество изменённых позиций, устранённые нарушения

**Пример:**
```python
result = await suggest_rebalance(
    positions=[
        {"ticker": "SBER", "current_weight": 0.45, "asset_class": "equity"},
        {"ticker": "GAZP", "current_weight": 0.20, "asset_class": "equity"},
        {"ticker": "LKOH", "current_weight": 0.15, "asset_class": "equity"},
        {"ticker": "OFZ", "current_weight": 0.20, "asset_class": "fixed_income"}
    ],
    total_portfolio_value=5000000.0,
    risk_profile={
        "max_single_position_weight": 0.25,
        "max_issuer_weight": 0.30,
        "max_turnover": 0.30
    },
    ctx=ctx
)
```

**Пример ответа:**
```json
{
  "target_weights": {
    "SBER": 0.25,
    "GAZP": 0.25,
    "LKOH": 0.25,
    "OFZ": 0.25
  },
  "trades": [
    {"ticker": "SBER", "side": "sell", "weight_delta": -0.20, "estimated_value": 1000000.0}
  ],
  "summary": {
    "total_turnover": 0.20,
    "turnover_within_limit": true,
    "positions_changed": 4,
    "concentration_issues_resolved": 1
  }
}
```

## Эндпоинты

- `GET /health` - Проверка здоровья сервера
- `GET /metrics` - Prometheus метрики (если включён мониторинг)
- `POST /mcp` - MCP протокол

## Мониторинг

При включённом мониторинге (`RISK_ENABLE_MONITORING=true`) сервер экспортирует Prometheus метрики:
- Количество вызовов инструментов
- Количество ошибок по типам
- Латентность выполнения инструментов

## Трейсинг

При настройке OpenTelemetry (`RISK_OTEL_ENDPOINT`) сервер отправляет трейсы операций для анализа производительности и отладки.

