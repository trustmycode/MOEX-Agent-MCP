from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

REPO_ROOT = Path(__file__).resolve().parents[2]
LINT_IMPORTS_BIN = Path(sys.executable).with_name("lint-imports")
if sys.platform.startswith("win") and LINT_IMPORTS_BIN.suffix == "":
    LINT_IMPORTS_BIN = LINT_IMPORTS_BIN.with_suffix(".exe")

SDK_CONFIG = """
[importlinter]
root_package = moex_iss_sdk
include_external_packages = True

[contract:sdk_no_mcp]
name = moex_iss_sdk must not import moex_iss_mcp
type = forbidden
source_modules =
    moex_iss_sdk
forbidden_modules =
    moex_iss_mcp
"""

CALCULATIONS_CONFIG = """
[importlinter]
root_package = risk_analytics_mcp
include_external_packages = True

[contract:calc_no_http_clients]
name = risk_analytics_mcp.calculations must not depend on HTTP clients
type = forbidden
source_modules =
    risk_analytics_mcp.calculations
forbidden_modules =
    httpx
    requests
    urllib
    urllib.request
    urllib.error
    urllib.parse
    urllib3
"""


def _run_importlinter(config_body: str) -> None:
    if not LINT_IMPORTS_BIN.exists():
        raise RuntimeError(f"lint-imports entrypoint not found at {LINT_IMPORTS_BIN}")

    env = os.environ.copy()
    env["PYTHONPATH"] = f"{REPO_ROOT}{os.pathsep}{env.get('PYTHONPATH', '')}"

    with TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir) / ".importlinter"
        config_path.write_text(config_body)

        result = subprocess.run(
            [str(LINT_IMPORTS_BIN), "--config", str(config_path)],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            env=env,
        )

    assert result.returncode == 0, (
        "Import-linter rule violation:\n"
        f"stdout:\n{result.stdout}\n"
        f"stderr:\n{result.stderr}"
    )


def test_moex_sdk_is_isolated_from_mcp() -> None:
    _run_importlinter(SDK_CONFIG)


def test_calculations_are_pure_python() -> None:
    _run_importlinter(CALCULATIONS_CONFIG)


