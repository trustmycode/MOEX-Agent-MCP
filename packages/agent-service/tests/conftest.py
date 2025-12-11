"""
Pytest configuration for agent-service tests.
"""

import sys
from pathlib import Path

# Добавляем src в sys.path для импортов без установки пакета
ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
