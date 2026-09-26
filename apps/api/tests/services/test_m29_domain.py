"""M29 — domain primitive tests."""
from __future__ import annotations

from app.domain.technical_intelligence import (
    CONF_EXACT,
    CONF_KEYWORD_HEURISTIC,
    M29_VERSION,
    is_algorithm_name,
    is_hyperparameter_name,
    metric_direction,
    normalize_metric_name,
    scan_hyperparameters_from_signature,
)


def test_version_pinned() -> None:
    assert M29_VERSION == "m29.1"


def test_confidence_constants() -> None:
    assert CONF_EXACT == 1.0
    assert CONF_KEYWORD_HEURISTIC < 1.0


def test_metric_normalization() -> None:
    assert normalize_metric_name("Accuracy") == "accuracy"
    assert normalize_metric_name("roc_auc") == "auc"
    assert normalize_metric_name("F1-Score") == "f1"
    assert normalize_metric_name("nonsense") == "custom"


def test_metric_direction() -> None:
    assert metric_direction("rmse") == "lower"
    assert metric_direction("f1") == "higher"
    assert metric_direction("custom") is None


def test_algorithm_detection() -> None:
    assert is_algorithm_name("RandomForest")
    assert is_algorithm_name("build_transformer_model")
    assert not is_algorithm_name("foo_bar")


def test_hyperparameter_detection() -> None:
    assert is_hyperparameter_name("learning_rate")
    assert is_hyperparameter_name("BATCH_SIZE")
    assert not is_hyperparameter_name("foo")


def test_scan_hyperparameters() -> None:
    got = scan_hyperparameters_from_signature(
        "train(x, y, lr=0.1, batch_size=32, foo=1)"
    )
    assert "lr" in got
    assert "batch_size" in got
    assert "foo" not in got
