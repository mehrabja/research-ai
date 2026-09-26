"""M29 — artifact role classification tests."""
from __future__ import annotations

from types import SimpleNamespace

from app.services.technical_intelligence.artifact_role import (
    ROLE_CONFIGURATION,
    ROLE_DATASET,
    ROLE_EXPERIMENT_RESULT,
    ROLE_SOURCE_CODE,
    detect_artifact_role,
)


def _pf(name, ext, kind=None):
    return SimpleNamespace(
        extension=ext,
        original_filename=name,
        normalized_filename=name,
        file_kind=kind,
        file_meta=None,
    )


def test_py_is_source_code() -> None:
    assert detect_artifact_role(
        _pf("a.py", ".py")
    ).role == ROLE_SOURCE_CODE


def test_metrics_csv_is_result() -> None:
    # structured_data + result hint → experiment_result
    assert detect_artifact_role(
        _pf("metrics_run1.csv", ".csv", kind="structured_data")
    ).role == ROLE_EXPERIMENT_RESULT


def test_plain_csv_is_dataset() -> None:
    # No file_kind → extension fallback
    assert detect_artifact_role(
        _pf("data.csv", ".csv")
    ).role == ROLE_DATASET


def test_yaml_is_config() -> None:
    assert detect_artifact_role(
        _pf("settings.yaml", ".yaml")
    ).role == ROLE_CONFIGURATION


def test_file_kind_structured_data_no_hint_is_dataset() -> None:
    # structured_data + no result hint → dataset
    assert detect_artifact_role(
        _pf("random_data.csv", ".csv", kind="structured_data")
    ).role == ROLE_DATASET


def test_file_kind_structured_data_with_result_hint() -> None:
    assert detect_artifact_role(
        _pf("metrics_run1.csv", ".csv", kind="structured_data")
    ).role == ROLE_EXPERIMENT_RESULT


def test_unknown_extension() -> None:
    assert detect_artifact_role(
        _pf("a.xyz", ".xyz")
    ).role == "unknown"
