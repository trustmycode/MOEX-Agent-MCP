"""
OrchestratorAgent — центральный координатор мультиагентной системы.

Отвечает за:
1. Приём A2A-запросов
2. Классификацию intent и выбор сценария
3. Выполнение pipeline сабагентов
4. Агрегацию результатов
5. Формирование A2A-ответа
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import TYPE_CHECKING, Any, Optional

from ..core import AgentContext, SubagentRegistry, SubagentResult
from .intent_classifier import IntentClassifier, ScenarioType
from .models import A2AInput, A2AOutput, DebugInfo, SubagentTrace, TableData
from .pipelines import PipelineStep, ScenarioPipeline, get_pipeline
from .query_parser import QueryParser
from .session_store import SessionStateStore

if TYPE_CHECKING:
    from ..core import BaseSubagent

logger = logging.getLogger(__name__)


class OrchestratorAgent:
    """
    Центральный координатор мультиагентной системы.

    Принимает A2A-запросы, определяет сценарий, выполняет pipeline
    сабагентов и формирует финальный ответ.

    Attributes:
        registry: Реестр доступных сабагентов.
        classifier: Классификатор намерений.
        default_timeout: Таймаут по умолчанию для шагов pipeline.
        enable_debug: Включить ли отладочную информацию в ответ.
    """

    def __init__(
        self,
        registry: Optional[SubagentRegistry] = None,
        classifier: Optional[IntentClassifier] = None,
        default_timeout: float = 30.0,
        enable_debug: bool = True,
        query_parser: Optional[QueryParser] = None,
        session_store: Optional[SessionStateStore] = None,
        session_ttl_seconds: float = 900.0,
    ) -> None:
        """
        Инициализация оркестратора.

        Args:
            registry: Реестр сабагентов. Если не указан, создаётся пустой.
            classifier: Классификатор намерений. Если не указан, создаётся новый.
            default_timeout: Таймаут по умолчанию для шагов (секунды).
            enable_debug: Включить отладочную информацию в ответ.
            query_parser: Парсер пользовательских запросов (rule-based/LLM).
            session_store: Хранилище сессионных parsed_params.
            session_ttl_seconds: TTL для сессионных данных (секунды).
        """
        self.registry = registry or SubagentRegistry()
        self.classifier = classifier or IntentClassifier()
        self.default_timeout = default_timeout
        self.enable_debug = enable_debug
        self.query_parser = query_parser or QueryParser()
        self.session_store = session_store or SessionStateStore(ttl_seconds=session_ttl_seconds)

    async def handle_request(self, a2a_input: A2AInput) -> A2AOutput:
        """
        Обработать A2A-запрос.

        Основной публичный метод оркестратора. Выполняет полный цикл:
        1. Извлечение user_query из input
        2. Классификация intent → ScenarioType
        3. Получение pipeline для сценария
        4. Последовательное выполнение шагов pipeline
        5. Агрегация результатов
        6. Формирование A2AOutput

        Args:
            a2a_input: Входящий A2A-запрос.

        Returns:
            A2AOutput с результатом выполнения или ошибкой.
        """
        start_time = time.perf_counter()
        subagent_traces: list[SubagentTrace] = []

        try:
            # Шаг 1: Извлечение запроса
            user_query = a2a_input.user_query
            if not user_query:
                return A2AOutput.error(
                    error_message="Не указан запрос пользователя",
                    debug=self._build_debug_info(
                        ScenarioType.UNKNOWN,
                        0.0,
                        [],
                        subagent_traces,
                        start_time,
                    ),
                )

            logger.info(
                "Processing request: session=%s, query=%s...",
                a2a_input.session_id or "unknown",
                user_query[:100],
            )

            # Шаг 2: Классификация intent
            scenario_type, confidence = self.classifier.classify_with_confidence(
                query=user_query,
                role=a2a_input.user_role,
            )

            logger.info(
                "Classified as %s (confidence=%.2f)",
                scenario_type.value,
                confidence,
            )

            if scenario_type == ScenarioType.UNKNOWN:
                return A2AOutput.error(
                    error_message=(
                        "Не удалось определить тип запроса. "
                        "Пожалуйста, переформулируйте запрос."
                    ),
                    debug=self._build_debug_info(
                        scenario_type,
                        confidence,
                        [],
                        subagent_traces,
                        start_time,
                    ),
                )

            # Шаг 3: Получение pipeline
            pipeline = get_pipeline(scenario_type)
            logger.info(
                "Using pipeline: %s (%d steps)",
                pipeline.description,
                len(pipeline.steps),
            )

            # Шаг 4: Создание AgentContext
            context = AgentContext(
                user_query=user_query,
                session_id=a2a_input.session_id or "",
                user_role=a2a_input.user_role,
                scenario_type=scenario_type.value,
                metadata={
                    "locale": a2a_input.locale,
                    "a2a_metadata": a2a_input.metadata,
                    "confidence": confidence,
                },
            )

            # Подготовка parsed_params: используем сохранённое состояние сессии,
            # данные из клиента и при необходимости — парсер.
            parsed_params = {}
            session_state: dict[str, Any] = {}
            if a2a_input.session_id:
                session_state = self.session_store.get(a2a_input.session_id)
                if session_state:
                    parsed_params.update(session_state)

            client_params = (
                a2a_input.metadata.get("parsed_params", {}) if a2a_input.metadata else {}
            )
            if client_params:
                parsed_params.update(client_params)

            if scenario_type in (ScenarioType.PORTFOLIO_RISK, ScenarioType.CFO_LIQUIDITY):
                if not parsed_params.get("positions"):
                    parse_result = self.query_parser.parse_portfolio(user_query, allow_llm=True)
                    if parse_result.positions:
                        parsed_params["positions"] = parse_result.positions
                if not parsed_params.get("positions"):
                    hint = (
                        "Для портфельных сценариев укажите позиции в parsed_params.positions "
                        "или добавьте в запрос вида: \"SBER 40%, GAZP 30%, LKOH 30%\"."
                    )
                    return A2AOutput.error(
                        error_message=hint,
                        debug=self._build_debug_info(
                            scenario_type,
                            confidence,
                            [],
                            subagent_traces,
                            start_time,
                        ),
                    )

            if parsed_params:
                context.add_result("parsed_params", parsed_params)
                if a2a_input.session_id:
                    self.session_store.set(a2a_input.session_id, parsed_params)

            # Шаг 5: Выполнение pipeline
            result = await self._execute_pipeline(
                pipeline=pipeline,
                context=context,
                subagent_traces=subagent_traces,
            )

            # Шаг 6: Формирование ответа
            return self._build_output(
                result=result,
                context=context,
                scenario_type=scenario_type,
                confidence=confidence,
                subagent_traces=subagent_traces,
                start_time=start_time,
            )

        except Exception as e:
            logger.exception("Orchestrator failed with unexpected error")
            return A2AOutput.error(
                error_message=f"Внутренняя ошибка: {type(e).__name__}: {e}",
                debug=self._build_debug_info(
                    ScenarioType.UNKNOWN,
                    0.0,
                    [],
                    subagent_traces,
                    start_time,
                ),
            )

    async def _execute_pipeline(
        self,
        pipeline: ScenarioPipeline,
        context: AgentContext,
        subagent_traces: list[SubagentTrace],
    ) -> dict[str, Any]:
        """
        Выполнить pipeline сабагентов.

        Последовательно выполняет шаги pipeline, сохраняя промежуточные
        результаты в context.intermediate_results.

        Args:
            pipeline: Pipeline для выполнения.
            context: Контекст выполнения.
            subagent_traces: Список для записи трейсов (мутируется).

        Returns:
            Словарь с результатами: {"success": bool, "data": {...}, "errors": [...]}
        """
        result: dict[str, Any] = {
            "success": True,
            "data": {},
            "errors": [],
        }

        for step in pipeline.steps:
            step_start = time.perf_counter()
            trace = SubagentTrace(
                name=step.subagent_name,
                status="skipped",
                duration_ms=0.0,
            )

            try:
                # Проверяем зависимости
                if not self._check_dependencies(step, context):
                    logger.warning(
                        "Skipping %s: dependencies not satisfied",
                        step.subagent_name,
                    )
                    trace.status = "skipped"
                    trace.error = "Dependencies not satisfied"
                    subagent_traces.append(trace)
                    continue

                # Получаем сабагент из registry
                subagent = self.registry.get(step.subagent_name)
                if subagent is None:
                    logger.warning(
                        "Subagent '%s' not found in registry",
                        step.subagent_name,
                    )
                    if step.required:
                        result["success"] = False
                        result["errors"].append(
                            f"Сабагент '{step.subagent_name}' не найден"
                        )
                        # Прерываем для обязательных шагов
                        trace.status = "error"
                        trace.error = "Subagent not found"
                        trace.duration_ms = (time.perf_counter() - step_start) * 1000
                        subagent_traces.append(trace)
                        break
                    else:
                        trace.status = "skipped"
                        trace.error = "Subagent not found"
                        subagent_traces.append(trace)
                        continue

                # Выполняем сабагент с таймаутом
                timeout = step.timeout_seconds or self.default_timeout
                subagent_result = await self._execute_with_timeout(
                    subagent=subagent,
                    context=context,
                    timeout=timeout,
                )

                # Записываем время выполнения
                trace.duration_ms = (time.perf_counter() - step_start) * 1000

                # Обрабатываем результат
                if subagent_result.is_success:
                    trace.status = "success"
                    context.add_result(step.result_key or step.subagent_name, subagent_result.data)
                    result["data"][step.result_key or step.subagent_name] = subagent_result.data

                elif subagent_result.is_partial:
                    trace.status = "partial"
                    trace.error = subagent_result.error_message
                    # Частичные данные всё равно сохраняем
                    if subagent_result.data:
                        context.add_result(step.result_key or step.subagent_name, subagent_result.data)
                        result["data"][step.result_key or step.subagent_name] = subagent_result.data
                    context.add_error(subagent_result.error_message or "Partial result")

                else:  # error
                    trace.status = "error"
                    trace.error = subagent_result.error_message
                    error_msg = subagent_result.error_message or f"Error in {step.subagent_name}"
                    context.add_error(error_msg)
                    result["errors"].append(error_msg)

                    if step.required:
                        result["success"] = False
                        logger.error(
                            "Required step '%s' failed: %s",
                            step.subagent_name,
                            error_msg,
                        )
                        subagent_traces.append(trace)
                        break  # Прерываем pipeline

            except asyncio.TimeoutError:
                trace.duration_ms = (time.perf_counter() - step_start) * 1000
                trace.status = "error"
                trace.error = f"Timeout after {step.timeout_seconds}s"
                subagent_traces.append(trace)

                error_msg = f"Таймаут при выполнении '{step.subagent_name}'"
                context.add_error(error_msg)
                result["errors"].append(error_msg)

                if step.required:
                    result["success"] = False
                    break

                continue

            except Exception as e:
                trace.duration_ms = (time.perf_counter() - step_start) * 1000
                trace.status = "error"
                trace.error = f"{type(e).__name__}: {e}"
                subagent_traces.append(trace)

                error_msg = f"Ошибка в '{step.subagent_name}': {e}"
                logger.exception("Subagent %s failed", step.subagent_name)
                context.add_error(error_msg)
                result["errors"].append(error_msg)

                if step.required:
                    result["success"] = False
                    break

                continue

            subagent_traces.append(trace)

        return result

    async def _execute_with_timeout(
        self,
        subagent: BaseSubagent,
        context: AgentContext,
        timeout: float,
    ) -> SubagentResult:
        """
        Выполнить сабагент с таймаутом.

        Args:
            subagent: Сабагент для выполнения.
            context: Контекст выполнения.
            timeout: Таймаут в секундах.

        Returns:
            SubagentResult от сабагента.

        Raises:
            asyncio.TimeoutError: При превышении таймаута.
        """
        return await asyncio.wait_for(
            subagent.safe_execute(context),
            timeout=timeout,
        )

    def _check_dependencies(self, step: PipelineStep, context: AgentContext) -> bool:
        """
        Проверить, выполнены ли зависимости шага.

        Args:
            step: Шаг pipeline.
            context: Контекст с промежуточными результатами.

        Returns:
            True если все зависимости выполнены.
        """
        if not step.depends_on:
            return True

        for dep in step.depends_on:
            if context.get_result(dep) is None:
                logger.debug(
                    "Dependency '%s' not satisfied for step '%s'",
                    dep,
                    step.subagent_name,
                )
                return False

        return True

    def _build_output(
        self,
        result: dict[str, Any],
        context: AgentContext,
        scenario_type: ScenarioType,
        confidence: float,
        subagent_traces: list[SubagentTrace],
        start_time: float,
    ) -> A2AOutput:
        """
        Построить финальный A2A-ответ.

        Args:
            result: Результат выполнения pipeline.
            context: Контекст с промежуточными результатами.
            scenario_type: Тип сценария.
            confidence: Уверенность классификации.
            subagent_traces: Трейсы выполнения сабагентов.
            start_time: Время начала выполнения.

        Returns:
            A2AOutput.
        """
        # Извлекаем данные из результатов сабагентов
        text = self._extract_text(context)
        tables = self._extract_tables(context)
        dashboard = self._extract_dashboard(context)

        # Строим debug info
        debug_info = self._build_debug_info(
            scenario_type,
            confidence,
            [step.name for step in subagent_traces],
            subagent_traces,
            start_time,
        )

        # Определяем статус ответа
        if not result["success"]:
            # Если есть хоть какой-то текст, возвращаем partial
            if text and text != self._get_fallback_text():
                return A2AOutput.partial(
                    text=text,
                    error_message="; ".join(result["errors"]),
                    tables=tables,
                    dashboard=dashboard,
                    debug=debug_info if self.enable_debug else None,
                )
            else:
                return A2AOutput.error(
                    error_message="; ".join(result["errors"]) or "Не удалось выполнить запрос",
                    debug=debug_info if self.enable_debug else None,
                )

        # Проверяем, есть ли хоть какой-то текст
        if not text:
            text = self._get_fallback_text()

        return A2AOutput.success(
            text=text,
            tables=tables,
            dashboard=dashboard,
            debug=debug_info if self.enable_debug else None,
        )

    def _extract_text(self, context: AgentContext) -> str:
        """
        Извлечь текстовый отчёт из результатов сабагентов.

        Args:
            context: Контекст с результатами.

        Returns:
            Текстовый отчёт или пустая строка.
        """
        # Ищем результат от explainer
        explainer_result = context.get_result("explainer")
        if explainer_result:
            # Explainer возвращает {"text": "..."} или просто строку
            if isinstance(explainer_result, dict):
                return explainer_result.get("text", "")
            elif isinstance(explainer_result, str):
                return explainer_result

        # Fallback: пытаемся собрать текст из других источников
        return ""

    def _extract_tables(self, context: AgentContext) -> list[TableData]:
        """
        Извлечь табличные данные из результатов сабагентов.

        Args:
            context: Контекст с результатами.

        Returns:
            Список таблиц.
        """
        tables: list[TableData] = []

        # Ищем таблицы в risk_analytics результате
        risk_result = context.get_result("risk_analytics")
        if risk_result and isinstance(risk_result, dict):
            # Таблица позиций
            if "per_instrument" in risk_result:
                per_instrument = risk_result["per_instrument"]
                if per_instrument:
                    columns = ["Тикер", "Вес, %", "Доходность, %", "Волатильность, %", "Max DD, %"]
                    rows = []
                    for item in per_instrument:
                        if isinstance(item, dict):
                            rows.append([
                                item.get("ticker", ""),
                                f"{item.get('weight', 0) * 100:.1f}",
                                f"{item.get('total_return_pct', 0):.2f}",
                                f"{item.get('annualized_volatility_pct', 0):.2f}",
                                f"{item.get('max_drawdown_pct', 0):.2f}",
                            ])
                    if rows:
                        tables.append(TableData(
                            id="positions",
                            title="Позиции портфеля",
                            columns=columns,
                            rows=rows,
                        ))

            # Таблица стресс-сценариев
            if "stress_results" in risk_result:
                stress_results = risk_result["stress_results"]
                if stress_results:
                    columns = ["Сценарий", "Описание", "P&L, %"]
                    rows = []
                    for item in stress_results:
                        if isinstance(item, dict):
                            rows.append([
                                item.get("id", ""),
                                item.get("description", ""),
                                f"{item.get('pnl_pct', 0):.2f}",
                            ])
                    if rows:
                        tables.append(TableData(
                            id="stress_results",
                            title="Результаты стресс-сценариев",
                            columns=columns,
                            rows=rows,
                        ))

        # Таблица сравнения бумаг из market_data (для securities_compare)
        market_data = context.get_result("market_data")
        if market_data and isinstance(market_data, dict):
            securities = market_data.get("securities") or {}
            if securities:
                columns = ["Тикер", "Последняя цена", "Изм. %", "Оборот, ₽", "Интрадей вола"]
                rows: list[list[str]] = []
                for ticker, payload in securities.items():
                    if not isinstance(payload, dict):
                        continue
                    snap = payload.get("snapshot") or {}
                    last_price = snap.get("last_price")
                    price_change_pct = snap.get("price_change_pct")
                    value = snap.get("value")
                    intraday_vol = snap.get("intraday_volatility_estimate")

                    rows.append([
                        str(ticker),
                        f"{last_price:.2f}" if last_price is not None else "—",
                        f"{price_change_pct:.2f}" if price_change_pct is not None else "—",
                        f"{value:,.0f}".replace(",", " ") if value is not None else "—",
                        f"{intraday_vol:.2f}" if intraday_vol is not None else "—",
                    ])

                if any(rows):
                    tables.append(TableData(
                        id="securities_compare",
                        title="Сравнение тикеров",
                        columns=columns,
                        rows=rows,
                    ))

        return tables

    def _extract_dashboard(self, context: AgentContext) -> Optional[dict[str, Any]]:
        """
        Извлечь dashboard из результатов сабагентов.

        Args:
            context: Контекст с результатами.

        Returns:
            RiskDashboardSpec или None.
        """
        dashboard_result = context.get_result("dashboard")
        if dashboard_result and isinstance(dashboard_result, dict):
            return dashboard_result
        return None

    def _build_debug_info(
        self,
        scenario_type: ScenarioType,
        confidence: float,
        pipeline_steps: list[str],
        subagent_traces: list[SubagentTrace],
        start_time: float,
    ) -> DebugInfo:
        """
        Построить отладочную информацию.

        Args:
            scenario_type: Определённый тип сценария.
            confidence: Уверенность классификации.
            pipeline_steps: Список выполненных шагов.
            subagent_traces: Трейсы сабагентов.
            start_time: Время начала выполнения.

        Returns:
            DebugInfo.
        """
        total_duration = (time.perf_counter() - start_time) * 1000

        return DebugInfo(
            scenario_type=scenario_type.value,
            scenario_confidence=confidence,
            pipeline=pipeline_steps,
            subagent_traces=subagent_traces,
            total_duration_ms=total_duration,
        )

    def _get_fallback_text(self) -> str:
        """Получить текст по умолчанию при отсутствии результата от explainer."""
        return (
            "К сожалению, не удалось сформировать текстовый отчёт. "
            "Проверьте наличие данных в таблицах и дашборде."
        )

    # =========================================================================
    # Вспомогательные методы для управления registry
    # =========================================================================

    def register_subagent(self, subagent: BaseSubagent) -> None:
        """
        Зарегистрировать сабагент в оркестраторе.

        Args:
            subagent: Сабагент для регистрации.
        """
        self.registry.register(subagent)
        logger.info("Registered subagent: %s", subagent.name)

    def list_subagents(self) -> list[str]:
        """
        Получить список зарегистрированных сабагентов.

        Returns:
            Список имён сабагентов.
        """
        return self.registry.list_available()

    def check_pipeline_readiness(self, scenario_type: ScenarioType) -> dict[str, bool]:
        """
        Проверить готовность pipeline к выполнению.

        Возвращает словарь с информацией о наличии каждого сабагента.

        Args:
            scenario_type: Тип сценария.

        Returns:
            Словарь {subagent_name: is_available}.
        """
        pipeline = get_pipeline(scenario_type)
        result: dict[str, bool] = {}

        for step in pipeline.steps:
            result[step.subagent_name] = step.subagent_name in self.registry

        return result
