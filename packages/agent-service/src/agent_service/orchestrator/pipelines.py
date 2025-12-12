"""
Pipelines — определения pipeline'ов сабагентов для каждого типа сценария.

Каждый pipeline определяет последовательность вызова сабагентов
и правила обработки ошибок (required vs optional).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Optional

from .intent_classifier import ScenarioType

logger = logging.getLogger(__name__)


@dataclass
class PipelineStep:
    """
    Шаг pipeline — описание вызова сабагента.

    Attributes:
        subagent_name: Имя сабагента в registry (например, "market_data").
        required: Обязателен ли этот шаг. Если True и шаг падает, весь pipeline прерывается.
        timeout_seconds: Таймаут для этого шага (переопределяет глобальный).
        depends_on: Список имён сабагентов, от которых зависит этот шаг.
        result_key: Ключ для сохранения результата в context.intermediate_results.
    """

    subagent_name: str
    required: bool = True
    timeout_seconds: float = 30.0
    depends_on: list[str] = field(default_factory=list)
    result_key: Optional[str] = None

    def __post_init__(self) -> None:
        """Установить result_key по умолчанию."""
        if self.result_key is None:
            self.result_key = self.subagent_name


@dataclass
class ScenarioPipeline:
    """
    Pipeline для выполнения сценария.

    Определяет последовательность шагов (сабагентов) и их параметры.

    Attributes:
        scenario_type: Тип сценария, которому соответствует этот pipeline.
        description: Человекочитаемое описание pipeline.
        steps: Список шагов (сабагентов) для выполнения.
        default_timeout: Таймаут по умолчанию для шагов без явного таймаута.
    """

    scenario_type: ScenarioType
    description: str
    steps: list[PipelineStep]
    default_timeout: float = 30.0

    @property
    def required_steps(self) -> list[PipelineStep]:
        """Получить только обязательные шаги."""
        return [step for step in self.steps if step.required]

    @property
    def optional_steps(self) -> list[PipelineStep]:
        """Получить опциональные шаги."""
        return [step for step in self.steps if not step.required]

    @property
    def subagent_names(self) -> list[str]:
        """Получить список имён всех сабагентов в pipeline."""
        return [step.subagent_name for step in self.steps]


# =============================================================================
# Определения pipeline'ов для всех сценариев
# =============================================================================

PORTFOLIO_RISK_PIPELINE = ScenarioPipeline(
    scenario_type=ScenarioType.PORTFOLIO_RISK,
    description=(
        "Анализ риска портфеля: получение данных, расчёт риска, "
        "формирование дашборда и текстового отчёта"
    ),
    steps=[
        PipelineStep(
            subagent_name="market_data",
            required=True,
            timeout_seconds=30.0,
            result_key="market_data",
        ),
        PipelineStep(
            subagent_name="risk_analytics",
            required=True,
            timeout_seconds=45.0,
            depends_on=["market_data"],
            result_key="risk_analytics",
        ),
        PipelineStep(
            subagent_name="dashboard",
            required=True,
            timeout_seconds=15.0,
            depends_on=["risk_analytics"],
            result_key="dashboard",
        ),
        PipelineStep(
            subagent_name="knowledge",
            required=False,  # RAG опционален
            timeout_seconds=20.0,
            result_key="knowledge",
        ),
        PipelineStep(
            subagent_name="explainer",
            required=True,
            timeout_seconds=30.0,
            depends_on=["risk_analytics", "dashboard"],
            result_key="explainer",
        ),
    ],
)


CFO_LIQUIDITY_PIPELINE = ScenarioPipeline(
    scenario_type=ScenarioType.CFO_LIQUIDITY,
    description=(
        "CFO-отчёт по ликвидности: расчёт ликвидности, стресс-сценарии, "
        "проверка ковенантов, формирование executive summary"
    ),
    steps=[
        PipelineStep(
            subagent_name="risk_analytics",
            required=True,
            timeout_seconds=60.0,
            result_key="risk_analytics",
        ),
        PipelineStep(
            subagent_name="dashboard",
            required=True,
            timeout_seconds=15.0,
            depends_on=["risk_analytics"],
            result_key="dashboard",
        ),
        PipelineStep(
            subagent_name="knowledge",
            required=False,  # RAG для регламентов
            timeout_seconds=20.0,
            result_key="knowledge",
        ),
        PipelineStep(
            subagent_name="explainer",
            required=True,
            timeout_seconds=30.0,
            depends_on=["risk_analytics", "dashboard"],
            result_key="explainer",
        ),
    ],
)


ISSUER_COMPARE_PIPELINE = ScenarioPipeline(
    scenario_type=ScenarioType.ISSUER_COMPARE,
    description=(
        "Сравнение эмитента с пирами: получение данных по пирам, "
        "расчёт мультипликаторов, формирование сравнительного отчёта"
    ),
    steps=[
        PipelineStep(
            subagent_name="market_data",
            required=True,
            timeout_seconds=30.0,
            result_key="market_data",
        ),
        PipelineStep(
            subagent_name="risk_analytics",
            required=True,
            timeout_seconds=30.0,
            depends_on=["market_data"],
            result_key="risk_analytics",
        ),
        PipelineStep(
            subagent_name="dashboard",
            required=False,  # Для сравнения можно обойтись без dashboard
            timeout_seconds=15.0,
            depends_on=["risk_analytics"],
            result_key="dashboard",
        ),
        PipelineStep(
            subagent_name="explainer",
            required=True,
            timeout_seconds=30.0,
            depends_on=["market_data", "risk_analytics"],
            result_key="explainer",
        ),
    ],
)


SECURITY_OVERVIEW_PIPELINE = ScenarioPipeline(
    scenario_type=ScenarioType.SECURITY_OVERVIEW,
    description=(
        "Обзор одной бумаги: получение snapshot и истории, "
        "базовые метрики, формирование отчёта"
    ),
    steps=[
        PipelineStep(
            subagent_name="market_data",
            required=True,
            timeout_seconds=30.0,
            result_key="market_data",
        ),
        PipelineStep(
            subagent_name="explainer",
            required=True,
            timeout_seconds=20.0,
            depends_on=["market_data"],
            result_key="explainer",
        ),
    ],
)


SECURITIES_COMPARE_PIPELINE = ScenarioPipeline(
    scenario_type=ScenarioType.SECURITIES_COMPARE,
    description=(
        "Сравнение нескольких бумаг: получение данных по всем тикерам, "
        "расчёт метрик и корреляций, сравнительный анализ"
    ),
    steps=[
        PipelineStep(
            subagent_name="market_data",
            required=True,
            timeout_seconds=45.0,  # Больше времени для нескольких тикеров
            result_key="market_data",
        ),
        PipelineStep(
            subagent_name="risk_analytics",
            required=False,  # Корреляции опциональны
            timeout_seconds=30.0,
            depends_on=["market_data"],
            result_key="risk_analytics",
        ),
        PipelineStep(
            subagent_name="dashboard",
            required=False,
            timeout_seconds=15.0,
            depends_on=["market_data"],
            result_key="dashboard",
        ),
        PipelineStep(
            subagent_name="explainer",
            required=True,
            timeout_seconds=30.0,
            depends_on=["market_data"],
            result_key="explainer",
        ),
    ],
)


INDEX_SCAN_PIPELINE = ScenarioPipeline(
    scenario_type=ScenarioType.INDEX_SCAN,
    description=(
        "Анализ индекса: получение состава индекса, расчёт метрик "
        "по компонентам, выявление рискованных бумаг"
    ),
    steps=[
        PipelineStep(
            subagent_name="market_data",
            required=True,
            timeout_seconds=45.0,
            result_key="market_data",
        ),
        PipelineStep(
            subagent_name="risk_analytics",
            required=False,  # Риск-расчёты опциональны
            timeout_seconds=30.0,
            depends_on=["market_data"],
            result_key="risk_analytics",
        ),
        PipelineStep(
            subagent_name="dashboard",
            required=False,
            timeout_seconds=15.0,
            depends_on=["market_data"],
            result_key="dashboard",
        ),
        PipelineStep(
            subagent_name="explainer",
            required=True,
            timeout_seconds=30.0,
            depends_on=["market_data"],
            result_key="explainer",
        ),
    ],
)


# Fallback pipeline для неизвестных сценариев
UNKNOWN_PIPELINE = ScenarioPipeline(
    scenario_type=ScenarioType.UNKNOWN,
    description=(
        "Fallback pipeline: попытка общего ответа на основе LLM"
    ),
    steps=[
        PipelineStep(
            subagent_name="explainer",
            required=True,
            timeout_seconds=30.0,
            result_key="explainer",
        ),
    ],
)


# =============================================================================
# Реестр pipeline'ов
# =============================================================================

_PIPELINE_REGISTRY: dict[ScenarioType, ScenarioPipeline] = {
    ScenarioType.PORTFOLIO_RISK: PORTFOLIO_RISK_PIPELINE,
    ScenarioType.CFO_LIQUIDITY: CFO_LIQUIDITY_PIPELINE,
    ScenarioType.ISSUER_COMPARE: ISSUER_COMPARE_PIPELINE,
    ScenarioType.SECURITY_OVERVIEW: SECURITY_OVERVIEW_PIPELINE,
    ScenarioType.SECURITIES_COMPARE: SECURITIES_COMPARE_PIPELINE,
    ScenarioType.INDEX_SCAN: INDEX_SCAN_PIPELINE,
    ScenarioType.UNKNOWN: UNKNOWN_PIPELINE,
}


def get_pipeline(scenario_type: ScenarioType) -> ScenarioPipeline:
    """
    Получить pipeline для заданного типа сценария.

    Args:
        scenario_type: Тип сценария.

    Returns:
        ScenarioPipeline для выполнения сценария.
    """
    pipeline = _PIPELINE_REGISTRY.get(scenario_type)
    if pipeline is None:
        logger.warning(
            "No pipeline found for scenario %s, using UNKNOWN",
            scenario_type,
        )
        return UNKNOWN_PIPELINE
    return pipeline


def list_pipelines() -> list[ScenarioPipeline]:
    """
    Получить список всех зарегистрированных pipeline'ов.

    Returns:
        Список всех ScenarioPipeline.
    """
    return list(_PIPELINE_REGISTRY.values())


def get_pipeline_summary(scenario_type: ScenarioType) -> str:
    """
    Получить краткое описание pipeline в виде строки.

    Args:
        scenario_type: Тип сценария.

    Returns:
        Строка вида "market_data → risk_analytics → dashboard → explainer".
    """
    pipeline = get_pipeline(scenario_type)
    step_names = [step.subagent_name for step in pipeline.steps]
    required_marks = ["*" if step.required else "" for step in pipeline.steps]
    labeled_steps = [f"{name}{mark}" for name, mark in zip(step_names, required_marks)]
    return " → ".join(labeled_steps)


