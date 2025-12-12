# AG-UI для MOEX Market Analyst Agent

Next.js UI, который общается с агентом по SSE (`/agui`) и показывает сообщения, таблицы и риск-дашборды.

## Быстрый старт (локально)
```bash
cd /Users/Admin/CursorProject/MOEX-Agent-MCP/apps/web
pnpm install           # или npm/yarn
pnpm dev               # порт 3000
```
Открыть: http://localhost:${WEB_PORT:-3000}

## Переменные окружения
- `WEB_PORT` — порт UI (по умолчанию 3000)
- `AGENT_SERVICE_URL` — endpoint агента для AG-UI, например `http://localhost:8100/agui` или `http://agent:8100/agui` в docker-compose
- Использует корневой `.env` (см. `env.example`)

## Сборка и запуск (prod-режим)
```bash
pnpm build
pnpm start --hostname 0.0.0.0 --port ${WEB_PORT:-3000}
```

## Docker / compose
- Образ: `docker build -t moex-market-analyst-web:local -f apps/web/Dockerfile .`
- Запуск: `docker run -p 3000:3000 --env-file env.example moex-market-analyst-web:local`
- В составе стека: `make local-up` в корне (поднимет web + MCP + агент).

## Проверки
- Линт: `pnpm lint`

## Траблшутинг
- SSE 404/timeout: проверьте `AGENT_SERVICE_URL` и доступность агента.
- Пустые данные в дашборде: убедитесь, что MCP-сервера запущены или доступны из агента.
