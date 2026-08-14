from __future__ import annotations

# pyright: reportMissingImports=false

import asyncio
import json
import logging
import os
from typing import Any, Optional

from openai import (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    AsyncOpenAI,
    RateLimitError,
)

logger = logging.getLogger(__name__)

DEFAULT_API_BASE = "https://openrouter.ai/api/v1"
DEFAULT_MODEL = "google/gemini-3.7-flash"
DEFAULT_FALLBACK_MODEL = "openai/gpt-5.6-luna"
DEFAULT_REASONING_EFFORT = "low"


class OpenRouterLLMClient:
    """
    Клиент OpenRouter через совместимый с OpenAI программный интерфейс.
    """

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
            raise ValueError(
                "OPENROUTER_API_KEY не задан: OpenRouterLLMClient выключен"
            )

        self.api_base = api_base or os.getenv("OPENROUTER_API_BASE", DEFAULT_API_BASE)
        self.model = model or os.getenv("OPENROUTER_MODEL", DEFAULT_MODEL)
        self.fallback_model = fallback_model or os.getenv(
            "OPENROUTER_FALLBACK_MODEL", DEFAULT_FALLBACK_MODEL
        )
        self.reasoning_effort = reasoning_effort or os.getenv(
            "OPENROUTER_REASONING_EFFORT", DEFAULT_REASONING_EFFORT
        )
        self.site_url = site_url or os.getenv("OPENROUTER_SITE_URL")
        self.app_name = app_name or os.getenv("OPENROUTER_APP_NAME")

        self.max_retries = max_retries
        self.backoff_factor = backoff_factor
        self.request_timeout = request_timeout

        client_kwargs: dict[str, Any] = {
            "api_key": self.api_key,
            "base_url": self.api_base,
        }
        default_headers: dict[str, str] = {}
        if self.site_url:
            default_headers["HTTP-Referer"] = self.site_url
        if self.app_name:
            default_headers["X-OpenRouter-Title"] = self.app_name
        if default_headers:
            client_kwargs["default_headers"] = default_headers

        self.client = client or AsyncOpenAI(**client_kwargs)

    async def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.3,
        max_tokens: int = 2000,
        response_format: Optional[dict] = None,
        tools: Optional[list[dict[str, Any]]] = None,
        allow_tool_call: bool = False,
        structured_schema: Optional[dict[str, Any]] = None,
        structured_name: str = "result",
        prefer_structured: Optional[bool] = None,
    ) -> str:
        """
        Сгенерировать текст с учётом системного и пользовательского промптов.

        Делает попытку через основную модель, при необходимости — fallback.
        """
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        last_error: Optional[Exception] = None
        response_format_final = response_format

        if structured_schema is not None:
            response_format_final = {
                "type": "json_schema",
                "json_schema": {
                    "name": structured_name or "result",
                    "schema": structured_schema,
                },
            }

        for model in self._get_model_sequence():
            try:
                return await self._call_model(
                    model=model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    response_format=response_format_final,
                    tools=tools,
                    allow_tool_call=allow_tool_call,
                )
            except Exception as exc:
                last_error = exc
                logger.warning(
                    "OpenRouter call failed for model %s (%s). Trying fallback if available.",
                    model,
                    type(exc).__name__,
                )

                # Fallback: если json_schema не прошёл, пробуем json_object
                if response_format_final and response_format_final.get("type") == "json_schema":
                    try:
                        return await self._call_model(
                            model=model,
                            messages=messages,
                            temperature=temperature,
                            max_tokens=max_tokens,
                            response_format={"type": "json_object"},
                            tools=tools,
                            allow_tool_call=allow_tool_call,
                        )
                    except Exception as rf_exc:
                        last_error = rf_exc
                        logger.warning(
                            "JSON schema fallback to json_object failed for model %s (%s)",
                            model,
                            type(rf_exc).__name__,
                        )

                # Fallback на tool-calling, если доступен
                if tools:
                    try:
                        return await self._call_model(
                            model=model,
                            messages=messages,
                            temperature=temperature,
                            max_tokens=max_tokens,
                            response_format=None,
                            tools=tools,
                            tool_choice="auto",
                            allow_tool_call=True,
                        )
                    except Exception as tool_exc:
                        last_error = tool_exc
                        logger.warning(
                            "Tool-calling fallback failed for model %s (%s)",
                            model,
                            type(tool_exc).__name__,
                        )
                        continue
                continue

        if last_error:
            raise last_error

        raise RuntimeError("LLM generation failed without explicit error")

    async def _call_model(
        self,
        model: str,
        messages: list[dict[str, str]],
        temperature: float,
        max_tokens: int,
        response_format: Optional[dict],
        tools: Optional[list[dict[str, Any]]] = None,
        tool_choice: Optional[Any] = None,
        allow_tool_call: bool = False,
    ) -> str:
        """Вызвать конкретную модель с ретраем и backoff."""
        last_error: Optional[Exception] = None

        for attempt in range(self.max_retries + 1):
            try:
                response = await self.client.chat.completions.create(
                    model=model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    response_format=response_format,
                    tools=tools,
                    tool_choice=tool_choice,
                    timeout=self.request_timeout,
                    extra_body={"reasoning": {"effort": self.reasoning_effort}},
                )

                self._log_usage(response, requested_model=model)

                choice = (response.choices or [None])[0]
                if not choice or not choice.message:
                    return ""

                # Поддержка tool-calling fallback: если модель вернула tool_calls и это разрешено
                if allow_tool_call and getattr(choice.message, "tool_calls", None):
                    tool_calls = choice.message.tool_calls
                    if tool_calls:
                        first_call = tool_calls[0]
                        # arguments уже строка JSON
                        return first_call.function.arguments  # type: ignore[return-value]

                if not choice.message.content:
                    return ""
                return choice.message.content

            except Exception as exc:  # pragma: no cover - конкретные типы разбираются ниже
                last_error = exc

                if not self._is_retryable(exc) or attempt >= self.max_retries:
                    raise

                delay = self.backoff_factor * (2**attempt)
                logger.info(
                    "Retrying OpenRouter (attempt %d/%d, model=%s, error=%s), backoff=%.2fs",
                    attempt + 1,
                    self.max_retries,
                    model,
                    type(exc).__name__,
                    delay,
                )
                await asyncio.sleep(delay)

        if last_error:
            raise last_error
        raise RuntimeError("LLM call failed without explicit error")

    @staticmethod
    def _log_usage(response: Any, *, requested_model: str) -> None:
        """Записать расход OpenRouter без содержимого запроса и секретов."""
        usage = getattr(response, "usage", None)
        prompt_details = (
            getattr(usage, "prompt_tokens_details", None) if usage is not None else None
        )
        logger.info(
            "OpenRouter usage requested_model=%s actual_model=%s "
            "prompt_tokens=%s cached_tokens=%s completion_tokens=%s cost=%s",
            requested_model,
            getattr(response, "model", None),
            getattr(usage, "prompt_tokens", None) if usage is not None else None,
            getattr(prompt_details, "cached_tokens", 0)
            if prompt_details is not None
            else 0,
            getattr(usage, "completion_tokens", None) if usage is not None else None,
            getattr(usage, "cost", None) if usage is not None else None,
        )

    def _get_model_sequence(self) -> list[str]:
        """Вернуть последовательность моделей (основная → fallback)."""
        models = [self.model]

        if self.fallback_model and self.fallback_model not in models:
            models.append(self.fallback_model)

        return models

    @staticmethod
    def _is_retryable(exc: Exception) -> bool:
        """Определить, стоит ли повторять запрос."""
        if isinstance(exc, (RateLimitError, APIConnectionError, APITimeoutError)):
            return True

        if isinstance(exc, APIStatusError):
            return exc.status_code >= 500 or exc.status_code == 429

        return False


def build_openrouter_llm_client_from_env() -> Optional[OpenRouterLLMClient]:
    """
    Попробовать создать OpenRouterLLMClient на основе переменных окружения.

    Возвращает None, если ключ не задан или инициализация не удалась.
    """
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        logger.warning("OPENROUTER_API_KEY не найден: используется MockLLMClient")
        return None

    try:
        client = OpenRouterLLMClient(api_key=api_key)
        logger.info(
            "OpenRouterLLMClient инициализирован (model=%s)",
            client._get_model_sequence()[0],
        )
        return client
    except Exception as exc:
        logger.error("Не удалось инициализировать OpenRouterLLMClient: %s", exc)
        return None


# Временный мост на время последовательного перевода потребителей.
EvolutionLLMClient = OpenRouterLLMClient
build_evolution_llm_client_from_env = build_openrouter_llm_client_from_env
