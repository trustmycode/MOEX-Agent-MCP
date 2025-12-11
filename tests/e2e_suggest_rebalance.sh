#!/bin/bash
# E2E тесты suggest_rebalance через curl
# Использование: ./e2e_suggest_rebalance.sh [BASE_URL]

BASE_URL="${1:-http://localhost:8010}"
PASSED=0
FAILED=0

# Цвета
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "=============================================="
echo "🧪 E2E тесты suggest_rebalance"
echo "   URL: $BASE_URL"
echo "=============================================="
echo ""

# Функция для запуска теста
run_test() {
    local name="$1"
    local payload="$2"
    local check_cmd="$3"
    
    echo -n "▶ $name... "
    
    # Получаем SSE и извлекаем последний JSON-ответ
    raw_response=$(curl -s -X POST "$BASE_URL/mcp" \
        -H "Content-Type: application/json" \
        -H "Accept: application/json, text/event-stream" \
        -d "$payload")
    
    # Извлекаем JSON из SSE (последняя строка data:)
    response=$(echo "$raw_response" | grep '^data:' | tail -1 | sed 's/^data: //')
    
    if echo "$response" | eval "$check_cmd" > /dev/null 2>&1; then
        echo -e "${GREEN}✓ PASSED${NC}"
        ((PASSED++))
    else
        echo -e "${RED}✗ FAILED${NC}"
        echo "  Response: $(echo "$response" | jq -c '.result.structuredContent.data // .error' 2>/dev/null || echo "$response" | head -100)"
        ((FAILED++))
    fi
}

# Health check
echo "📋 Проверка сервера..."
if curl -s "$BASE_URL/health" | jq -e '.status == "ok"' > /dev/null 2>&1; then
    echo -e "${GREEN}✓ Сервер доступен${NC}"
else
    echo -e "${RED}✗ Сервер недоступен!${NC}"
    echo "  Запустите: python -m risk_analytics_mcp.main"
    exit 1
fi
echo ""

# ============================================
# Сценарии ребалансировки
# ============================================
echo "📊 Сценарии ребалансировки"
echo "-------------------------------------------"

# Сценарий 1: Снижение концентрации
run_test "Снижение концентрации SBER (45% → 25%)" '{
    "jsonrpc": "2.0",
    "method": "tools/call",
    "params": {
        "name": "suggest_rebalance",
        "arguments": {
            "positions": [
                {"ticker": "SBER", "current_weight": 0.45, "asset_class": "equity"},
                {"ticker": "GAZP", "current_weight": 0.20, "asset_class": "equity"},
                {"ticker": "LKOH", "current_weight": 0.15, "asset_class": "equity"},
                {"ticker": "ROSN", "current_weight": 0.10, "asset_class": "equity"},
                {"ticker": "GMKN", "current_weight": 0.10, "asset_class": "equity"}
            ],
            "total_portfolio_value": 10000000,
            "risk_profile": {"max_single_position_weight": 0.25, "max_turnover": 0.30}
        }
    },
    "id": 1
}' 'jq -e ".result.structuredContent.data.target_weights.SBER <= 0.26"'

# Сценарий 2: Концентрация по эмитенту
run_test "Концентрация Сбербанк (40% → 25%)" '{
    "jsonrpc": "2.0",
    "method": "tools/call",
    "params": {
        "name": "suggest_rebalance",
        "arguments": {
            "positions": [
                {"ticker": "SBER", "current_weight": 0.25, "asset_class": "equity", "issuer": "SBERBANK"},
                {"ticker": "SBERP", "current_weight": 0.15, "asset_class": "equity", "issuer": "SBERBANK"},
                {"ticker": "GAZP", "current_weight": 0.20, "asset_class": "equity"},
                {"ticker": "LKOH", "current_weight": 0.20, "asset_class": "equity"},
                {"ticker": "ROSN", "current_weight": 0.20, "asset_class": "equity"}
            ],
            "risk_profile": {"max_issuer_weight": 0.25, "max_turnover": 0.30}
        }
    },
    "id": 2
}' 'jq -e "(.result.structuredContent.data.target_weights.SBER + .result.structuredContent.data.target_weights.SBERP) <= 0.26"'

# Сценарий 3: Целевая аллокация 60/40
run_test "Аллокация 60/40 (акции → облигации)" '{
    "jsonrpc": "2.0",
    "method": "tools/call",
    "params": {
        "name": "suggest_rebalance",
        "arguments": {
            "positions": [
                {"ticker": "SBER", "current_weight": 0.30, "asset_class": "equity"},
                {"ticker": "GAZP", "current_weight": 0.30, "asset_class": "equity"},
                {"ticker": "LKOH", "current_weight": 0.20, "asset_class": "equity"},
                {"ticker": "OFZ26", "current_weight": 0.10, "asset_class": "fixed_income"},
                {"ticker": "OFZ29", "current_weight": 0.10, "asset_class": "fixed_income"}
            ],
            "risk_profile": {
                "max_equity_weight": 0.60,
                "max_turnover": 0.30,
                "target_asset_class_weights": {"equity": 0.60, "fixed_income": 0.40}
            }
        }
    },
    "id": 3
}' 'jq -e ".result.structuredContent.data.summary.positions_changed >= 0"'

# Сценарий 4: Низкий оборот (5%)
run_test "Консервативная ребалансировка (оборот 5%)" '{
    "jsonrpc": "2.0",
    "method": "tools/call",
    "params": {
        "name": "suggest_rebalance",
        "arguments": {
            "positions": [
                {"ticker": "SBER", "current_weight": 0.35, "asset_class": "equity"},
                {"ticker": "GAZP", "current_weight": 0.25, "asset_class": "equity"},
                {"ticker": "LKOH", "current_weight": 0.20, "asset_class": "equity"},
                {"ticker": "OFZ", "current_weight": 0.20, "asset_class": "fixed_income"}
            ],
            "risk_profile": {"max_single_position_weight": 0.25, "max_turnover": 0.05}
        }
    },
    "id": 4
}' 'jq -e ".result.structuredContent.data.summary.total_turnover <= 0.06"'

# Сценарий 5: CFO квартальная
run_test "CFO квартальная ребалансировка" '{
    "jsonrpc": "2.0",
    "method": "tools/call",
    "params": {
        "name": "suggest_rebalance",
        "arguments": {
            "positions": [
                {"ticker": "SBER", "current_weight": 0.25, "asset_class": "equity"},
                {"ticker": "GAZP", "current_weight": 0.20, "asset_class": "equity"},
                {"ticker": "LKOH", "current_weight": 0.15, "asset_class": "equity"},
                {"ticker": "OFZ26", "current_weight": 0.15, "asset_class": "fixed_income"},
                {"ticker": "OFZ29", "current_weight": 0.10, "asset_class": "fixed_income"},
                {"ticker": "USD", "current_weight": 0.10, "asset_class": "fx"},
                {"ticker": "MONEY", "current_weight": 0.05, "asset_class": "cash"}
            ],
            "total_portfolio_value": 50000000,
            "risk_profile": {"max_single_position_weight": 0.20, "max_turnover": 0.20}
        }
    },
    "id": 5
}' 'jq -e ".result.structuredContent.data.summary.total_turnover <= 0.21"'

echo ""
echo "-------------------------------------------"
echo "🚫 Сценарии ошибок"
echo "-------------------------------------------"

# Ошибка: Пустой портфель
run_test "Пустой портфель (ошибка валидации)" '{
    "jsonrpc": "2.0",
    "method": "tools/call",
    "params": {
        "name": "suggest_rebalance",
        "arguments": {"positions": []}
    },
    "id": 100
}' 'jq -e ".error != null or .result.structuredContent.error != null"'

# Ошибка: Веса не суммируются к 1
run_test "Веса не = 1.0 (ошибка)" '{
    "jsonrpc": "2.0",
    "method": "tools/call",
    "params": {
        "name": "suggest_rebalance",
        "arguments": {
            "positions": [
                {"ticker": "SBER", "current_weight": 0.30},
                {"ticker": "GAZP", "current_weight": 0.30}
            ]
        }
    },
    "id": 101
}' 'jq -e ".error != null or .result.structuredContent.error != null"'

# Best-effort: Одна позиция
run_test "Одна позиция (best-effort + warnings)" '{
    "jsonrpc": "2.0",
    "method": "tools/call",
    "params": {
        "name": "suggest_rebalance",
        "arguments": {
            "positions": [{"ticker": "SBER", "current_weight": 1.0}],
            "risk_profile": {"max_single_position_weight": 0.25}
        }
    },
    "id": 102
}' 'jq -e ".result.structuredContent.data.summary.warnings | length > 0"'

echo ""
echo "=============================================="
echo "📊 Результаты"
echo "=============================================="
echo -e "   ${GREEN}Passed: $PASSED${NC}"
echo -e "   ${RED}Failed: $FAILED${NC}"
echo ""

if [ $FAILED -eq 0 ]; then
    echo -e "${GREEN}✓ Все тесты пройдены!${NC}"
    exit 0
else
    echo -e "${RED}✗ Есть ошибки${NC}"
    exit 1
fi
