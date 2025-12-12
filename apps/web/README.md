# AG-UI для MOEX Market Analyst Agent

Next.js UI, который общается с агентом по SSE (`/agui`) и отображает текст, таблицы и дашборды риска.

## Быстрый старт (локально)
```bash
cd apps/web
pnpm install        # или npm/yarn
pnpm dev            # порт 3000
```
Открыть: http://localhost:3000

Переменные окружения (см. корневой `.env`):
- `WEB_PORT` — порт UI (по умолчанию 3000)
- `AGENT_SERVICE_URL` — endpoint агента для AG-UI, например `http://localhost:8100/agui` или `http://agent:8100/agui` в docker-compose.

## Через docker-compose (рекомендуется)
В корне репозитория:
```bash
make local-up   # поднимет moex-iss-mcp, risk-analytics-mcp, agent, web
```
UI доступен на `http://localhost:${WEB_PORT:-3000}`.

## Функциональность
- Чат с агентом (A2A/AG-UI протокол).
- Отображение TEXT_MESSAGE_* и STATE_SNAPSHOT (дашборд/таблицы).
- Передача `state`/`context` для сценариев (parsed_params, locale, user_role).

## Деплой
- Платформа: linux/amd64.
- Dockerfile в `apps/web/Dockerfile`, аргумент `NEXT_DISABLE_SOURCEMAPS=1` по умолчанию.
- В Evolution AI Agents UI указывайте `AGENT_SERVICE_URL` на внешний адрес агента.

