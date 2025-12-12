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

DEFAULT_API_BASE = "https://foundation-models.api.cloud.ru/v1"
DEFAULT_MODEL_MAIN = "Qwen/Qwen3-235B-A22B-Instruct-2507"
DEFAULT_MODEL_FALLBACK = "openai/gpt-oss-120b"
DEFAULT_MODEL_DEV = "Qwen/Qwen3-235B-A22B-Instruct-2507"

class EvolutionLLMClient:
    """
    Клиент для Evolution Foundation Models (OpenAI-compatible API).

    Использует official FM endpoint и умеет переключать модель в зависимости от окружения:
    - dev → LLM_MODEL_DEV
    - prod → LLM_MODEL_MAIN с fallback на LLM_MODEL_FALLBACK при retryable-ошибках
    - LLM_MODEL (если задан) имеет наивысший приоритет.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        api_base: Optional[str] = None,
        model_main: Optional[str] = None,
        model_fallback: Optional[str] = None,
        model_dev: Optional[str] = None,
        model_override: Optional[str] = None,
        environment: Optional[str] = None,
        max_retries: int = 2,
        backoff_factor: float = 0.8,
        request_timeout: float = 30.0,
        client: Optional[AsyncOpenAI] = None,
    ) -> None:
        self.api_key = api_key or os.getenv("LLM_API_KEY")
        if not self.api_key:
            raise ValueError("LLM_API_KEY не задан: EvolutionLLMClient выключен")

        self.api_base = api_base or os.getenv("LLM_API_BASE", DEFAULT_API_BASE)
        self.environment = (environment or os.getenv("ENVIRONMENT", "dev")).lower()

        # Параметры моделей
        self.model_override = model_override or os.getenv("LLM_MODEL")
        self.model_main = model_main or os.getenv("LLM_MODEL_MAIN", DEFAULT_MODEL_MAIN)
        self.model_fallback = model_fallback or os.getenv(
            "LLM_MODEL_FALLBACK", DEFAULT_MODEL_FALLBACK
        )
        self.model_dev = model_dev or os.getenv("LLM_MODEL_DEV", DEFAULT_MODEL_DEV)

        self.max_retries = max_retries
        self.backoff_factor = backoff_factor
        self.request_timeout = request_timeout

        self.client = client or AsyncOpenAI(api_key=self.api_key, base_url=self.api_base)

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
                    "Evolution LLM call failed for model %s (%s). Trying fallback if available.",
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
                )

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
                    "Retrying Evolution LLM (attempt %d/%d, model=%s, error=%s), backoff=%.2fs",
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

    def _get_model_sequence(self) -> list[str]:
        """Вернуть последовательность моделей (основная → fallback)."""
        primary = self._select_primary_model()
        models = [primary]

        if (
            self.environment == "prod"
            and self.model_fallback
            and self.model_fallback not in models
        ):
            models.append(self.model_fallback)

        return models

    def _select_primary_model(self) -> str:
        """Выбрать основную модель с учётом ENVIRONMENT и override."""
        if self.model_override:
            return self.model_override

        if self.environment == "prod":
            return self.model_main

        return self.model_dev or self.model_main

    @staticmethod
    def _is_retryable(exc: Exception) -> bool:
        """Определить, стоит ли повторять запрос."""
        if isinstance(exc, (RateLimitError, APIConnectionError, APITimeoutError)):
            return True

        if isinstance(exc, APIStatusError):
            return exc.status_code >= 500 or exc.status_code == 429

        return False


def build_evolution_llm_client_from_env() -> Optional[EvolutionLLMClient]:
    """
    Попробовать создать EvolutionLLMClient на основе переменных окружения.

    Возвращает None, если ключ не задан или инициализация не удалась.
    """
    api_key = os.getenv("LLM_API_KEY")
    if not api_key:
        logger.warning("LLM_API_KEY не найден: используется MockLLMClient")
        return None

    try:
        client = EvolutionLLMClient(api_key=api_key)
        logger.info(
            "EvolutionLLMClient инициализирован (env=%s, model=%s)",
            client.environment,
            client._get_model_sequence()[0],
        )
        return client
    except Exception as exc:
        logger.error("Не удалось инициализировать EvolutionLLMClient: %s", exc)
        return None
