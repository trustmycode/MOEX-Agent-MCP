# Подготовка к собеседованию по `MOEX-Agent-MCP`

## Рассказ о проекте

`MOEX-Agent-MCP` — агентная система финансовой аналитики. Один MCP-сервис инкапсулирует MOEX ISS, второй выполняет детерминированные расчёты риска, агент планирует цепочку вызовов и формирует объяснение и панель, а Next.js передаёт поток AG-UI. Сильная сторона — разделение получения данных, чистых вычислений и представления, большая тестовая база и хорошая документация. Аудит выявил, что границы правильные концептуально, но договоры инструментов расходятся на уровне строк, а безопасность сетевого контура и конкурентная изоляция пока не готовы к эксплуатации.

## 20 вопросов и ответы

1. **Зачем здесь MCP?** Он отделяет типизированные инструменты данных и расчётов от логики агента; серверы регистрируются отдельно ([`moex_iss_mcp/server.py`](../moex_iss_mcp/server.py#L34), [`risk_analytics_mcp/server.py`](../risk_analytics_mcp/server.py#L15)).
2. **Каков главный поток?** AG-UI/A2A → планировщик → конвейер → MCP-клиенты → объяснение и панель ([`README.md`](../README.md#L23)).
3. **Почему расчёты вынесены из модели?** Численные результаты должны быть детерминированными и тестируемыми; модель отвечает за план и объяснение.
4. **Как обрабатываются сбои ISS?** Тайм-ауты, ограничение частоты, кэш и повторы находятся в [`moex_iss_sdk/client.py`](../moex_iss_sdk/client.py#L34).
5. **Какая главная функциональная ошибка была найдена и исправлена?** Имена инструментов агента не совпадали с реестром сервера; исправление унифицировало имя отчёта ликвидности и зарегистрировало хвостовые метрики ([`risk_analytics.py`](../packages/agent-service/src/agent_service/subagents/risk_analytics.py#L50), [`cfo_liquidity_report.py`](../risk_analytics_mcp/tools/cfo_liquidity_report.py#L272), [`compute_tail_metrics.py`](../risk_analytics_mcp/tools/compute_tail_metrics.py#L75)).
6. **Почему тесты её не поймали?** Подмена принимает строку и проверяет ту же строку; живой реестр не участвует ([`test_risk_analytics_subagent.py`](../packages/agent-service/tests/test_risk_analytics_subagent.py#L17)).
7. **Как исправить договоры?** Генерировать клиентские имена из схемы сервера либо проверять реестр в сквозном тесте при каждой сборке.
8. **Где гонка?** Общий объект конвейера мутируется для одного запроса и остаётся изменённым для других ([`pipelines.py`](../packages/agent-service/src/agent_service/orchestrator/pipelines.py#L323), [`orchestrator_agent.py`](../packages/agent-service/src/agent_service/orchestrator/orchestrator_agent.py#L680)).
9. **Как устранить гонку?** Неизменяемые описания и отдельный экземпляр плана на запрос.
10. **Как хранятся сеансы?** В словаре процесса с ленивым сроком жизни ([`session_store.py`](../packages/agent-service/src/agent_service/orchestrator/session_store.py#L7)); для нескольких экземпляров нужен внешний ограниченный накопитель.
11. **Какие точки входа есть?** `/health`, `/a2a`, `/agui` в [`server.py`](../packages/agent-service/src/agent_service/server.py#L195).
12. **Главный риск безопасности?** На них нет аутентификации и ограничения частоты, а отладка возвращает полный вход ([`server.py`](../packages/agent-service/src/agent_service/server.py#L242)).
13. **Как устроены повторы модели?** Есть тайм-аут, экспоненциальная задержка и запасные режимы структурированного ответа ([`llm/client.py`](../packages/agent-service/src/agent_service/llm/client.py#L187)).
14. **Что контролировать по стоимости?** Число запасных вызовов, токены, модель, длительность и квоты пользователя.
15. **Что показал запуск тестов?** Основной набор: 241 успех, 8 пропусков, 2 сбоя из-за жёсткого `/usr/local/bin/lint-imports` ([`test_import_rules.py`](../tests/architecture/test_import_rules.py#L45)).
16. **Каких тестов не хватает?** Живого договора MCP, параллельных запросов, авторизации, пределов входа и деградации всех сервисов вместе.
17. **Почему синхронный ISS-клиент опасен?** Он блокирует асинхронный обработчик во время `urlopen` ([`moex_iss_sdk/client.py`](../moex_iss_sdk/client.py#L421)).
18. **Что хорошего в наблюдаемости?** Оба MCP имеют здоровье и показатели ([`risk_analytics_mcp/server.py`](../risk_analytics_mcp/server.py#L130)); не хватает сквозной трассировки и стоимости модели.
19. **Готов ли проект к публичной эксплуатации?** Нет: сначала договоры инструментов, изоляция запросов, сетевой доступ и воспроизводимая сборка.
20. **Как честно оценить проект?** Архитектурно сильный прототип с хорошими тестами ядра, но с несколькими интеграционными и эксплуатационными разрывами.

## Слабые места

- Строковые договоры инструментов расходятся.
- Конвейеры изменяются между запросами.
- Сеансы процессные и неограниченные.
- Отсутствуют аутентификация и ограничение частоты.
- Отладка включена по умолчанию и возвращает лишние данные.
- Нет автоматической проверки репозитория и единой фиксации Python-зависимостей.
- Асинхронный путь содержит блокирующие вызовы.

## Файлы для изучения

1. [`README.md`](../README.md#L1) — карта системы.
2. [`packages/agent-service/src/agent_service/server.py`](../packages/agent-service/src/agent_service/server.py#L108) — протоколы и поток событий.
3. [`packages/agent-service/src/agent_service/orchestrator/orchestrator_agent.py`](../packages/agent-service/src/agent_service/orchestrator/orchestrator_agent.py#L650) — исполнение и гонка.
4. [`packages/agent-service/src/agent_service/orchestrator/pipelines.py`](../packages/agent-service/src/agent_service/orchestrator/pipelines.py#L323) — реестр планов.
5. [`packages/agent-service/src/agent_service/mcp/client.py`](../packages/agent-service/src/agent_service/mcp/client.py#L55) — транспорт MCP.
6. [`moex_iss_sdk/client.py`](../moex_iss_sdk/client.py#L34) — кэш, повторы и ISS.
7. [`risk_analytics_mcp/server.py`](../risk_analytics_mcp/server.py#L15) — фактический набор инструментов.
8. [`packages/agent-service/src/agent_service/subagents/risk_analytics.py`](../packages/agent-service/src/agent_service/subagents/risk_analytics.py#L50) — ошибочные имена.
9. [`packages/agent-service/src/agent_service/llm/client.py`](../packages/agent-service/src/agent_service/llm/client.py#L71) — структурированный ответ модели.
10. [`tests/architecture/test_import_rules.py`](../tests/architecture/test_import_rules.py#L1) — архитектурные ограничения и проблема переносимости.

## Короткая позиция на собеседовании

«Я разделил недетерминированное планирование и детерминированные финансовые вычисления через MCP. Это облегчает тестирование и замену источников. Аудит показал, что следующий этап зрелости — сделать договоры инструментов машиночитаемыми, изолировать план на запрос, закрыть внешние точки входа и добавить настоящие сквозные проверки. Численные ответы не должны зависеть от доверия к тексту модели».
