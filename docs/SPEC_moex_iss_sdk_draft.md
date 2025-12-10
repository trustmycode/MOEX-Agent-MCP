# Черновой SPEC — moex_iss_sdk (Фаза 0.4)

Черновик фиксирует требования к SDK на основе существующих документов
(`docs/SPEC_moex-iss-mcp.md`, `architecture/sdk/ARCH-sdk-moex-iss-v1.md`,
`architecture/mcp/ARCH-mcp-moex-iss-v1.md`, Q&A и задачи фаз 0–1).
Фокус — какие вызовы ISS уже используются `moex-iss-mcp`, какие поля
нужны доменной логике и какие методы должен предоставить `IssClient`.

## 1. Обращения к MOEX ISS внутри moex-iss-mcp

- **Ресурсы ISS** — только публичные JSON-таблицы (`iss.meta=off`).
- **Базовый URL** — `https://iss.moex.com/iss/` (переопределяемый).
- **Общие ограничения**:
  - `MAX_LOOKBACK_DAYS = 730`, валидация `from_date <= to_date`.
  - Интервалы OHLCV: `"1d"` → `interval=24`, `"1h"` → `interval=60`.
  - Дефолтный борд для акций: `"TQBR"`.
  - Ошибки ISS нормализуются в `InvalidTickerError | DateRangeTooLargeError | IssTimeoutError | IssServerError | UnknownIssError`.

### 1.1. get_security_snapshot (tool `get_security_snapshot`)

- **Endpoint**: `engines/stock/markets/shares/boards/{board}/securities/{ticker}.json`
  - query: `iss.meta=off`, `iss.only=marketdata,marketdata_yields`.
- **Используемые поля** (`marketdata`):
  - `TIME | SYSTIME` → `as_of` (UTC).
  - `LAST | LASTPRICE | LCLOSEPRICE` → `last_price`.
  - `LASTCHANGE | CHANGE` → `price_change_abs`.
  - `LASTCHANGEPRC | PRC` → `price_change_pct`.
  - `OPEN`, `HIGH`, `LOW`, `VOLUME | VOLTODAY`, `VALTODAY | VALUE`.
- **Поведение**:
  - Пустая таблица → `InvalidTickerError`.
  - Кэшируемая операция (TTL ~30 c), используется MCP метрика `intraday_volatility_estimate` поверх `high/low/last`.

### 1.2. get_ohlcv_series (tool `get_ohlcv_timeseries`)

- **Endpoint**: `engines/stock/markets/shares/securities/{ticker}/candles.json`
  - query: `from`, `till`, `interval` (`24`/`60`), `boardid`, `iss.meta=off`.
- **Используемые поля** (`candles`):
  - `begin | datetime | time` → `ts`.
  - `open`, `high`, `low`, `close`, `volume`, `value`.
- **Поведение**:
  - Проверка дат (`from_date <= to_date`, длительность ≤ `MAX_LOOKBACK_DAYS`), иначе `DateRangeTooLargeError`.
  - Пустая таблица → `InvalidTickerError`.
  - Данные используются для расчёта MCP-метрик: `total_return_pct`, `annualized_volatility`, `avg_daily_volume`.
  - Кэширование опционально и обычно отключено на длинных периодах.

### 1.3. get_index_constituents (tool `get_index_constituents_metrics`)

- **Endpoint**: `statistics/engines/stock/markets/index/analytics/{index_ticker}.json`
  - query: `date`, `iss.meta=off`.
- **Используемые поля** (`analytics`):
  - `ticker | secids` → `ticker`.
  - `weight | weight_cc` → `weight_pct`.
  - `LAST | PRICE` → `last_price`.
  - `LASTCHANGEPRC | CHANGE_PCT` → `price_change_pct`.
  - Дополнительно, если есть: `SECTOR | sector`, `BOARDID | board`, `FIGI | ISIN` для трассировки.
- **Поведение**:
  - Маппинг `index_ticker` → ISS `indexid` (`IMOEX`, `RTSI`) с кэшем 24ч; при отсутствии → ошибка `UNKNOWN_INDEX` на уровне MCP.
  - Пустая таблица → `InvalidTickerError`.
  - Используется для расчёта MCP-метрик `top5_weight_pct`, `num_constituents`.

### 1.4. get_security_dividends (используется в risk-analytics-mcp и перспективных tools)

- **Endpoint**: `securities/{ticker}/dividends.json`
  - query: `from`, `till`, `iss.meta=off`.
- **Используемые поля** (`dividends`):
  - `BOARDID`, `value`, `currencyid`.
  - `registryclosedate | registry_close_date` → `registry_close_date`.
  - `paymentdate | payment_date`, `declaredate | announcement_date`.
  - `yield` (если доступно).
- **Поведение**:
  - Проверка периода аналогична OHLCV.
  - Пустая таблица → `InvalidTickerError`.
  - Кэшируемая операция (дивиденды меняются редко).

## 2. Требуемые методы IssClient и связь с MCP

- `get_security_snapshot(ticker: str, board: str = "TQBR") -> SecuritySnapshot`
  - Используется tool `get_security_snapshot`.
  - Ошибки: `InvalidTickerError`, сетевые (`IssTimeoutError`, `IssServerError`, `UnknownIssError`).

- `get_ohlcv_series(ticker: str, board: str, from_date: date, to_date: date, interval: Literal["1d","1h"]) -> list[OhlcvBar]`
  - Используется tool `get_ohlcv_timeseries` и расчёты risk-analytics.
  - Ошибки: `DateRangeTooLargeError`, `InvalidTickerError`, сетевые/5xx.

- `get_index_constituents(index_ticker: str, as_of_date: date) -> list[IndexConstituent]`
  - Используется tool `get_index_constituents_metrics`; маппинг индекса кэшируется.
  - Ошибки: `InvalidTickerError`, `UnknownIssError` при сетевых сбоях; `UNKNOWN_INDEX` маппится на MCP-слое.

- `get_security_dividends(ticker: str, from_date: date, to_date: date) -> list[DividendRecord]`
  - Используется в risk-analytics сценариях (дивидендные корректировки/доходность).
  - Ошибки: `DateRangeTooLargeError`, `InvalidTickerError`, сетевые/5xx.

## 3. Модели данных и используемые поля

- **SecuritySnapshot**: `ticker`, `board`, `as_of`, `last_price`, `price_change_abs`, `price_change_pct`, `open_price`, `high_price`, `low_price`, `volume`, `value`, `raw`.
- **OhlcvBar**: `ts`, `open`, `high`, `low`, `close`, `volume`, `value`, опционально `board`, `currency`, `raw`.
- **IndexConstituent**: `index_ticker`, `ticker`, `weight_pct`, `last_price`, `price_change_pct`, `sector`, `board`, `figi`, `isin`, `raw`.
- **DividendRecord**: `ticker`, `board`, `dividend`, `currency`, даты `registry_close_date/record_date/payment_date/announcement_date`, `yield_pct`, `raw`.

Модели допускают дополнительные поля в `raw` для устойчивости к изменениям ISS.

## 4. Ограничения и умолчания (для SDK и MCP)

- Нормализация дат: если пользователь не передал период, агент/MCP подставляет `to_date=today (UTC)`, `from_date=to_date-365`.
- Лимит истории: `MAX_LOOKBACK_DAYS=730`, нарушение → `DATE_RANGE_TOO_LARGE`.
- Режимы тайм-аута и rate limiting задаются env: `MOEX_ISS_BASE_URL`, `MOEX_ISS_RATE_LIMIT_RPS`, `MOEX_ISS_TIMEOUT_SECONDS`, `ENABLE_CACHE`, `CACHE_TTL_SECONDS`, `CACHE_MAX_SIZE`, `MOEX_ISS_MAX_LOOKBACK_DAYS`.
- Все сетевые ошибки/тайм-ауты переводятся в исключения SDK и далее в MCP `error_type` без утечки HTTP-деталей.

## 5. Кэширование

- Флаг `ENABLE_CACHE=true` активирует LRU+TTL кэш SDK (`TTLCache`), настраиваемый через `CACHE_TTL_SECONDS`, `CACHE_MAX_SIZE`.
- Кэшируются идемпотентные операции:
  - `get_security_snapshot`;
  - `get_index_constituents`;
  - `get_security_dividends`;
  - `get_ohlcv_series` — опционально, обычно только для коротких диапазонов; при необходимости MCP может передать собственный кэш.
- Ключ кэша собирается из имени операции и нормализованных аргументов; истечение TTL или превышение размера приводит к вытеснению по LRU.
- При `ENABLE_CACHE=false` все методы обращаются напрямую в ISS.

## 6. Исключения и маппинг в MCP

Исключения SDK → `error_type` MCP:

| Исключение SDK             | error_type         | Когда возникает                                   |
|----------------------------|--------------------|---------------------------------------------------|
| `InvalidTickerError`       | `INVALID_TICKER`   | Пустой ответ ISS / 404 по тикеру/борду            |
| `DateRangeTooLargeError`   | `DATE_RANGE_TOO_LARGE` | Диапазон дат превышает лимит или from>to      |
| `TooManyTickersError`      | `TOO_MANY_TICKERS` | Запрос с пачкой тикеров превысил лимит            |
| `IssTimeoutError`          | `ISS_TIMEOUT`      | Тайм-аут сетевого запроса                         |
| `IssServerError`           | `ISS_5XX`          | Ответы 5xx или повторные ошибки транспорта        |
| `UnknownIssError`          | `UNKNOWN`          | Любые иные непредвиденные ситуации                 |

## 7. Пример использования в MCP

```python
from moex_iss_sdk import IssClient, IssClientSettings, InvalidTickerError, IssTimeoutError

settings = IssClientSettings.from_env()  # учитывает ENABLE_CACHE/CACHE_TTL_SECONDS и т.д.
client = IssClient(settings)

try:
    snapshot = client.get_security_snapshot("SBER", "TQBR")
    print(snapshot.last_price)
except InvalidTickerError as exc:
    error_type = "INVALID_TICKER"
    details = exc.details
except IssTimeoutError:
    error_type = "ISS_TIMEOUT"
```

## 8. Переменные окружения (основные)

- `MOEX_ISS_BASE_URL` — базовый URL ISS (по умолчанию `https://iss.moex.com/iss/`).
- `MOEX_ISS_DEFAULT_BOARD` — дефолтный борд (по умолчанию `TQBR`).
- `MOEX_ISS_DEFAULT_INTERVAL` — дефолтный интервал свечей (`1d` или `1h`, по умолчанию `1d`).
- `MOEX_ISS_RATE_LIMIT_RPS` — лимит RPS (по умолчанию 3).
- `MOEX_ISS_TIMEOUT_SECONDS` — тайм-аут HTTP (по умолчанию 10).
- `MOEX_ISS_MAX_LOOKBACK_DAYS` — максимальная глубина истории (по умолчанию 730).
- `ENABLE_CACHE` — включает кэш.
- `CACHE_TTL_SECONDS`, `CACHE_MAX_SIZE` — параметры кэша.
