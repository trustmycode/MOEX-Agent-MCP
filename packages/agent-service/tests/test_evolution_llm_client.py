import asyncio

import pytest

from agent_service.llm import EvolutionLLMClient


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
async def test_generate_uses_dev_model_by_default(monkeypatch):
    models_called: list[str] = []
    fake_client = FakeOpenAI(responses=["hello"], models_called=models_called)

    client = EvolutionLLMClient(
        api_key="test-key",
        api_base="http://dummy",
        model_dev="dev-model",
        model_main="main-model",
        client=fake_client,
        max_retries=0,
    )
    monkeypatch.setattr(client, "_is_retryable", lambda exc: False)

    result = await client.generate(system_prompt="sys", user_prompt="user")

    assert result == "hello"
    assert models_called == ["dev-model"]


@pytest.mark.asyncio
async def test_generate_falls_back_to_fallback_model(monkeypatch):
    models_called: list[str] = []
    fake_client = FakeOpenAI(
        responses=[TransientError("boom"), "from-fallback"], models_called=models_called
    )

    client = EvolutionLLMClient(
        api_key="test-key",
        api_base="http://dummy",
        environment="prod",
        model_main="main-model",
        model_fallback="fallback-model",
        client=fake_client,
        max_retries=0,
    )
    monkeypatch.setattr(
        client, "_is_retryable", lambda exc: isinstance(exc, TransientError)
    )

    result = await client.generate(system_prompt="sys", user_prompt="user")

    assert result == "from-fallback"
    assert models_called == ["main-model", "fallback-model"]


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

    client = EvolutionLLMClient(
        api_key="test-key",
        api_base="http://dummy",
        model_dev="dev-model",
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
    assert models_called == ["dev-model", "dev-model"]

