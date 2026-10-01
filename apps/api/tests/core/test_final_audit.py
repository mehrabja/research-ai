"""F19 final repository audit regression coverage."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
SCRIPT = ROOT / "scripts" / "final_audit.py"

spec = importlib.util.spec_from_file_location("final_audit", SCRIPT)
assert spec is not None and spec.loader is not None
final_audit = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = final_audit
spec.loader.exec_module(final_audit)


def test_required_release_artifacts_exist() -> None:
    assert final_audit.check_required() == []


def test_tracked_forbidden_environment_files_are_absent() -> None:
    assert final_audit.tracked_forbidden_files() == []


def test_repository_secret_scan_is_clean() -> None:
    assert final_audit.secret_findings() == []
