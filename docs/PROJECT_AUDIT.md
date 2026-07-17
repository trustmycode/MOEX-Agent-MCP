# Технический аудит `MOEX-Agent-MCP`

Дата исходного среза: 17 июля 2026 года. Проверен коммит `88feede`. Оценки ниже отражают состояние исходного среза до исправлений.

## Статус исправлений

В ветке подготовки к публикации устранены основные блокирующие замечания аудита:

- имена инструментов агента приведены к фактическому реестру MCP, а `compute_tail_metrics` зарегистрирован как MCP-инструмент;
- планы запросов возвращаются независимыми копиями и больше не изменяют общий реестр;
- маршруты агента требуют служебный ключ, подробная отладочная выдача выключена по умолчанию, а внутренние исключения не возвращаются клиенту;
- MCP и агент больше не публикуют порты на узле в Compose, а локальный запуск MCP по умолчанию слушает только `127.0.0.1`;
- зависимости ограничены совместимыми основными версиями, добавлена автоматическая проверка Python и веб-приложения;
- контейнеры Python запускаются от непривилегированного пользователя.

Контрольный результат после исправлений: 532 серверных теста пройдены, 4 пропущены, 4 сетевых сценария исключены; проверка стиля и рабочая сборка веб-приложения прошли. Оставшиеся улучшения — внешнее хранилище сеансов, распределённое ограничение частоты запросов и дальнейшее сокращение блокирующего ввода-вывода.

## Итог и оценки

Это наиболее зрелый из проверенных проектов: многосервисная система аналитики Московской биржи с отдельными MCP-серверами, пакетом доступа к ISS, агентом, веб-интерфейсом и большой тестовой базой. Архитектурная идея и документация сильны, но фактические договоры между агентом и MCP расходятся, общедоступные точки входа не имеют авторизации и ограничений, а общий изменяемый конвейер создаёт гонку между запросами.

| Область | Оценка |
|---|---:|
| Архитектура | 74/100 |
| Надёжность | 56/100 |
| Поддерживаемость | 69/100 |
| Тесты | 72/100 |
| Безопасность | 36/100 |
| Инфраструктура | 54/100 |
| Документация | 88/100 |
| **Средняя** | **64/100** |

## Наиболее значимые находки

1. **Агент вызывает несуществующие инструменты.** Для отчёта ликвидности агент задаёт имя `cfo_liquidity_report` ([`packages/agent-service/src/agent_service/subagents/risk_analytics.py`](../packages/agent-service/src/agent_service/subagents/risk_analytics.py#L50)) и вызывает его ([тот же файл](../packages/agent-service/src/agent_service/subagents/risk_analytics.py#L792)), тогда как сервер регистрирует `build_cfo_liquidity_report` ([`risk_analytics_mcp/tools/cfo_liquidity_report.py`](../risk_analytics_mcp/tools/cfo_liquidity_report.py#L272)). Аналогично агент вызывает `compute_tail_metrics`, но функция не помечена как инструмент ([`risk_analytics_mcp/tools/compute_tail_metrics.py`](../risk_analytics_mcp/tools/compute_tail_metrics.py#L75)), и сервер её не регистрирует ([`risk_analytics_mcp/server.py`](../risk_analytics_mcp/server.py#L15)). Запрос фундаментальных данных также ссылается на отсутствующий инструмент ([`packages/agent-service/src/agent_service/subagents/market_data.py`](../packages/agent-service/src/agent_service/subagents/market_data.py#L50), [`moex_iss_mcp/tools/__init__.py`](../moex_iss_mcp/tools/__init__.py#L1)).
2. **Тесты закрепляют ошибочный договор.** Подмена клиента принимает любое имя, а проверки ожидают то же неверное имя ([`packages/agent-service/tests/test_risk_analytics_subagent.py`](../packages/agent-service/tests/test_risk_analytics_subagent.py#L17), [`packages/agent-service/tests/test_risk_analytics_subagent.py`](../packages/agent-service/tests/test_risk_analytics_subagent.py#L238)). Нет сквозной проверки реестра инструментов агента против живого MCP-сервера.
3. **Общие изменяемые конвейеры создают межзапросную гонку.** Реестр возвращает один и тот же объект конвейера ([`packages/agent-service/src/agent_service/orchestrator/pipelines.py`](../packages/agent-service/src/agent_service/orchestrator/pipelines.py#L323)), а оркестратор при ухудшении доступности меняет его зависимости на месте ([`packages/agent-service/src/agent_service/orchestrator/orchestrator_agent.py`](../packages/agent-service/src/agent_service/orchestrator/orchestrator_agent.py#L680)). Параллельные запросы могут влиять друг на друга, а изменение сохранится для следующих запросов.
4. **Сетевые точки входа не защищены.** `/a2a` и потоковый `/agui` принимают произвольные запросы без аутентификации и ограничения частоты ([`packages/agent-service/src/agent_service/server.py`](../packages/agent-service/src/agent_service/server.py#L195), [`packages/agent-service/src/agent_service/server.py`](../packages/agent-service/src/agent_service/server.py#L217)). Оба MCP-сервера запускаются на всех интерфейсах ([`moex_iss_mcp/server.py`](../moex_iss_mcp/server.py#L58), [`risk_analytics_mcp/server.py`](../risk_analytics_mcp/server.py#L93)).
5. **Отладочный режим раскрывает лишние данные.** По умолчанию он включён ([`packages/agent-service/src/agent_service/server.py`](../packages/agent-service/src/agent_service/server.py#L92)); первый потоковый пакет возвращает клиенту полный вход, включая состояние, сообщения и контекст ([`packages/agent-service/src/agent_service/server.py`](../packages/agent-service/src/agent_service/server.py#L242)). Исключения отдаются с типом и текстом ([`packages/agent-service/src/agent_service/server.py`](../packages/agent-service/src/agent_service/server.py#L303)).

## 1. Назначение и стек

Система получает рыночные данные MOEX ISS, считает риск и формирует агентный ответ и панель. Состав и поток хорошо описаны в [`README.md`](../README.md#L1). Серверные части написаны на Python с FastMCP, FastAPI, Pydantic, httpx и клиентами моделей; интерфейс — Next.js ([`pyproject.toml`](../pyproject.toml#L1), [`apps/web/package.json`](../apps/web/package.json#L1)).

## 2. Точки входа и компоненты

- MOEX MCP: [`moex_iss_mcp/main.py`](../moex_iss_mcp/main.py#L1) и [`moex_iss_mcp/server.py`](../moex_iss_mcp/server.py#L34).
- Risk MCP: [`risk_analytics_mcp/server.py`](../risk_analytics_mcp/server.py#L15).
- Агентные протоколы A2A и AG-UI: [`packages/agent-service/src/agent_service/server.py`](../packages/agent-service/src/agent_service/server.py#L108).
- Доступ к ISS: [`moex_iss_sdk/client.py`](../moex_iss_sdk/client.py#L34).
- Прокси веб-приложения: [`apps/web/app/api/agui/route.ts`](../apps/web/app/api/agui/route.ts#L1).

## 3. Главный поток данных

Запрос проходит через AG-UI/A2A, классифицируется и планируется, затем оркестратор выполняет шаги конвейера и вызывает MCP через клиент. Рыночный MCP обращается к ISS, риск-сервис выполняет чистые расчёты, после чего агент собирает объяснение и панель. Конвейер исполняет шаги последовательно ([`packages/agent-service/src/agent_service/orchestrator/orchestrator_agent.py`](../packages/agent-service/src/agent_service/orchestrator/orchestrator_agent.py#L697)), а итог преобразуется в потоковые события ([`packages/agent-service/src/agent_service/server.py`](../packages/agent-service/src/agent_service/server.py#L242)).

## 4. Архитектурные границы

Границы в целом удачны: пакет ISS изолирован от MCP, вычисления отделены от транспорта, агент работает через MCP-клиент. Эти намерения закреплены архитектурными тестами ([`tests/architecture/test_import_rules.py`](../tests/architecture/test_import_rules.py#L1)). Слабое место — договоры имён инструментов дублируются строками в разных пакетах и не проверяются сквозным тестом.

## 5. Обработка ошибок

Клиент ISS классифицирует сетевые ошибки и повторяет временные сбои ([`moex_iss_sdk/client.py`](../moex_iss_sdk/client.py#L421)). MCP-клиент различает тайм-ауты, ответы 4xx/5xx и повторы ([`packages/agent-service/src/agent_service/mcp/client.py`](../packages/agent-service/src/agent_service/mcp/client.py#L95)). Плохо, что карта ошибок включает исходные тексты исключений ([`moex_iss_sdk/error_mapper.py`](../moex_iss_sdk/error_mapper.py#L37)), а сетевой слой возвращает их клиенту. У повторов MCP нет задержки между попытками, что усиливает перегрузку.

## 6. Асинхронность, фоновые задачи и гонки

Асинхронный FastAPI вызывает синхронный ISS-клиент; сетевой вызов через `urlopen` блокирует поток исполнения ([`moex_iss_sdk/client.py`](../moex_iss_sdk/client.py#L421)). Хранилище сеансов — словарь в памяти с очисткой только при чтении конкретного ключа ([`packages/agent-service/src/agent_service/orchestrator/session_store.py`](../packages/agent-service/src/agent_service/orchestrator/session_store.py#L7)): нет предела, общей уборки, сохранности при перезапуске и согласованности нескольких процессов. Главная гонка — мутация общих конвейеров, описанная выше.

## 7. Транзакции и база данных

Основные данные получаются по сети и рассчитываются в памяти; собственной транзакционной базы в рабочем потоке нет. Кэш ISS локален процессу. Это уменьшает риск частичных записей, но означает отсутствие долговечного состояния сеансов и единого кэша между экземплярами.

## 8. Безопасность и секреты

Текущий поиск по дереву не обнаружил очевидного действующего ключа; образец окружения оставляет секретные поля пустыми ([`env.example`](../env.example#L13)). Ключ модели проверяется через окружение и не журналируется ([`packages/agent-service/src/agent_service/llm/client.py`](../packages/agent-service/src/agent_service/llm/client.py#L50), [`packages/agent-service/src/agent_service/llm/client.py`](../packages/agent-service/src/agent_service/llm/client.py#L273)). Основные риски: отсутствие авторизации и ограничения частоты; полный вход в отладочном событии; текст пользовательского запроса в журнале ([`packages/agent-service/src/agent_service/orchestrator/orchestrator_agent.py`](../packages/agent-service/src/agent_service/orchestrator/orchestrator_agent.py#L128)); отсутствие ограничений размера входного `Any` ([`packages/agent-service/src/agent_service/server.py`](../packages/agent-service/src/agent_service/server.py#L118)).

## 9. Тесты

Тестовая база широкая: расчёты, модели, клиенты, агенты, снимки схем и архитектурные правила. В изолированной копии команда `pytest tests -q -m 'not live'` дала **241 успешную проверку, 8 пропусков и 2 сбоя**: оба архитектурных теста требуют `/usr/local/bin/lint-imports` ([`tests/architecture/test_import_rules.py`](../tests/architecture/test_import_rules.py#L45)). Полный сбор нашёл 419 проверок, но остановился на 9 ошибках импорта из-за отсутствия зависимостей агентного пакета; зависимости не устанавливались. Также среда предупредила об отсутствующем расширении асинхронных тестов.

Критично не покрыты: соответствие реальных имён инструментов, совместный запуск трёх сервисов, конкурентные запросы к одному конвейеру, ограничение входа, авторизация и истощение хранилища сеансов.

## 10. Производительность

ISS-клиент имеет кэш, ограничение частоты, тайм-аут и повторы ([`moex_iss_sdk/client.py`](../moex_iss_sdk/client.py#L34)). При этом ответ читается целиком без верхней границы ([`moex_iss_sdk/client.py`](../moex_iss_sdk/client.py#L456)); независимые шаги конвейера выполняются последовательно; несколько запасных способов структурированного вызова модели могут умножать стоимость и задержку ([`packages/agent-service/src/agent_service/llm/client.py`](../packages/agent-service/src/agent_service/llm/client.py#L106)). Веб-прокси читает всё тело запроса и не задаёт тайм-аут ([`apps/web/app/api/agui/route.ts`](../apps/web/app/api/agui/route.ts#L13)).

## 11. Логи и наблюдаемость

Есть проверки здоровья и показатели MCP ([`moex_iss_mcp/server.py`](../moex_iss_mcp/server.py#L95), [`risk_analytics_mcp/server.py`](../risk_analytics_mcp/server.py#L130)), структурированное журналирование и деградация. Не хватает сквозного идентификатора запроса, распределённой трассировки, метрик стоимости модели, заполнения очередей и размера сеансов. В журналах следует редактировать запрос пользователя и финансовые данные.

## 12. Docker, автоматизация и воспроизводимость

Compose поднимает сервисы и описывает зависимости ([`docker-compose.yml`](../docker-compose.yml#L1)); Dockerfile веб-приложения переводит процесс на непривилегированного пользователя ([`apps/web/Dockerfile`](../apps/web/Dockerfile#L23)). Недостатки: образы не закреплены по хешам, Python-зависимости имеют диапазоны и нет единого файла блокировки ([`pyproject.toml`](../pyproject.toml#L1), [`packages/agent-service/requirements.txt`](../packages/agent-service/requirements.txt#L1)); Python-контейнеры запускаются от root и обновляют установщик при сборке ([`packages/agent-service/Dockerfile`](../packages/agent-service/Dockerfile#L1)); автоматизация GitHub Actions отсутствует.

## 13. Документация

README хорошо описывает схему, запуск, переменные и инструменты ([`README.md`](../README.md#L23), [`README.md`](../README.md#L40), [`README.md`](../README.md#L106)). Есть отдельные архитектурные документы. Слабости: локальный абсолютный путь в инструкции запуска ([`README.md`](../README.md#L52)) и расхождение документации инструментов с фактической регистрацией.

## 14. Часть AI/LLM

Сильные стороны: структурированный результат, запасные режимы, тайм-аут и повторы ([`packages/agent-service/src/agent_service/llm/client.py`](../packages/agent-service/src/agent_service/llm/client.py#L71), [`packages/agent-service/src/agent_service/llm/client.py`](../packages/agent-service/src/agent_service/llm/client.py#L187)). Риски: общий изменяемый конвейер, отладочная выдача исходных данных, возможная передача чувствительных портфелей внешнему поставщику, отсутствие явного бюджета запросов и оценки качества на эталонном наборе. Для финансовой аналитики нужен явный отказ от инвестиционной рекомендации и проверка численных результатов независимо от текста модели.

## 15. Риски публичной публикации

Прямых секретов в текущем дереве не найдено. Перед публичным сканированием следует исправить несуществующие инструменты, убрать отладочный режим по умолчанию, закрыть сетевые точки входа, добавить автоматическую проверку и закрепить зависимости. Финансовые примеры и документация должны ясно отделять аналитический прототип от инвестиционной рекомендации.

## Приоритет действий

1. Ввести единый типизированный реестр инструментов и сквозной тест агент → живой MCP.
2. Запретить мутацию общих конвейеров: копировать план на запрос или сделать его неизменяемым.
3. Добавить аутентификацию, права, ограничение частоты/размера и безопасные ошибки.
4. Выключить отладочную выдачу по умолчанию и редактировать чувствительные поля журналов.
5. Сделать сеансы ограниченными и внешними; убрать блокирующий ввод-вывод из асинхронного пути.
6. Закрепить зависимости, непривилегированных пользователей и автоматическую проверку.
