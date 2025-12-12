# E2E Тестирование Мультиагентной Архитектуры

Данная директория содержит скрипты для тестирования мультиагентной архитектуры MOEX Market Analyst Agent.

## Требования

1. Python 3.11+
2. Установленные зависимости проекта (`uv sync` или `pip install -e .`)
3. Запущенные MCP-серверы (см. ниже)

## Структура файлов

```
examples/
├── README.md           # Эта документация
├── manual_test.py      # Ручное тестирование с mock-сабагентами
└── e2e_test.py         # E2E тестирование с реальными MCP-серверами
```

## Быстрый старт E2E тестирования

### Шаг 1: Запуск MCP-серверов

Откройте **три терминала**:

**Терминал 1 — moex-iss-mcp (порт 8000):**
```bash
cd /path/to/MOEX-Agent-MCP
python -m moex_iss_mcp.main
```

**Терминал 2 — risk-analytics-mcp (порт 8010):**
```bash
cd /path/to/MOEX-Agent-MCP
python -m risk_analytics_mcp.main
```

### Шаг 2: Запуск E2E тестов

**Терминал 3 — E2E тесты:**
```bash
cd /path/to/MOEX-Agent-MCP/packages/agent-service
python examples/e2e_test.py
```

## Режимы запуска

### Интерактивный режим (по умолчанию)

```bash
python examples/e2e_test.py
```

Открывает интерактивное меню с опциями:
- Тест MCP-клиентов напрямую
- Тест сабагентов
- Тест полного pipeline через оркестратор
- Кастомные запросы

### Командная строка (для CI/CD)

```bash
# Запустить все тесты
python examples/e2e_test.py --all

# Только MCP-клиенты
python examples/e2e_test.py --mcp

# Только сабагенты
python examples/e2e_test.py --subagents

# Только оркестратор
python examples/e2e_test.py --orchestrator
```

## Конфигурация

URL MCP-серверов можно переопределить через переменные окружения:

```bash
MOEX_ISS_MCP_URL=http://localhost:8000 \
RISK_ANALYTICS_MCP_URL=http://localhost:8001 \
python examples/e2e_test.py
```

## Что тестируется

### 1. Прямые вызовы MCP-клиентов

Проверяет работу `McpClient` с JSON-RPC протоколом:
- `get_security_snapshot` — снимок данных по бумаге
- `get_ohlcv_timeseries` — исторические котировки
- `compute_portfolio_risk_basic` — базовый портфельный риск

### 2. Сабагенты

Проверяет работу реальных сабагентов:
- `MarketDataSubagent` — получение рыночных данных через moex-iss-mcp
- `RiskAnalyticsSubagent` — риск-аналитика через risk-analytics-mcp

### 3. Оркестратор (полный pipeline)

Проверяет полный цикл обработки запросов:
1. Классификация intent → определение ScenarioType
2. Выбор pipeline сабагентов
3. Последовательное выполнение сабагентов
4. Агрегация результатов в A2A-ответ

## Сценарии тестирования

| Сценарий | Запрос | Сабагенты |
|----------|--------|-----------|
| `portfolio_risk` | "Оцени риск портфеля: SBER 40%, GAZP 30%, LKOH 30%" | market_data → risk_analytics → dashboard → explainer |
| `security_overview` | "Дай обзор акции SBER" | market_data → explainer |
| `cfo_liquidity` | "Сформируй отчёт для CFO" | risk_analytics → dashboard → explainer |

## Решение проблем

### MCP-сервер недоступен

```
❌ moex-iss-mcp недоступен: http://localhost:8000
```

**Решение:** Убедитесь, что MCP-сервер запущен на указанном порту.

### Ошибка INVALID_TICKER

```
Ошибка получения данных по XXXXX: INVALID_TICKER
```

**Решение:** Используйте реальные тикеры с MOEX (SBER, GAZP, LKOH, и т.д.).

### Timeout

```
MCP call timeout (attempt 1/3)
```

**Решение:** 
1. Проверьте подключение к интернету (MCP обращается к MOEX ISS API)
2. Увеличьте таймаут в `McpConfig`

## Сравнение с manual_test.py

| Характеристика | manual_test.py | e2e_test.py |
|---------------|----------------|-------------|
| MCP-серверы | Mock (эмуляция) | Реальные |
| Данные | Захардкожены | Реальные с MOEX |
| Зависимости | Нет | MCP-серверы должны быть запущены |
| Скорость | Быстро | Зависит от сети |
| Использование | Unit-тестирование логики | Интеграционное E2E тестирование |

## Docker Compose (опционально)

Для запуска MCP-серверов через Docker:

```bash
# moex-iss-mcp
docker-compose -f moex_iss_mcp/docker-compose.yml up -d

# risk-analytics-mcp
docker-compose -f risk_analytics_mcp/docker-compose.yml up -d
```

> Проверьте `docker-compose.yml` файлы для настройки портов.


