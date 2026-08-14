"""Regressão para ciclos de importação no ponto de entrada."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def test_run_module_imports_in_clean_python_process() -> None:
    project_root = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        [sys.executable, "-c", "import run; print('entrypoint-import-ok')"],
        cwd=project_root,
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "entrypoint-import-ok" in result.stdout
