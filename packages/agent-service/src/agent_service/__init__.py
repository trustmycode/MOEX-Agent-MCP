"""
Agent Service — AI-агент для анализа российского фондового рынка.

Основные модули:
- core: Базовые абстракции мультиагентной архитектуры
- orchestrator: Оркестратор запросов (TASK-122)
- subagents: Специализированные сабагенты (TASK-121, TASK-123)
- models: Pydantic-модели для структурированных ответов (RiskDashboardSpec)

Пример использования:

    from agent_service import (
        OrchestratorAgent,
        A2AInput,
        A2AOutput,
        SubagentRegistry,
        DashboardSubagent,
        ExplainerSubagent,
        RiskDashboardSpec,
    )

    # Создаём оркестратор
    registry = SubagentRegistry()
    registry.register(DashboardSubagent())
    registry.register(ExplainerSubagent())
    orchestrator = OrchestratorAgent(registry=registry)

    # Обрабатываем запрос
    input = A2AInput(
        messages=[{"role": "user", "content": "Оцени риск портфеля..."}]
    )
    output = await orchestrator.handle_request(input)
    print(output.text)
"""

__version__ = "0.1.0"

# Core
from .core import (
    AgentContext,
    BaseSubagent,
    SubagentRegistry,
    SubagentResult,
    default_registry,
    get_registry,
)

# Models
from .models import (
    Alert,
    AlertSeverity,
    ChartAxis,
    ChartSeries,
    ChartSpec,
    ChartType,
    DashboardMetadata,
    LayoutItem,
    Metric,
    MetricCard,
    MetricSeverity,
    RiskDashboardSpec,
    TableColumn,
    TableSpec,
    WidgetType,
)

# Subagents
from .subagents import (
    DashboardSubagent,
    ExplainerSubagent,
)

# Orchestrator
from .orchestrator import (
    A2AInput,
    A2AMessage,
    A2AOutput,
    DebugInfo,
    IntentClassifier,
    OrchestratorAgent,
    PipelineStep,
    ScenarioPipeline,
    ScenarioType,
    get_pipeline,
)

__all__ = [
    # Version
    "__version__",
    # Core
    "AgentContext",
    "BaseSubagent",
    "SubagentRegistry",
    "SubagentResult",
    "default_registry",
    "get_registry",
    # Models
    "RiskDashboardSpec",
    "DashboardMetadata",
    "MetricCard",
    "Metric",
    "MetricSeverity",
    "WidgetType",
    "TableColumn",
    "TableSpec",
    "ChartAxis",
    "ChartSeries",
    "ChartSpec",
    "ChartType",
    "Alert",
    "AlertSeverity",
    # Subagents
    "DashboardSubagent",
    "ExplainerSubagent",
    # Orchestrator
    "OrchestratorAgent",
    "IntentClassifier",
    "ScenarioType",
    "ScenarioPipeline",
    "PipelineStep",
    "get_pipeline",
    # A2A Models
    "A2AInput",
    "A2AOutput",
    "A2AMessage",
    "DebugInfo",
]
