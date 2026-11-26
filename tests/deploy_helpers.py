"""Load scripts/deploy_lambda.py by file path so tests can import it."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "deploy_lambda.py"


def load_deploy_module() -> ModuleType:
    """Import the deploy script as a module. It does not import boto3."""
    spec = importlib.util.spec_from_file_location("deploy_lambda_under_test", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
