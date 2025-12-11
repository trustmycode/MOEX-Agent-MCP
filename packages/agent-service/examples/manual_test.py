#!/usr/bin/env python3
"""
Скрипт для ручного тестирования мультиагентной архитектуры.

Запуск:
    cd packages/agent-service
    python examples/manual_test.py

Этот скрипт эмулирует реальный сценарий работы системы:
1. Создаёт несколько сабагентов (MarketData, RiskAnalytics, Explainer)
2. Регистрирует их в SubagentRegistry
3. Эмулирует поток оркестратора: контекст → сабагенты → результат
"""

import asyncio
import sys
from pathlib import Path

# Добавляем src в path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from agent_service.core import (
    AgentContext,
    BaseSubagent,
    SubagentRegistry,
    SubagentResult,
)


# ============================================================================
# Реализации сабагентов (приближённые к проду)
# ============================================================================


class MarketDataSubagent(BaseSubagent):
    """
    Сабагент для получения рыночных данных.
    В проде: вызывает moex-iss-mcp через MCP-клиент.
    """

    def __init__(self):
        super().__init__(
            name="market_data",
            description="Провайдер рыночных данных через moex-iss-mcp",
            capabilities=["get_ohlcv", "get_snapshot", "get_index_constituents"],
        )

    async def execute(self, context: AgentContext) -> SubagentResult:
        print(f"  📊 MarketDataSubagent: обрабатываю запрос '{context.user_query[:50]}...'")
        
        # Эмуляция вызова MCP (в проде здесь будет mcp_client.call_tool(...))
        await asyncio.sleep(0.3)  # Имитация сетевого запроса
        
        # Извлекаем тикеры из контекста (в проде — парсинг через LLM)
        tickers = context.get_metadata("tickers", ["SBER", "GAZP"])
        
        # Эмуляция ответа MCP
        market_data = {
            ticker: {
                "price": 290.5 + hash(ticker) % 100,
                "volume": 1_000_000 + hash(ticker) % 500_000,
                "change_pct": round((hash(ticker) % 10 - 5) / 10, 2),
            }
            for ticker in tickers
        }
        
        # Сохраняем в контекст для других сабагентов
        context.add_result("market_data", market_data)
        
        print(f"  ✅ MarketDataSubagent: получены данные по {len(tickers)} тикерам")
        return SubagentResult.success(
            data=market_data,
            next_agent_hint="risk_analytics",
        )


class RiskAnalyticsSubagent(BaseSubagent):
    """
    Сабагент для риск-аналитики.
    В проде: вызывает risk-analytics-mcp.
    """

    def __init__(self):
        super().__init__(
            name="risk_analytics",
            description="Расчёт портфельного риска через risk-analytics-mcp",
            capabilities=["compute_risk", "compute_var", "compute_correlation"],
        )

    async def execute(self, context: AgentContext) -> SubagentResult:
        print(f"  📈 RiskAnalyticsSubagent: рассчитываю риск-метрики...")
        
        # Получаем данные от предыдущего сабагента
        market_data = context.get_result("market_data")
        if not market_data:
            return SubagentResult.create_error(
                error="Нет рыночных данных от MarketDataSubagent"
            )
        
        await asyncio.sleep(0.2)  # Имитация расчётов
        
        # Эмуляция расчёта риска
        risk_metrics = {
            "portfolio_volatility": 0.18,
            "var_95": -0.032,
            "sharpe_ratio": 1.25,
            "max_drawdown": -0.15,
            "per_instrument": {
                ticker: {
                    "weight": round(1 / len(market_data), 2),
                    "contribution_to_risk": round(0.18 / len(market_data), 3),
                }
                for ticker in market_data
            },
        }
        
        context.add_result("risk_metrics", risk_metrics)
        
        print(f"  ✅ RiskAnalyticsSubagent: volatility={risk_metrics['portfolio_volatility']:.1%}")
        return SubagentResult.success(
            data=risk_metrics,
            next_agent_hint="explainer",
        )


class ExplainerSubagent(BaseSubagent):
    """
    Сабагент для генерации текстового отчёта.
    В проде: вызывает LLM для генерации объяснения.
    """

    def __init__(self):
        super().__init__(
            name="explainer",
            description="Генерация текстового отчёта для пользователя",
            capabilities=["generate_report", "explain_metrics"],
        )

    async def execute(self, context: AgentContext) -> SubagentResult:
        print(f"  📝 ExplainerSubagent: генерирую отчёт для роли '{context.user_role}'...")
        
        risk_metrics = context.get_result("risk_metrics")
        market_data = context.get_result("market_data")
        
        await asyncio.sleep(0.15)  # Имитация LLM-вызова
        
        # Генерация отчёта (в проде — через LLM)
        tickers = list(market_data.keys()) if market_data else []
        vol = risk_metrics.get("portfolio_volatility", 0) if risk_metrics else 0
        var_95 = risk_metrics.get("var_95", 0) if risk_metrics else 0
        sharpe_ratio = risk_metrics.get("sharpe_ratio", 0) if risk_metrics else 0
        
        report = f"""
## Анализ портфеля

**Состав:** {', '.join(tickers)}

### Ключевые метрики риска
- Волатильность портфеля: {vol:.1%}
- VaR (95%): {var_95:.1%}
- Sharpe Ratio: {sharpe_ratio:.2f}

### Рекомендации для {context.user_role or 'аналитика'}
Портфель демонстрирует {"умеренный" if vol < 0.2 else "повышенный"} уровень риска.
"""
        
        context.add_result("report", {"text": report})
        
        print(f"  ✅ ExplainerSubagent: отчёт сгенерирован ({len(report)} символов)")
        return SubagentResult.success(data={"text": report})


# ============================================================================
# Эмуляция оркестратора
# ============================================================================


async def run_orchestrator(
    registry: SubagentRegistry,
    user_query: str,
    user_role: str = "CFO",
    tickers: list[str] | None = None,
) -> dict:
    """
    Эмулирует работу OrchestratorAgent.
    
    В проде это будет отдельный класс OrchestratorAgent,
    который определяет сценарий и вызывает сабагентов по плану.
    """
    print("\n" + "=" * 60)
    print(f"🚀 ЗАПУСК ОРКЕСТРАТОРА")
    print("=" * 60)
    
    # 1. Создаём контекст (в проде — из A2A-запроса)
    context = AgentContext(
        user_query=user_query,
        user_role=user_role,
        scenario_type="portfolio_risk_basic",  # В проде определяется ResearchPlannerSubagent
    )
    context.set_metadata("tickers", tickers or ["SBER", "GAZP", "LKOH"])
    
    print(f"\n📋 Контекст создан:")
    print(f"   session_id: {context.session_id[:8]}...")
    print(f"   user_role: {context.user_role}")
    print(f"   scenario: {context.scenario_type}")
    print(f"   tickers: {context.get_metadata('tickers')}")
    
    # 2. План выполнения (в проде определяется ResearchPlannerSubagent)
    execution_plan = ["market_data", "risk_analytics", "explainer"]
    print(f"\n📝 План выполнения: {' → '.join(execution_plan)}")
    
    # 3. Выполняем сабагенты по плану
    print(f"\n🔄 Выполнение плана:")
    
    for step_name in execution_plan:
        agent = registry.get(step_name)
        if not agent:
            context.add_error(f"Сабагент '{step_name}' не найден")
            continue
        
        result = await agent.safe_execute(context)
        
        if result.is_error:
            context.add_error(f"{step_name}: {result.error_message}")
            print(f"  ❌ {step_name}: ОШИБКА - {result.error_message}")
            break
    
    # 4. Агрегируем результат
    print(f"\n📦 Агрегация результатов...")
    
    final_output = {
        "session_id": context.session_id,
        "scenario_type": context.scenario_type,
        "output": {
            "text": context.get_result("report", {}).get("text", ""),
            "dashboard": {
                "metrics": context.get_result("risk_metrics"),
                "market_data": context.get_result("market_data"),
            },
        },
        "errors": context.errors,
        "has_errors": context.has_errors(),
    }
    
    return final_output


# ============================================================================
# Интерактивное меню
# ============================================================================


def print_menu():
    print("\n" + "=" * 60)
    print("🧪 РУЧНОЕ ТЕСТИРОВАНИЕ МУЛЬТИАГЕНТНОЙ АРХИТЕКТУРЫ")
    print("=" * 60)
    print("\nВыберите действие:")
    print("  1. Запустить полный сценарий portfolio_risk")
    print("  2. Просмотреть зарегистрированные сабагенты")
    print("  3. Тест AgentContext (создание/модификация)")
    print("  4. Тест SubagentResult (все статусы)")
    print("  5. Тест отдельного сабагента")
    print("  6. Тест с ошибкой (отсутствующий сабагент)")
    print("  q. Выход")


async def interactive_mode():
    """Интерактивный режим тестирования."""
    
    # Инициализация
    registry = SubagentRegistry()
    registry.register(MarketDataSubagent())
    registry.register(RiskAnalyticsSubagent())
    registry.register(ExplainerSubagent())
    
    print("\n✅ Инициализация завершена:")
    print(f"   Зарегистрировано сабагентов: {len(registry)}")
    
    while True:
        print_menu()
        choice = input("\n> Ваш выбор: ").strip().lower()
        
        if choice == "q":
            print("\n👋 До свидания!")
            break
        
        elif choice == "1":
            # Полный сценарий
            result = await run_orchestrator(
                registry=registry,
                user_query="Оцени риск моего портфеля: SBER, GAZP, LKOH. Дай рекомендации для CFO.",
                user_role="CFO",
                tickers=["SBER", "GAZP", "LKOH"],
            )
            
            print("\n" + "=" * 60)
            print("📊 ИТОГОВЫЙ РЕЗУЛЬТАТ")
            print("=" * 60)
            print(f"\nSession: {result['session_id'][:8]}...")
            print(f"Scenario: {result['scenario_type']}")
            print(f"Errors: {result['errors'] or 'Нет'}")
            print(f"\n--- OUTPUT.TEXT ---")
            print(result["output"]["text"])
        
        elif choice == "2":
            # Список сабагентов
            print("\n📋 Зарегистрированные сабагенты:")
            for name in registry.list_available():
                agent = registry.get(name)
                print(f"\n  [{name}]")
                print(f"    Описание: {agent.description}")
                print(f"    Capabilities: {agent.capabilities}")
        
        elif choice == "3":
            # Тест AgentContext
            print("\n🧪 Тестирование AgentContext:")
            ctx = AgentContext(
                user_query="Тестовый запрос",
                user_role="analyst",
            )
            print(f"  Создан контекст: session_id={ctx.session_id[:8]}...")
            
            ctx.add_result("test_key", {"value": 42})
            print(f"  Добавлен результат: {ctx.get_result('test_key')}")
            
            ctx.add_error("Тестовая ошибка")
            print(f"  Добавлена ошибка: has_errors={ctx.has_errors()}")
            
            ctx.set_metadata("locale", "ru")
            print(f"  Метаданные: locale={ctx.get_metadata('locale')}")
            
            print(f"\n  JSON:")
            print(f"  {ctx.model_dump_json(indent=2)[:500]}...")
        
        elif choice == "4":
            # Тест SubagentResult
            print("\n🧪 Тестирование SubagentResult:")
            
            success = SubagentResult.success(data={"key": "value"}, next_agent_hint="next")
            print(f"\n  SUCCESS: status={success.status}, is_success={success.is_success}")
            print(f"    data={success.data}, next_hint={success.next_agent_hint}")
            
            error = SubagentResult.create_error(error="Что-то пошло не так")
            print(f"\n  ERROR: status={error.status}, is_error={error.is_error}")
            print(f"    error_message={error.error_message}")
            
            partial = SubagentResult.partial(data={"partial": True}, error="Частичные данные")
            print(f"\n  PARTIAL: status={partial.status}, is_partial={partial.is_partial}")
            print(f"    data={partial.data}, error_message={partial.error_message}")
        
        elif choice == "5":
            # Тест отдельного сабагента
            print("\n🧪 Тест отдельного сабагента:")
            print("  Доступные: " + ", ".join(registry.list_available()))
            name = input("  Введите имя сабагента: ").strip()
            
            agent = registry.get(name)
            if agent:
                ctx = AgentContext(user_query="Тестовый запрос для " + name)
                ctx.set_metadata("tickers", ["SBER"])
                result = await agent.safe_execute(ctx)
                print(f"\n  Результат: status={result.status}")
                print(f"  Data: {result.data}")
            else:
                print(f"  ❌ Сабагент '{name}' не найден")
        
        elif choice == "6":
            # Тест с ошибкой
            result = await run_orchestrator(
                registry=SubagentRegistry(),  # Пустой реестр!
                user_query="Запрос в пустой реестр",
                user_role="test",
            )
            print(f"\n❌ Ошибки: {result['errors']}")
        
        else:
            print("  ⚠️ Неизвестная команда")


# ============================================================================
# Точка входа
# ============================================================================


def main():
    print("""
╔══════════════════════════════════════════════════════════════╗
║     MOEX Market Analyst Agent - Multi-Agent Architecture    ║
║                    Manual Testing Tool                       ║
╚══════════════════════════════════════════════════════════════╝
    """)
    
    asyncio.run(interactive_mode())


if __name__ == "__main__":
    main()
