"""
Orchestrator — центральный координатор мультиагентной системы.

Содержит:
- OrchestratorAgent — основной класс оркестратора
- IntentClassifier — классификатор намерений пользователя
- ScenarioPipeline — определения pipeline'ов для сценариев
- A2A-модели — модели входа/выхода для протокола A2A

Пример использования:

    from agent_service.orchestrator import (
        OrchestratorAgent,
        A2AInput,
        A2AOutput,
    )

    orchestrator = OrchestratorAgent(registry=my_registry)
    output = await orchestrator.handle_request(
        A2AInput(messages=[{"role": "user", "content": "Оцени риск портфеля..."}])
    )
    print(output.text)
"""

from .intent_classifier import IntentClassifier, ScenarioType
from .models import A2AInput, A2AMessage, A2AOutput, DebugInfo
from .orchestrator_agent import OrchestratorAgent
from .pipelines import PipelineStep, ScenarioPipeline, get_pipeline
from .query_parser import ParseResult, QueryParser
from .session_store import SessionStateStore

__all__ = [
    # Основные классы
    "OrchestratorAgent",
    "IntentClassifier",
    "ScenarioType",
    "QueryParser",
    "ParseResult",
    "SessionStateStore",
    # Pipeline
    "ScenarioPipeline",
    "PipelineStep",
    "get_pipeline",
    # A2A модели
    "A2AInput",
    "A2AOutput",
    "A2AMessage",
    "DebugInfo",
]
