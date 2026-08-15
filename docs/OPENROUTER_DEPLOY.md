# Настройка OpenRouter и развёртывание

Документ описывает подготовку MCP-серверов и агента `moex-market-analyst-agent` к локальному и промышленному запуску. OpenRouter используется как единая точка доступа к языковым моделям.

## 1. Выбранные модели

- Основная: `google/gemini-3.7-flash`.
- Резервная: `openai/gpt-5.6-luna`.
- Уровень рассуждения: `low`.

При временной ошибке основной модели клиент повторяет запрос, а затем переключается на резервную. Для структурированного ответа сначала используется схема JSON, затем обычный объект JSON и вызов инструмента.

## 2. Ключ OpenRouter

1. Создайте ключ в панели OpenRouter.
2. Скопируйте `env.example` в `.env`.
3. Укажите `OPENROUTER_API_KEY` только в локальном файле `.env` или в хранилище секретов среды развёртывания.
4. Не добавляйте ключ в систему контроля версий и журналы.

Без ключа служба запускается, но планировщик и формирование отчёта используют локальные имитационные ответы.

## 3. Переменные агента

| Переменная | Назначение | Значение по умолчанию | Секрет |
| --- | --- | --- | --- |
| `AGENT_API_KEY` | Служебная авторизация запросов к агенту | нет | да |
| `AGENT_PORT` | Порт службы агента | `8100` | нет |
| `AGENT_ENABLE_DEBUG` | Отладочные данные в ответе | `false` | нет |
| `AGENT_STEP_TIMEOUT_SECONDS` | Ограничение времени одного шага | `120` | нет |
| `MOEX_ISS_MCP_URL` | Адрес MCP-сервера рыночных данных | `http://moex-iss-mcp:8000` | нет |
| `RISK_ANALYTICS_MCP_URL` | Адрес MCP-сервера расчёта риска | `http://risk-analytics-mcp:8010` | нет |
| `OPENROUTER_API_KEY` | Ключ доступа OpenRouter | нет | да |
| `OPENROUTER_API_BASE` | Базовый адрес программного интерфейса | `https://openrouter.ai/api/v1` | нет |
| `OPENROUTER_MODEL` | Основная модель | `google/gemini-3.7-flash` | нет |
| `OPENROUTER_FALLBACK_MODEL` | Резервная модель | `openai/gpt-5.6-luna` | нет |
| `OPENROUTER_REASONING_EFFORT` | Уровень рассуждения | `low` | нет |
| `OPENROUTER_SITE_URL` | Адрес приложения для атрибуции | `http://localhost:3000` | нет |
| `OPENROUTER_APP_NAME` | Название приложения для атрибуции | `MOEX Market Analyst` | нет |

## 4. Локальный запуск

```bash
cp env.example .env
# заполните AGENT_API_KEY и OPENROUTER_API_KEY
make local-up
```

Проверьте готовность служб:

```bash
curl http://localhost:8000/health
curl http://localhost:8010/health
curl http://localhost:8100/health
```

Веб-приложение доступно по адресу `http://localhost:3000`.

## 5. Сборка образов

```bash
docker buildx build --platform linux/amd64 -t <registry>/<project>/moex-iss-mcp:<tag> -f moex_iss_mcp/Dockerfile .
docker buildx build --platform linux/amd64 -t <registry>/<project>/risk-analytics-mcp:<tag> -f risk_analytics_mcp/Dockerfile .
docker buildx build --platform linux/amd64 -t <registry>/<project>/moex-market-analyst-agent:<tag> -f packages/agent-service/Dockerfile .
```

Каждый MCP-сервер должен предоставлять `/mcp`, `/health` и `/metrics`. Агент предоставляет `POST /a2a`, `POST /agui` и `GET /health`.

## 6. Учёт стоимости

После каждого успешного ответа клиент записывает в журнал запрошенную и фактическую модель, входные, кэшированные и выходные токены, а также стоимость, если OpenRouter вернул её. Содержимое запросов, ответов и ключ доступа в эту запись не входят.

## 7. Проверка перед публикацией

- Образы собраны для целевой платформы.
- MCP-серверы отвечают на `/mcp` и `/health`.
- `AGENT_API_KEY` и `OPENROUTER_API_KEY` переданы через хранилище секретов.
- Внешний адрес в `OPENROUTER_SITE_URL` соответствует развёрнутому приложению.
- Проверочный сценарий проходит против развёрнутого стека.
