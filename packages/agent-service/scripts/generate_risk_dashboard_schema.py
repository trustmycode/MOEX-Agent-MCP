"""
Генерация JSON Schema для RiskDashboardSpec из Pydantic-модели.

Pydantic — источник правды. Скрипт обновляет:
- docs/schemas/risk-dashboard.schema.json
- apps/web/schemas/risk-dashboard.schema.json
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


def resolve_repo_root() -> Path:
    """Найти корень репозитория (относительно файла скрипта)."""
    # .../packages/agent-service/scripts -> parents[0]=scripts, [1]=agent-service, [2]=packages, [3]=repo root
    return Path(__file__).resolve().parents[3]


def main() -> None:
    root = resolve_repo_root()
    sys.path.insert(0, str(root))
    sys.path.insert(0, str(root / "packages" / "agent-service" / "src"))

    from agent_service.models.dashboard_spec import RiskDashboardSpec  # noqa: WPS433

    schema = RiskDashboardSpec.model_json_schema(ref_template="#/$defs/{model}")

    targets = [
        root / "docs" / "schemas" / "risk-dashboard.schema.json",
        root / "apps" / "web" / "schemas" / "risk-dashboard.schema.json",
    ]

    for path in targets:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as fp:
            json.dump(schema, fp, ensure_ascii=False, indent=2)
            fp.write("\n")
        print(f"Written schema to {path}")


if __name__ == "__main__":
    main()

