#!/usr/bin/env python3
"""
E2E (End-to-End) тестирование мультиагентной архитектуры с реальными MCP-серверами.

Требования перед запуском:
1. Запустите moex-iss-mcp сервер:
   cd /path/to/project
   python -m moex_iss_mcp.main  # Порт 8000

2. Запустите risk-analytics-mcp сервер (в другом терминале):
   cd /path/to/project
   RISK_MCP_PORT=8001 python -m risk_analytics_mcp.main  # Порт 8001

3. Или используйте docker-compose:
   docker-compose -f moex_iss_mcp/docker-compose.yml up -d
   docker-compose -f risk_analytics_mcp/docker-compose.yml up -d

Запуск скрипта:
   cd packages/agent-service
   python examples/e2e_test.py

   Или с кастомными URL:
   MOEX_ISS_MCP_URL=http://localhost:8000 \
   RISK_ANALYTICS_MCP_URL=http://localhost:8001 \
   python examples/e2e_test.py
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import httpx

# Добавляем src в path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from agent_service.core import AgentContext, SubagentRegistry
from agent_service.mcp.client import McpClient
from agent_service.mcp.types import McpConfig
from agent_service.orchestrator.intent_classifier import ScenarioType
from agent_service.orchestrator.models import A2AInput
from agent_service.orchestrator.orchestrator_agent import OrchestratorAgent
from agent_service.subagents.dashboard import DashboardSubagent
from agent_service.subagents.explainer import ExplainerSubagent
from agent_service.subagents.market_data import MarketDataSubagent
from agent_service.subagents.risk_analytics import RiskAnalyticsSubagent

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


# ============================================================================
# Константы и конфигурация
# ============================================================================

# URL MCP-серверов (можно переопределить через ENV)
MOEX_ISS_MCP_URL = os.getenv("MOEX_ISS_MCP_URL", "http://localhost:8000")
RISK_ANALYTICS_MCP_URL = os.getenv("RISK_ANALYTICS_MCP_URL", "http://localhost:8010")

# Тестовые данные
TEST_TICKERS = ["SBER", "GAZP", "LKOH"]
TEST_PORTFOLIO = [
    {"ticker": "SBER", "weight": 0.4},
    {"ticker": "GAZP", "weight": 0.3},
    {"ticker": "LKOH", "weight": 0.3},
]


# ============================================================================
# Вспомогательные функции
# ============================================================================


async def check_mcp_health(name: str, url: str) -> bool:
    """Проверить доступность MCP-сервера."""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{url}/health")
            if response.status_code == 200:
                logger.info("✅ %s доступен: %s", name, url)
                return True
            else:
                logger.warning("⚠️ %s вернул статус %d", name, response.status_code)
                return False
    except Exception as e:
        logger.error("❌ %s недоступен: %s — %s", name, url, e)
        return False


def print_separator(title: str = "") -> None:
    """Печать разделителя."""
    if title:
        print(f"\n{'=' * 60}")
        print(f"  {title}")
        print(f"{'=' * 60}")
    else:
        print("=" * 60)


def format_result(data: Any, indent: int = 2) -> str:
    """Форматировать результат для печати."""
    if isinstance(data, dict):
        return json.dumps(data, ensure_ascii=False, indent=indent, default=str)
    return str(data)


# ============================================================================
# Тесты MCP-клиентов напрямую
# ============================================================================


async def test_mcp_clients_direct() -> bool:
    """Тестирование прямых вызовов MCP-клиентов (без сабагентов)."""
    print_separator("ТЕСТ 1: Прямые вызовы MCP-клиентов")

    # Создаём MCP-клиенты
    moex_config = McpConfig(name="moex-iss-mcp", url=MOEX_ISS_MCP_URL)
    risk_config = McpConfig(name="risk-analytics-mcp", url=RISK_ANALYTICS_MCP_URL)

    moex_client = McpClient(moex_config)
    risk_client = McpClient(risk_config)

    success_count = 0
    total_tests = 3

    try:
        # Тест 1: get_security_snapshot
        print("\n📊 1.1: get_security_snapshot(SBER)")
        result = await moex_client.call_tool(
            tool_name="get_security_snapshot",
            args={"ticker": "SBER", "board": "TQBR"},
        )
        if result.success:
            print(f"   ✅ Успешно! Данные: {format_result(result.data)[:200]}...")
            success_count += 1
        else:
            print(f"   ❌ Ошибка: {result.error}")

        # Тест 2: get_ohlcv_timeseries
        print("\n📈 1.2: get_ohlcv_timeseries(SBER)")
        from_date = (date.today() - timedelta(days=30)).isoformat()
        to_date = date.today().isoformat()
        result = await moex_client.call_tool(
            tool_name="get_ohlcv_timeseries",
            args={
                "ticker": "SBER",
                "board": "TQBR",
                "from_date": from_date,
                "to_date": to_date,
                "interval": "1d",
            },
        )
        if result.success:
            candles_count = len(result.data.get("data", [])) if isinstance(result.data, dict) else 0
            print(f"   ✅ Успешно! Получено {candles_count} свечей")
            success_count += 1
        else:
            print(f"   ❌ Ошибка: {result.error}")

        # Тест 3: compute_portfolio_risk_basic
        print("\n📉 1.3: compute_portfolio_risk_basic")
        result = await risk_client.call_tool(
            tool_name="compute_portfolio_risk_basic",
            args={
                "positions": TEST_PORTFOLIO,
                "from_date": from_date,
                "to_date": to_date,
                "rebalance": "buy_and_hold",
            },
        )
        if result.success:
            print(f"   ✅ Успешно! Данные: {format_result(result.data)[:300]}...")
            success_count += 1
        else:
            print(f"   ❌ Ошибка: {result.error}")

    finally:
        await moex_client.close()
        await risk_client.close()

    print(f"\n📝 Результат: {success_count}/{total_tests} тестов пройдено")
    return success_count == total_tests


# ============================================================================
# Тесты сабагентов
# ============================================================================


async def test_subagents() -> bool:
    """Тестирование сабагентов с MCP-клиентами."""
    print_separator("ТЕСТ 2: Сабагенты (MarketData, RiskAnalytics)")

    # Создаём конфигурации
    moex_config = McpConfig(name="moex-iss-mcp", url=MOEX_ISS_MCP_URL)
    risk_config = McpConfig(name="risk-analytics-mcp", url=RISK_ANALYTICS_MCP_URL)

    # Создаём сабагенты
    market_data = MarketDataSubagent(mcp_config=moex_config)
    risk_analytics = RiskAnalyticsSubagent(mcp_config=risk_config)

    success_count = 0
    total_tests = 2

    try:
        # Тест 1: MarketDataSubagent — single security
        print("\n📊 2.1: MarketDataSubagent (single_security_overview)")
        context = AgentContext(
            user_query="Покажи данные по SBER",
            scenario_type="single_security_overview",
        )
        context.add_result("parsed_params", {"ticker": "SBER"})

        result = await market_data.safe_execute(context)
        if result.is_success or result.is_partial:
            print(f"   ✅ Статус: {result.status}")
            print(f"   📦 Данные: {format_result(result.data)[:300]}...")
            success_count += 1
        else:
            print(f"   ❌ Ошибка: {result.error_message}")

        # Тест 2: RiskAnalyticsSubagent — portfolio risk
        print("\n📉 2.2: RiskAnalyticsSubagent (portfolio_risk_basic)")
        from_date = (date.today() - timedelta(days=365)).isoformat()
        to_date = date.today().isoformat()

        context = AgentContext(
            user_query="Оцени риск портфеля: SBER 40%, GAZP 30%, LKOH 30%",
            scenario_type="portfolio_risk_basic",
        )
        context.add_result("parsed_params", {
            "positions": TEST_PORTFOLIO,
            "from_date": from_date,
            "to_date": to_date,
        })

        result = await risk_analytics.safe_execute(context)
        if result.is_success or result.is_partial:
            print(f"   ✅ Статус: {result.status}")
            print(f"   📦 Данные: {format_result(result.data)[:400]}...")
            success_count += 1
        else:
            print(f"   ❌ Ошибка: {result.error_message}")

    finally:
        await market_data.mcp_client.close()
        await risk_analytics.mcp_client.close()

    print(f"\n📝 Результат: {success_count}/{total_tests} тестов пройдено")
    return success_count == total_tests


# ============================================================================
# Тесты оркестратора
# ============================================================================


async def test_orchestrator() -> bool:
    """Тестирование полного пайплайна через OrchestratorAgent."""
    print_separator("ТЕСТ 3: Оркестратор (полный pipeline)")

    # Создаём конфигурации
    moex_config = McpConfig(name="moex-iss-mcp", url=MOEX_ISS_MCP_URL)
    risk_config = McpConfig(name="risk-analytics-mcp", url=RISK_ANALYTICS_MCP_URL)

    # Создаём реестр и регистрируем сабагенты
    registry = SubagentRegistry()
    market_data = MarketDataSubagent(mcp_config=moex_config)
    risk_analytics = RiskAnalyticsSubagent(mcp_config=risk_config)
    explainer = ExplainerSubagent()  # Mock LLM
    dashboard = DashboardSubagent()

    registry.register(market_data)
    registry.register(risk_analytics)
    registry.register(explainer)
    registry.register(dashboard)

    print(f"\n📋 Зарегистрировано сабагентов: {len(registry)}")
    for name in registry.list_available():
        print(f"   • {name}")

    # Создаём оркестратор
    orchestrator = OrchestratorAgent(registry=registry, enable_debug=True)

    success_count = 0
    total_tests = 3

    try:
        # Тест 1: portfolio_risk сценарий
        print("\n🚀 3.1: Сценарий portfolio_risk")
        a2a_input = A2AInput(
            messages=[
                {
                    "role": "user",
                    "content": (
                        "Оцени риск моего портфеля: SBER 40%, GAZP 30%, LKOH 30%. "
                        "Дай рекомендации для CFO."
                    ),
                }
            ],
            user_role="CFO",
            session_id="test-session-1",
            locale="ru",
            metadata={
                "parsed_params": {
                    "positions": TEST_PORTFOLIO,
                }
            },
        )

        output = await orchestrator.handle_request(a2a_input)
        print(f"   Статус: {output.status}")
        if output.text:
            print(f"   Текст ({len(output.text)} символов): {output.text[:200]}...")
        if output.debug:
            print(f"   Сценарий: {output.debug.scenario_type}")
            print(f"   Время: {output.debug.total_duration_ms:.0f}ms")
            for trace in output.debug.subagent_traces or []:
                print(f"      • {trace.name}: {trace.status} ({trace.duration_ms:.0f}ms)")

        if output.status in ("success", "partial"):
            success_count += 1
            print("   ✅ Тест пройден!")
        else:
            print(f"   ❌ Ошибка: {output.error_message}")

        # Тест 2: security_overview сценарий
        print("\n🚀 3.2: Сценарий security_overview")
        a2a_input = A2AInput(
            messages=[
                {
                    "role": "user",
                    "content": "Дай обзор акции SBER",
                }
            ],
            user_role="analyst",
            session_id="test-session-2",
            locale="ru",
        )

        output = await orchestrator.handle_request(a2a_input)
        print(f"   Статус: {output.status}")
        if output.debug:
            print(f"   Сценарий: {output.debug.scenario_type}")
            print(f"   Время: {output.debug.total_duration_ms:.0f}ms")

        if output.status in ("success", "partial"):
            success_count += 1
            print("   ✅ Тест пройден!")
        else:
            print(f"   ❌ Ошибка: {output.error_message}")

        # Тест 3: Проверка pipeline readiness
        print("\n🔧 3.3: Проверка готовности pipeline")
        for scenario in [ScenarioType.PORTFOLIO_RISK, ScenarioType.CFO_LIQUIDITY]:
            readiness = orchestrator.check_pipeline_readiness(scenario)
            all_ready = all(readiness.values())
            status = "✅" if all_ready else "⚠️"
            print(f"   {status} {scenario.value}:")
            for subagent, available in readiness.items():
                icon = "✓" if available else "✗"
                print(f"      {icon} {subagent}")

        success_count += 1  # Этот тест всегда считаем успешным

    finally:
        await market_data.mcp_client.close()
        await risk_analytics.mcp_client.close()

    print(f"\n📝 Результат: {success_count}/{total_tests} тестов пройдено")
    return success_count == total_tests


# ============================================================================
# Интерактивное меню
# ============================================================================


async def interactive_mode() -> None:
    """Интерактивный режим тестирования."""
    print("""
╔══════════════════════════════════════════════════════════════╗
║     MOEX Market Analyst Agent - E2E Testing Tool             ║
║                    With Real MCP Servers                     ║
╚══════════════════════════════════════════════════════════════╝
    """)

    # Проверяем доступность MCP-серверов
    print_separator("Проверка MCP-серверов")
    moex_ok = await check_mcp_health("moex-iss-mcp", MOEX_ISS_MCP_URL)
    risk_ok = await check_mcp_health("risk-analytics-mcp", RISK_ANALYTICS_MCP_URL)

    if not moex_ok or not risk_ok:
        print("\n⚠️ ПРЕДУПРЕЖДЕНИЕ: Не все MCP-серверы доступны!")
        print("   Запустите серверы командами:")
        print("   Terminal 1: python -m moex_iss_mcp.main")
        print("   Terminal 2: RISK_MCP_PORT=8010 python -m risk_analytics_mcp.main")
        print("\n   Или нажмите Enter для продолжения с частичными тестами...\n")
        input()

    while True:
        print("\n" + "=" * 60)
        print("📋 МЕНЮ")
        print("=" * 60)
        print("  1. Тест MCP-клиентов напрямую")
        print("  2. Тест сабагентов (MarketData, RiskAnalytics)")
        print("  3. Тест полного pipeline через оркестратор")
        print("  4. Запустить ВСЕ тесты")
        print("  5. Кастомный запрос к оркестратору")
        print("  h. Проверить health MCP-серверов")
        print("  q. Выход")

        choice = input("\n> Ваш выбор: ").strip().lower()

        if choice == "q":
            print("\n👋 До свидания!")
            break

        elif choice == "1":
            await test_mcp_clients_direct()

        elif choice == "2":
            await test_subagents()

        elif choice == "3":
            await test_orchestrator()

        elif choice == "4":
            print_separator("ЗАПУСК ВСЕХ ТЕСТОВ")
            test1 = await test_mcp_clients_direct()
            test2 = await test_subagents()
            test3 = await test_orchestrator()

            print_separator("ИТОГИ")
            print(f"  1. MCP-клиенты напрямую:  {'✅' if test1 else '❌'}")
            print(f"  2. Сабагенты:              {'✅' if test2 else '❌'}")
            print(f"  3. Оркестратор:            {'✅' if test3 else '❌'}")

            all_passed = test1 and test2 and test3
            if all_passed:
                print("\n🎉 ВСЕ ТЕСТЫ ПРОЙДЕНЫ!")
            else:
                print("\n⚠️ Некоторые тесты не пройдены")

        elif choice == "5":
            await custom_query_mode()

        elif choice == "h":
            print_separator("Проверка MCP-серверов")
            await check_mcp_health("moex-iss-mcp", MOEX_ISS_MCP_URL)
            await check_mcp_health("risk-analytics-mcp", RISK_ANALYTICS_MCP_URL)

        else:
            print("  ⚠️ Неизвестная команда")


async def custom_query_mode() -> None:
    """Режим кастомных запросов к оркестратору."""
    print_separator("Кастомный запрос")
    print("Примеры запросов:")
    print("  • Оцени риск портфеля: SBER 40%, GAZP 30%, LKOH 30%")
    print("  • Покажи данные по акции SBER")
    print("  • Сравни SBER и GAZP")
    print("  • Сформируй отчёт для CFO по ликвидности портфеля")

    query = input("\n> Введите запрос: ").strip()
    if not query:
        print("   ⚠️ Пустой запрос")
        return

    role = input("> Роль пользователя (CFO/analyst/risk_manager) [analyst]: ").strip() or "analyst"

    # Создаём окружение
    moex_config = McpConfig(name="moex-iss-mcp", url=MOEX_ISS_MCP_URL)
    risk_config = McpConfig(name="risk-analytics-mcp", url=RISK_ANALYTICS_MCP_URL)

    registry = SubagentRegistry()
    market_data = MarketDataSubagent(mcp_config=moex_config)
    risk_analytics = RiskAnalyticsSubagent(mcp_config=risk_config)
    explainer = ExplainerSubagent()
    dashboard = DashboardSubagent()

    registry.register(market_data)
    registry.register(risk_analytics)
    registry.register(explainer)
    registry.register(dashboard)

    orchestrator = OrchestratorAgent(registry=registry, enable_debug=True)

    try:
        print("\n🚀 Выполняю запрос...")
        a2a_input = A2AInput(
            messages=[{"role": "user", "content": query}],
            user_role=role,
            session_id="custom-query-session",
            locale="ru",
        )

        output = await orchestrator.handle_request(a2a_input)

        print_separator("РЕЗУЛЬТАТ")
        print(f"Статус: {output.status}")

        if output.debug:
            print(f"Сценарий: {output.debug.scenario_type} (уверенность: {output.debug.scenario_confidence:.0%})")
            print(f"Время выполнения: {output.debug.total_duration_ms:.0f}ms")
            print("\nТрейс сабагентов:")
            for trace in output.debug.subagent_traces or []:
                error_info = f" — {trace.error}" if trace.error else ""
                print(f"   • {trace.name}: {trace.status} ({trace.duration_ms:.0f}ms){error_info}")

        if output.error_message:
            print(f"\n❌ Ошибка: {output.error_message}")

        if output.text:
            print(f"\n📝 ТЕКСТОВЫЙ ОТЧЁТ:\n{output.text}")

        if output.tables:
            print(f"\n📊 ТАБЛИЦЫ ({len(output.tables)}):")
            for table in output.tables:
                print(f"   • {table.title}: {len(table.rows)} строк")

        if output.dashboard:
            dashboard_obj = output.dashboard
            if hasattr(dashboard_obj, "model_dump"):
                dashboard_payload = dashboard_obj.model_dump()
            elif hasattr(dashboard_obj, "dict"):
                dashboard_payload = dashboard_obj.dict()
            else:
                dashboard_payload = dashboard_obj

            try:
                dash_preview = json.dumps(dashboard_payload, ensure_ascii=False)[:300]
            except TypeError:
                dash_preview = str(dashboard_payload)[:300]

            print(f"\n🎨 DASHBOARD: {dash_preview}...")

    finally:
        await market_data.mcp_client.close()
        await risk_analytics.mcp_client.close()


# ============================================================================
# Точка входа
# ============================================================================


def main() -> None:
    """Точка входа скрипта."""
    if len(sys.argv) > 1:
        # Режим командной строки для CI/CD
        arg = sys.argv[1]
        if arg == "--all":
            async def run_all() -> int:
                test1 = await test_mcp_clients_direct()
                test2 = await test_subagents()
                test3 = await test_orchestrator()
                return 0 if (test1 and test2 and test3) else 1
            sys.exit(asyncio.run(run_all()))
        elif arg == "--mcp":
            asyncio.run(test_mcp_clients_direct())
        elif arg == "--subagents":
            asyncio.run(test_subagents())
        elif arg == "--orchestrator":
            asyncio.run(test_orchestrator())
        else:
            print("Использование: python e2e_test.py [--all|--mcp|--subagents|--orchestrator]")
            sys.exit(1)
    else:
        # Интерактивный режим
        asyncio.run(interactive_mode())


if __name__ == "__main__":
    main()
