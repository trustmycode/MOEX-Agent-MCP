"""Клиенты языковых моделей для работы через OpenRouter."""

from .client import (
    OpenRouterLLMClient,
    build_openrouter_llm_client_from_env,
)

# Временный мост на время последовательного перевода потребителей.
EvolutionLLMClient = OpenRouterLLMClient
build_evolution_llm_client_from_env = build_openrouter_llm_client_from_env

__all__ = [
    "OpenRouterLLMClient",
    "build_openrouter_llm_client_from_env",
]
