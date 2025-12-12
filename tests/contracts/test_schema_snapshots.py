from __future__ import annotations

import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
DOCS_SCHEMAS_DIR = REPO_ROOT / "docs" / "schemas"
WEB_SCHEMAS_DIR = REPO_ROOT / "apps" / "web" / "schemas"
SNAPSHOT_ROOT = REPO_ROOT / "tests" / "snapshots" / "schemas"
DOCS_SNAPSHOT_DIR = SNAPSHOT_ROOT / "docs"
WEB_SNAPSHOT_DIR = SNAPSHOT_ROOT / "apps_web"


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text())


def _assert_snapshots_match(source_dir: Path, snapshot_dir: Path) -> None:
    source_files = {path.name: path for path in sorted(source_dir.glob("*.json"))}
    snapshot_files = {path.name: path for path in sorted(snapshot_dir.glob("*.json"))}

    missing_snapshots = [name for name in source_files if name not in snapshot_files]
    unexpected_snapshots = [name for name in snapshot_files if name not in source_files]

    assert not missing_snapshots, f"Отсутствуют снапшоты для схем: {missing_snapshots}"
    assert not unexpected_snapshots, f"Снапшоты без исходных схем: {unexpected_snapshots}"

    for name, source_path in source_files.items():
        snapshot_path = snapshot_files[name]
        actual = _load_json(source_path)
        expected = _load_json(snapshot_path)
        assert actual == expected, f"Схема {name} изменилась. Обновите снапшот {snapshot_path} осознанно."


def test_docs_schema_snapshots_are_current() -> None:
    assert DOCS_SCHEMAS_DIR.exists(), "Каталог docs/schemas не найден"
    assert DOCS_SNAPSHOT_DIR.exists(), "Каталог снапшотов docs отсутствует"
    _assert_snapshots_match(DOCS_SCHEMAS_DIR, DOCS_SNAPSHOT_DIR)


def test_apps_web_schema_snapshots_are_current() -> None:
    if not WEB_SCHEMAS_DIR.exists():
        pytest.skip("apps/web/schemas отсутствует")
    assert WEB_SNAPSHOT_DIR.exists(), "Каталог снапшотов apps_web отсутствует"
    _assert_snapshots_match(WEB_SCHEMAS_DIR, WEB_SNAPSHOT_DIR)

