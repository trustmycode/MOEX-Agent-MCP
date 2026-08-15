# План реализации переноса на OpenRouter

> **Для исполнителей:** обязательно применять `superpowers:test-driven-development` для каждого изменения поведения и `superpowers:verification-before-completion` перед заявлениями о готовности. Шаги отмечаются флажками `- [ ]`.

**Цель:** полностью заменить интеграцию Evolution Foundation Models на OpenRouter с Gemini 3.7 Flash как основной моделью и GPT-5.6 Luna как резервной.

**Архитектура:** существующий совместимый с OpenAI клиент переименовывается и получает настройки OpenRouter, заголовки приложения, уровень рассуждения и безопасный учёт использования. Один клиент остаётся общей зависимостью планировщика и формирователя отчёта; при временных ошибках он повторяет запрос основной модели, затем использует резервную.

**Технологии:** Python 3.12, `openai.AsyncOpenAI`, FastAPI, pytest, Docker Compose, OpenRouter Chat Completions.

## Общие ограничения

- Базовый адрес: `https://openrouter.ai/api/v1`.
- Основная модель: `google/gemini-3.7-flash`.
- Резервная модель: `openai/gpt-5.6-luna`.
- Уровень рассуждения: `low`.
- Новые секреты читаются только из `OPENROUTER_API_KEY`.
- Переменные `LLM_*` и `EVOLUTION_*` не поддерживаются.
- Без ключа используются существующие детерминированные имитации модели.
- Секреты, инструкции, пользовательские запросы и финансовые данные не записываются в журнал.
- A2A, MCP, расчёты риска и получение данных Московской биржи не меняются.

---

## Карта файлов

- `packages/agent-service/src/agent_service/llm/client.py` — клиент OpenRouter, выбор моделей, повторы, структурированный ответ и учёт использования.
- `packages/agent-service/src/agent_service/llm/__init__.py` — публичные имена клиента и фабрики.
- `packages/agent-service/tests/test_openrouter_llm_client.py` — модульные проверки клиента; заменяет файл проверки Evolution.
- `packages/agent-service/src/agent_service/server.py` — создание общего клиента для планировщика и отчёта.
- `packages/agent-service/src/agent_service/subagents/research_planner.py` — новая фабрика клиента в автономном планировщике.
- `packages/agent-service/src/agent_service/orchestrator/query_parser.py` — новая фабрика клиента в разборщике запроса.
- `.env.example`, `env.example`, `docker-compose.yml` — локальные настройки OpenRouter.
- `README.md`, архитектурные и эксплуатационные документы — описание OpenRouter вместо Evolution.
- `docs/OPENROUTER_DEPLOY.md` — руководство развёртывания; заменяет `docs/EVOLUTION_DEPLOY.md`.

---

### Задача 1: Создать публичный клиент OpenRouter и фабрику окружения

**Файлы:**

- Переименовать: `packages/agent-service/tests/test_evolution_llm_client.py` → `packages/agent-service/tests/test_openrouter_llm_client.py`
- Изменить: `packages/agent-service/src/agent_service/llm/client.py`
- Изменить: `packages/agent-service/src/agent_service/llm/__init__.py`
- Проверить: `packages/agent-service/tests/test_openrouter_llm_client.py`

**Интерфейсы:**

- Создаёт `OpenRouterLLMClient(api_key=None, api_base=None, model=None, fallback_model=None, reasoning_effort=None, site_url=None, app_name=None, max_retries=2, backoff_factor=0.8, request_timeout=30.0, client=None)`.
- Создаёт `build_openrouter_llm_client_from_env() -> Optional[OpenRouterLLMClient]`.
- Сохраняет `generate(system_prompt, user_prompt, temperature=0.3, max_tokens=2000, response_format=None, tools=None, allow_tool_call=False, structured_schema=None, structured_name="result", prefer_structured=None) -> str`.

- [ ] **Шаг 1: переименовать файл проверки и написать проверки нового публичного интерфейса**

Заменить импорт и добавить проверки значений по умолчанию и фабрики:

```python
from agent_service.llm import OpenRouterLLMClient, build_openrouter_llm_client_from_env


def test_openrouter_defaults():
    client = OpenRouterLLMClient(api_key="test-key", client=FakeOpenAI([], []))

    assert client.api_base == "https://openrouter.ai/api/v1"
    assert client.model == "google/gemini-3.7-flash"
    assert client.fallback_model == "openai/gpt-5.6-luna"
    assert client.reasoning_effort == "low"


def test_factory_returns_none_without_openrouter_key(monkeypatch):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)

    assert build_openrouter_llm_client_from_env() is None


def test_factory_reads_openrouter_environment(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.setenv("OPENROUTER_MODEL", "primary-model")
    monkeypatch.setenv("OPENROUTER_FALLBACK_MODEL", "fallback-model")
    monkeypatch.setenv("OPENROUTER_REASONING_EFFORT", "low")

    client = build_openrouter_llm_client_from_env()

    assert client is not None
    assert client.model == "primary-model"
    assert client.fallback_model == "fallback-model"
```

- [ ] **Шаг 2: запустить новые проверки и подтвердить ожидаемое падение**

Команда:

```bash
PYTHONPATH=packages/agent-service/src pytest packages/agent-service/tests/test_openrouter_llm_client.py -q
```

Ожидание: сборка проверок падает, потому что `OpenRouterLLMClient` и `build_openrouter_llm_client_from_env` ещё не экспортируются.

- [ ] **Шаг 3: реализовать минимальный клиент и фабрику**

В `client.py` определить:

```python
DEFAULT_API_BASE = "https://openrouter.ai/api/v1"
DEFAULT_MODEL = "google/gemini-3.7-flash"
DEFAULT_FALLBACK_MODEL = "openai/gpt-5.6-luna"
DEFAULT_REASONING_EFFORT = "low"


class OpenRouterLLMClient:
    def __init__(
        self,
        api_key: Optional[str] = None,
        api_base: Optional[str] = None,
        model: Optional[str] = None,
        fallback_model: Optional[str] = None,
        reasoning_effort: Optional[str] = None,
        site_url: Optional[str] = None,
        app_name: Optional[str] = None,
        max_retries: int = 2,
        backoff_factor: float = 0.8,
        request_timeout: float = 30.0,
        client: Optional[AsyncOpenAI] = None,
    ) -> None:
        self.api_key = api_key or os.getenv("OPENROUTER_API_KEY")
        if not self.api_key:
            raise ValueError("OPENROUTER_API_KEY не задан: OpenRouterLLMClient выключен")
        self.api_base = api_base or os.getenv("OPENROUTER_API_BASE", DEFAULT_API_BASE)
        self.model = model or os.getenv("OPENROUTER_MODEL", DEFAULT_MODEL)
        self.fallback_model = fallback_model or os.getenv(
            "OPENROUTER_FALLBACK_MODEL", DEFAULT_FALLBACK_MODEL
        )
        self.reasoning_effort = reasoning_effort or os.getenv(
            "OPENROUTER_REASONING_EFFORT", DEFAULT_REASONING_EFFORT
        )
```

Фабрика читает только `OPENROUTER_API_KEY`, создаёт клиент и возвращает `None` без ключа или при ошибке инициализации.

- [ ] **Шаг 4: экспортировать новые имена и удалить старые**

В `llm/__init__.py` оставить:

```python
from .client import OpenRouterLLMClient, build_openrouter_llm_client_from_env

__all__ = ["OpenRouterLLMClient", "build_openrouter_llm_client_from_env"]
```

- [ ] **Шаг 5: запустить проверки клиента**

```bash
PYTHONPATH=packages/agent-service/src pytest packages/agent-service/tests/test_openrouter_llm_client.py -q
```

Ожидание: все проверки файла проходят.

- [ ] **Шаг 6: зафиксировать задачу**

```bash
git add packages/agent-service/src/agent_service/llm/client.py packages/agent-service/src/agent_service/llm/__init__.py packages/agent-service/tests/test_openrouter_llm_client.py packages/agent-service/tests/test_evolution_llm_client.py
git commit -m "feat: заменить клиент модели на OpenRouter"
```

---

### Задача 2: Добавить заголовки, уровень рассуждения, резервную модель и учёт использования

**Файлы:**

- Изменить: `packages/agent-service/src/agent_service/llm/client.py`
- Изменить: `packages/agent-service/tests/test_openrouter_llm_client.py`

**Интерфейсы:**

- Использует конструктор `OpenRouterLLMClient` из задачи 1.
- Передаёт `extra_body={"reasoning": {"effort": <уровень>}}` в каждый запрос.
- Метод `_get_model_sequence() -> list[str]` возвращает основную и уникальную непустую резервную модели.
- Метод `_log_usage(response, requested_model: str) -> None` безопасно читает необязательные поля ответа.

- [ ] **Шаг 1: расширить поддельный клиент для сохранения параметров запросов**

```python
class FakeCompletions:
    def __init__(self, responses, models_called, requests=None):
        self._responses = iter(responses)
        self._models_called = models_called
        self._requests = requests if requests is not None else []

    async def create(self, **kwargs):
        self._requests.append(kwargs)
        self._models_called.append(kwargs.get("model"))
        next_response = next(self._responses)
        if isinstance(next_response, Exception):
            raise next_response
        return FakeResponse(next_response)


class FakeChat:
    def __init__(self, responses, models_called, requests=None):
        self.completions = FakeCompletions(responses, models_called, requests)


class FakeOpenAI:
    def __init__(self, responses, models_called, requests=None):
        self.chat = FakeChat(responses, models_called, requests)
```

- [ ] **Шаг 2: написать проверки заголовков, рассуждения и последовательности моделей**

```python
def test_openrouter_builds_attribution_headers(monkeypatch):
    captured = {}

    def fake_async_openai(**kwargs):
        captured.update(kwargs)
        return FakeOpenAI([], [])

    monkeypatch.setattr("agent_service.llm.client.AsyncOpenAI", fake_async_openai)
    OpenRouterLLMClient(
        api_key="test-key",
        site_url="https://example.test",
        app_name="MOEX Market Analyst",
    )

    assert captured["base_url"] == "https://openrouter.ai/api/v1"
    assert captured["default_headers"] == {
        "HTTP-Referer": "https://example.test",
        "X-OpenRouter-Title": "MOEX Market Analyst",
    }


@pytest.mark.asyncio
async def test_generate_sends_low_reasoning_effort():
    requests = []
    client = OpenRouterLLMClient(
        api_key="test-key",
        client=FakeOpenAI(["ok"], [], requests=requests),
        max_retries=0,
    )

    await client.generate("sys", "user")

    assert requests[0]["extra_body"] == {"reasoning": {"effort": "low"}}
```

Сохранить существующие проверки повторов и заменить сценарий окружения на безусловную последовательность `primary-model`, `fallback-model`.

- [ ] **Шаг 3: запустить новые проверки и подтвердить ожидаемое падение**

```bash
PYTHONPATH=packages/agent-service/src pytest packages/agent-service/tests/test_openrouter_llm_client.py -q
```

Ожидание: новые проверки падают из-за отсутствия `default_headers`, `extra_body` и новой последовательности моделей.

- [ ] **Шаг 4: реализовать заголовки и рассуждение**

Сформировать заголовки только из непустых значений и создать SDK-клиент:

```python
headers = {}
if self.site_url:
    headers["HTTP-Referer"] = self.site_url
if self.app_name:
    headers["X-OpenRouter-Title"] = self.app_name

self.client = client or AsyncOpenAI(
    api_key=self.api_key,
    base_url=self.api_base,
    default_headers=headers or None,
)
```

В `_call_model` передать:

```python
extra_body={"reasoning": {"effort": self.reasoning_effort}}
```

`_get_model_sequence` возвращает `[self.model]` и добавляет `self.fallback_model`, если она непустая и отличается от основной.

- [ ] **Шаг 5: написать падающую проверку безопасного учёта использования**

Расширить поддельный ответ и проверить только безопасные поля журнала:

```python
from types import SimpleNamespace


class FakeResponse:
    def __init__(self, content: str, model: str = "actual-model") -> None:
        self.choices = [FakeChoice(content)]
        self.model = model
        self.usage = SimpleNamespace(
            prompt_tokens=120,
            completion_tokens=40,
            prompt_tokens_details=SimpleNamespace(cached_tokens=80),
            cost=0.001,
        )


@pytest.mark.asyncio
async def test_generate_logs_usage_without_secret(caplog):
    client = OpenRouterLLMClient(
        api_key="test-key",
        client=FakeOpenAI([FakeResponse("ok")], []),
        max_retries=0,
    )

    with caplog.at_level("INFO"):
        await client.generate("sys", "user")

    assert "actual-model" in caplog.text
    assert "prompt_tokens=120" in caplog.text
    assert "cached_tokens=80" in caplog.text
    assert "completion_tokens=40" in caplog.text
    assert "cost=0.001" in caplog.text
    assert "test-key" not in caplog.text
```

Обновить `FakeCompletions.create`: если очередное значение уже является `FakeResponse`, вернуть его без дополнительной упаковки; строку по-прежнему оборачивать в `FakeResponse`.

- [ ] **Шаг 6: реализовать безопасное журналирование статистики**

После успешного ответа вызвать `_log_usage`. Получать поля через `getattr`, подставлять `None` или `0`, не сериализовать весь ответ. Формат сообщения:

```python
logger.info(
    "OpenRouter usage requested_model=%s actual_model=%s prompt_tokens=%s "
    "cached_tokens=%s completion_tokens=%s cost=%s",
    requested_model,
    actual_model,
    prompt_tokens,
    cached_tokens,
    completion_tokens,
    cost,
)
```

- [ ] **Шаг 7: запустить проверки клиента**

```bash
PYTHONPATH=packages/agent-service/src pytest packages/agent-service/tests/test_openrouter_llm_client.py -q
```

Ожидание: все проверки проходят без предупреждений и ошибок.

- [ ] **Шаг 8: зафиксировать задачу**

```bash
git add packages/agent-service/src/agent_service/llm/client.py packages/agent-service/tests/test_openrouter_llm_client.py
git commit -m "feat: настроить модели и учёт OpenRouter"
```

---

### Задача 3: Подключить фабрику OpenRouter ко всем потребителям

**Файлы:**

- Изменить: `packages/agent-service/src/agent_service/server.py`
- Изменить: `packages/agent-service/src/agent_service/subagents/research_planner.py`
- Изменить: `packages/agent-service/src/agent_service/orchestrator/query_parser.py`
- Изменить: `packages/agent-service/tests/test_server_security.py`
- Проверить: `packages/agent-service/tests/test_research_planner_subagent.py`
- Проверить: `packages/agent-service/tests/test_structured_planner.py`

**Интерфейсы:**

- Использует `build_openrouter_llm_client_from_env() -> Optional[OpenRouterLLMClient]`.
- Сервер передаёт один и тот же экземпляр в `ResearchPlannerSubagent` и `ExplainerSubagent`.

- [ ] **Шаг 1: написать падающую проверку общей зависимости сервера**

В `test_server_security.py` импортировать модуль `from agent_service import server` и добавить проверку общей зависимости:

```python
def test_registry_reuses_one_openrouter_client(monkeypatch):
    sentinel = object()
    monkeypatch.setattr(server, "build_openrouter_llm_client_from_env", lambda: sentinel)

    registry = server._build_registry()

    assert registry.get_required("research_planner").llm_client is sentinel
    assert registry.get_required("explainer").llm_client is sentinel
```

- [ ] **Шаг 2: запустить проверку и подтвердить ожидаемое падение**

```bash
PYTHONPATH=packages/agent-service/src pytest packages/agent-service/tests/test_server_security.py::test_registry_reuses_one_openrouter_client -q
```

Ожидание: проверка падает, потому что сервер ещё импортирует старую фабрику.

- [ ] **Шаг 3: заменить импорты, вызовы и сообщения журналов**

Во всех трёх потребителях заменить старую фабрику на `build_openrouter_llm_client_from_env`. В аннотациях и пояснениях использовать `OpenRouterLLMClient`. В сообщениях сервера писать «клиент OpenRouter включён» и «OPENROUTER_API_KEY не задан».

- [ ] **Шаг 4: запустить целевые проверки интеграции агента**

```bash
PYTHONPATH=packages/agent-service/src pytest \
  packages/agent-service/tests/test_server_security.py \
  packages/agent-service/tests/test_research_planner_subagent.py \
  packages/agent-service/tests/test_structured_planner.py -q
```

Ожидание: все проверки проходят.

- [ ] **Шаг 5: убедиться, что старые имена отсутствуют в исполняемом коде**

```bash
rg -n "EvolutionLLMClient|build_evolution_llm_client_from_env|LLM_API_KEY|EVOLUTION_" packages/agent-service/src
```

Ожидание: совпадений нет.

- [ ] **Шаг 6: зафиксировать задачу**

```bash
git add packages/agent-service/src/agent_service/server.py packages/agent-service/src/agent_service/subagents/research_planner.py packages/agent-service/src/agent_service/orchestrator/query_parser.py packages/agent-service/tests/test_server_security.py
git commit -m "refactor: подключить OpenRouter к агенту"
```

---

### Задача 4: Перевести окружение и Docker Compose на OpenRouter

**Файлы:**

- Изменить: `.env.example`
- Изменить: `env.example`
- Изменить: `docker-compose.yml`

**Интерфейсы:**

- Контейнер `agent` получает семь переменных `OPENROUTER_*`, включая ключ.
- `AGENT_API_KEY` остаётся обязательным служебным ключом между веб-приложением и агентом.

- [ ] **Шаг 1: написать проверяемый ожидаемый набор переменных**

В `.env.example` и `env.example` указать:

```dotenv
OPENROUTER_API_KEY=
OPENROUTER_API_BASE=https://openrouter.ai/api/v1
OPENROUTER_MODEL=google/gemini-3.7-flash
OPENROUTER_FALLBACK_MODEL=openai/gpt-5.6-luna
OPENROUTER_REASONING_EFFORT=low
OPENROUTER_SITE_URL=http://localhost:3000
OPENROUTER_APP_NAME=MOEX Market Analyst
```

- [ ] **Шаг 2: изменить окружение контейнера агента**

В `docker-compose.yml` удалить `LLM_API_KEY` и добавить явную передачу всех переменных `OPENROUTER_*` с безопасными значениями по умолчанию, кроме необязательного пустого ключа.

- [ ] **Шаг 3: проверить итоговую конфигурацию Compose**

```bash
AGENT_API_KEY=local-test-key docker compose config > /tmp/moex-openrouter-compose.yaml
rg -n "OPENROUTER_(API_BASE|MODEL|FALLBACK_MODEL|REASONING_EFFORT|SITE_URL|APP_NAME)" /tmp/moex-openrouter-compose.yaml
rg -n "LLM_API_KEY|EVOLUTION_" /tmp/moex-openrouter-compose.yaml
```

Ожидание: первая команда поиска находит новые переменные, вторая не находит старые.

- [ ] **Шаг 4: зафиксировать задачу**

```bash
git add .env.example env.example docker-compose.yml
git commit -m "chore: настроить окружение OpenRouter"
```

---

### Задача 5: Переписать поддерживаемую документацию

**Файлы:**

- Изменить: `README.md`
- Переименовать: `docs/EVOLUTION_DEPLOY.md` → `docs/OPENROUTER_DEPLOY.md`
- Изменить: `docs/12.12.25.ARHITECTURE.md`
- Изменить: `docs/ARCHITECTURE.md`
- Изменить: `docs/REQUIREMENTS_moex-market-analyst-agent.md`
- Изменить: `docs/SPEC_moex-iss-mcp.md`
- Изменить: `docs/SPEC_risk-analytics-mcp.md`
- Изменить: `docs/c4_level_1_system_context.md`
- Изменить: `docs/c4_level_4_code_ai_agent.md`
- Изменить: `docs/dependencies/Требования к MCP.docx.md`
- Изменить: `docs/q&a.md`
- Изменить: `docs/structured_output.md`
- Изменить: `moex_iss_mcp/README.md`
- Изменить: `risk_analytics_mcp/README.md`
- Изменить: `risk_analytics_mcp/mcp-server-catalog.yaml`

**Интерфейсы:**

- Описывает только переменные `OPENROUTER_*` из задачи 4.
- Сохраняет A2A и MCP без привязки к Evolution AI Agents.

- [ ] **Шаг 1: переписать основной порядок запуска**

В `README.md` указать получение ключа OpenRouter, копирование `.env.example` в `.env`, модели по умолчанию и `make local-up`. Исправить путь проекта на `/Users/Admin/CursorProject/moex-agentic-system`. Объяснить работу с имитацией модели без ключа.

- [ ] **Шаг 2: заменить руководство развёртывания**

Переименовать файл командой:

```bash
git mv docs/EVOLUTION_DEPLOY.md docs/OPENROUTER_DEPLOY.md
```

Описать сборку контейнеров, передачу `OPENROUTER_API_KEY` через хранилище секретов, проверку `/health`, запуск веб-приложения и проверку вызова `/a2a`. Не добавлять инструкции, завязанные на конкретную облачную платформу.

- [ ] **Шаг 3: обновить архитектурные и предметные документы**

Во всех перечисленных файлах заменить поставщика модели на OpenRouter, новые имена клиента и переменных. Удалить требования сервисных учётных записей Evolution и адрес Foundation Models. Сохранить исторические решения только в документах `docs/superpowers`, которые являются журналом принятого переноса.

- [ ] **Шаг 4: проверить ссылки и старые упоминания**

```bash
rg -n "EVOLUTION_DEPLOY|EvolutionLLMClient|build_evolution_llm_client_from_env|LLM_API_|EVOLUTION_|foundation-models\.api\.cloud\.ru" \
  README.md .env.example env.example docker-compose.yml packages moex_iss_mcp risk_analytics_mcp docs \
  --glob '!docs/superpowers/**'
```

Ожидание: совпадений нет.

- [ ] **Шаг 5: проверить новые упоминания**

```bash
rg -n "OPENROUTER_API_KEY|google/gemini-3.7-flash|openai/gpt-5.6-luna|OPENROUTER_DEPLOY" README.md docs/OPENROUTER_DEPLOY.md .env.example env.example docker-compose.yml
```

Ожидание: все основные настройки и ссылка на руководство находятся.

- [ ] **Шаг 6: зафиксировать задачу**

```bash
git add README.md .env.example env.example docker-compose.yml docs moex_iss_mcp/README.md risk_analytics_mcp/README.md risk_analytics_mcp/mcp-server-catalog.yaml
git commit -m "docs: перевести проект на OpenRouter"
```

---

### Задача 6: Полная проверка переноса

**Файлы:**

- Проверить: все изменённые файлы

**Интерфейсы:**

- Подтверждает выполнение всех критериев документа `docs/superpowers/specs/2026-08-14-openrouter-migration-design.md`.

- [ ] **Шаг 1: запустить проверки клиента и агента**

```bash
PYTHONPATH=packages/agent-service/src pytest packages/agent-service/tests -q
```

Ожидание: ноль падений.

- [ ] **Шаг 2: запустить корневые проверки SDK и серверов MCP**

```bash
PYTHONPATH=. pytest tests -q
```

Ожидание: ноль падений; сетевые проверки, помеченные для живого окружения, пропускаются штатными метками.

- [ ] **Шаг 3: проверить различия и пробелы**

```bash
git diff --check
git status -sb
```

Ожидание: `git diff --check` завершается без вывода; в состоянии Git нет незапланированных файлов.

- [ ] **Шаг 4: проверить конфигурацию контейнеров**

```bash
AGENT_API_KEY=local-test-key docker compose config --quiet
```

Ожидание: код завершения 0.

- [ ] **Шаг 5: собрать контейнеры**

```bash
AGENT_API_KEY=local-test-key make local-build
```

Ожидание: четыре образа собираются без ошибок.

- [ ] **Шаг 6: выполнить окончательный поиск старого поставщика**

```bash
rg -n "EvolutionLLMClient|build_evolution_llm_client_from_env|LLM_API_|EVOLUTION_|foundation-models\.api\.cloud\.ru" \
  README.md .env.example env.example docker-compose.yml packages moex_iss_mcp risk_analytics_mcp docs \
  --glob '!docs/superpowers/**'
```

Ожидание: совпадений нет.

- [ ] **Шаг 7: сверить изменения с критериями проекта решения**

Проверить по пунктам: новый ключ, адрес, основная и резервная модели, уровень рассуждения, имитация без ключа, безопасный журнал, документация и отсутствие старых имён.

- [ ] **Шаг 8: зафиксировать только необходимые завершающие исправления**

Если полная проверка потребовала правок, добавить только соответствующие файлы и создать фиксацию:

```bash
git commit -m "test: подтвердить перенос на OpenRouter"
```
