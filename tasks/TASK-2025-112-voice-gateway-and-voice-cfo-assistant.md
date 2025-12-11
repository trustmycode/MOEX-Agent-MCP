---
id: TASK-2025-112
title: "Voice Gateway и голосовой CFO-ассистент (7/9)"
status: backlog
priority: low
type: feature
estimate: 24h
assignee: @unassigned
created: 2025-12-11
updated: 2025-12-11
parents: [TASK-2025-004, TASK-2025-105]
children: []
arch_refs: [ARCH-agent-moex-market-analyst]
risk: medium
benefit: "Добавляет голосовой интерфейс для сценариев portfolio_risk и cfo_liquidity_report, улучшая UX для CFO и демонстрационную ценность."
audit_log:
  - {date: 2025-12-11, user: "@AI-Codex", action: "created with status backlog"}
---

## Описание

Реализовать компонент `Voice Gateway` и базовый сценарий `voice_cfo_assistant`, при котором:

- CFO задаёт голосовой запрос через Web UI (например, «Оцени риск моего портфеля и расскажи, что изменилось за месяц»);
- аудио попадает в Voice Gateway, который вызывает ASR-модель (Whisper Large v3 / Foundation Models) и получает текст;
- Voice Gateway формирует A2A-запрос к `moex-market-analyst-agent` с этим текстом;
- агент выполняет сценарий `portfolio_risk` и/или `cfo_liquidity_report`, формируя `output.text` и `output.dashboard`;
- Voice Gateway возвращает результат в UI (текст + дашборд, опционально — через TTS).

## Критерии приемки

- Реализован легковесный сервис/компонент `Voice Gateway` (отдельный сервис или модуль в составе Web-UI), который:
  - принимает аудиофайлы/потоки от Web UI по HTTP/WebSocket;
  - вызывает ASR через Evolution Foundation Models API с заданной моделью (Whisper Large v3 или аналог);
  - формирует A2A-запрос к `moex-market-analyst-agent` и проксирует ответ обратно в UI;
  - не обращается к MCP и не содержит бизнес-логики сценариев.
- В REQUIREMENTS зафиксированы FR-VOICE-1/2 и соответствующие NFR (латентность, поддержка русского языка и тикеров).
- Подготовлен тестовый flow:
  - пример аудио-файла/стрима;
  - конфигурация Voice Gateway и агента;
  - проверка, что голосовой запрос приводит к тому же `output.text` и `output.dashboard`, что и эквивалентный текстовый запрос.
- (Опционально) реализован простой TTS-флоу (через внешний сервис), который озвучивает `output.text` и возвращает аудио-ответ.

## Определение готовности

- В dev-окружении можно:
  - записать голосовой запрос CFO;
  - отправить его через Voice Gateway;
  - получить в UI отчёт по портфелю (Risk Dashboard + текст) без ручного ввода текста.
- Архитектура голосового слоя не ломает существующий текстовый интерфейс и не усложняет MCP-слой.

