import asyncio

import pytest

from agent_service.llm import OpenRouterLLMClient, build_openrouter_llm_client_from_env


class TransientError(Exception):
    """Искусственная retryable-ошибка для тестов."""


class FakeMessage:
    def __init__(self, content: str) -> None:
        self.content = content


class FakeChoice:
    def __init__(self, content: str) -> None:
        self.message = FakeMessage(content)


class FakeResponse:
    def __init__(self, content: str) -> None:
        self.choices = [FakeChoice(content)]


class FakeCompletions:
    def __init__(self, responses: list[object], models_called: list[str]) -> None:
        self._responses = iter(responses)
        self._models_called = models_called

    async def create(self, **kwargs):
        self._models_called.append(kwargs.get("model"))
        next_response = next(self._responses)
        if isinstance(next_response, Exception):
            raise next_response
        return FakeResponse(next_response)


class FakeChat:
    def __init__(self, responses: list[object], models_called: list[str]) -> None:
        self.completions = FakeCompletions(responses, models_called)


class FakeOpenAI:
    def __init__(self, responses: list[object], models_called: list[str]) -> None:
        self.chat = FakeChat(responses, models_called)


@pytest.mark.asyncio
async def test_generate_uses_primary_model_by_default(monkeypatch):
    models_called: list[str] = []
    fake_client = FakeOpenAI(responses=["hello"], models_called=models_called)

    client = OpenRouterLLMClient(
        api_key="test-key",
        api_base="http://dummy",
        model="primary-model",
        client=fake_client,
        max_retries=0,
    )
    monkeypatch.setattr(client, "_is_retryable", lambda exc: False)

    result = await client.generate(system_prompt="sys", user_prompt="user")

    assert result == "hello"
    assert models_called == ["primary-model"]


@pytest.mark.asyncio
async def test_generate_falls_back_to_fallback_model(monkeypatch):
    models_called: list[str] = []
    fake_client = FakeOpenAI(
        responses=[TransientError("boom"), "from-fallback"], models_called=models_called
    )

    client = OpenRouterLLMClient(
        api_key="test-key",
        api_base="http://dummy",
        model="primary-model",
        fallback_model="fallback-model",
        client=fake_client,
        max_retries=0,
    )
    monkeypatch.setattr(
        client, "_is_retryable", lambda exc: isinstance(exc, TransientError)
    )

    result = await client.generate(system_prompt="sys", user_prompt="user")

    assert result == "from-fallback"
    assert models_called == ["primary-model", "fallback-model"]


@pytest.mark.asyncio
async def test_generate_retries_on_retryable_error(monkeypatch):
    sleeps: list[float] = []

    async def fake_sleep(delay: float) -> None:
        sleeps.append(delay)

    monkeypatch.setattr(asyncio, "sleep", fake_sleep)

    models_called: list[str] = []
    fake_client = FakeOpenAI(
        responses=[TransientError("temporary"), "after-retry"],
        models_called=models_called,
    )

    client = OpenRouterLLMClient(
        api_key="test-key",
        api_base="http://dummy",
        model="primary-model",
        client=fake_client,
        max_retries=1,
        backoff_factor=0.5,
    )
    monkeypatch.setattr(
        client, "_is_retryable", lambda exc: isinstance(exc, TransientError)
    )

    result = await client.generate(system_prompt="sys", user_prompt="user")

    assert result == "after-retry"
    assert sleeps == pytest.approx([0.5], rel=0.1)
    assert models_called == ["primary-model", "primary-model"]


def test_openrouter_defaults():
    client = OpenRouterLLMClient(
        api_key="test-key",
        client=FakeOpenAI(responses=[], models_called=[]),
    )

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
    assert client.reasoning_effort == "low"

