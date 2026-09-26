"""M29 — Code/Experiment Intelligence domain primitives (pure)."""
from __future__ import annotations

import re
from enum import StrEnum

M29_VERSION = "m29.1"
TECHNICAL_EXTRACTION_VERSION = "m29-extract-v1"
RESULT_PARSER_VERSION = "m29-parser-v1"
EXPERIMENT_KEY_MATCH_VERSION = "m29-key-v1"

# --- Confidence policy (documented; enforced in tests) --------------------
CONF_EXACT = 1.0               # parser-provided ground truth
CONF_PARSER_DERIVED = 1.0      # deterministic structural derivation
CONF_DEPENDENCY = 1.0          # import/include line
CONF_KEYWORD_HEURISTIC = 0.7   # algorithm / pipeline name keyword match
CONF_NAME_PATTERN_HEURISTIC = 0.7  # signature param naming
CONF_AMBIGUOUS = 0.5           # anything requiring interpretation


class TechnicalFactType(StrEnum):
    ALGORITHM = "algorithm"
    LIBRARY = "library"
    IMPORT = "import"
    FUNCTION = "function"
    CLASS = "class"
    PIPELINE_STEP = "pipeline_step"
    HYPERPARAMETER = "hyperparameter"
    CONFIGURATION = "configuration"
    DATASET_COLUMN = "dataset_column"
    DATASET_CHARACTERISTIC = "dataset_characteristic"
    INPUT_REFERENCE = "input_reference"
    OUTPUT_REFERENCE = "output_reference"
    EXPERIMENT_IDENTIFIER = "experiment_identifier"


class ExperimentResultType(StrEnum):
    METRIC_OBSERVATION = "metric_observation"
    COMPARISON = "comparison"
    DERIVED_RESULT = "derived_result"
    SUMMARY = "summary"


class MetricType(StrEnum):
    ACCURACY = "accuracy"
    PRECISION = "precision"
    RECALL = "recall"
    F1 = "f1"
    AUC = "auc"
    RMSE = "rmse"
    MAE = "mae"
    RUNTIME = "runtime"
    MEMORY = "memory"
    CUSTOM = "custom"


class FactStatus(StrEnum):
    EXTRACTED = "extracted"
    VALIDATED = "validated"
    REJECTED = "rejected"


class ResultStatus(StrEnum):
    PARSED = "parsed"
    VALIDATED = "validated"
    REJECTED = "rejected"


class MetricStatus(StrEnum):
    PARSED = "parsed"
    VALIDATED = "validated"
    REJECTED = "rejected"


class TechnicalIntelligenceRunStatus(StrEnum):
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


TECHNICAL_FACT_TYPES = tuple(t.value for t in TechnicalFactType)
EXPERIMENT_RESULT_TYPES = tuple(t.value for t in ExperimentResultType)
METRIC_TYPES = tuple(t.value for t in MetricType)
FACT_STATUSES = tuple(s.value for s in FactStatus)
RESULT_STATUSES = tuple(s.value for s in ResultStatus)
METRIC_STATUSES = tuple(s.value for s in MetricStatus)
TECHNICAL_INTELLIGENCE_RUN_STATUSES = tuple(
    s.value for s in TechnicalIntelligenceRunStatus
)

# --- Deterministic keyword tables (versioned with M29_VERSION) ------------

_ALGORITHM_KEYWORDS: tuple[str, ...] = (
    "random_forest", "randomforest", "gradient_boosting",
    "gradientboosting", "xgboost", "lightgbm", "catboost",
    "svm", "svc", "svr", "logistic_regression", "linear_regression",
    "ridge", "lasso", "kmeans", "k_means", "dbscan",
    "hierarchical_clustering", "pca", "umap", "tsne", "lda",
    "transformer", "bert", "roberta", "gpt", "llama", "t5",
    "resnet", "vgg", "efficientnet", "unet", "vit",
    "lstm", "gru", "rnn", "cnn", "mlp", "attention",
    "self_attention", "isolation_forest", "autoencoder", "vae",
    "gan", "naive_bayes", "decision_tree", "adaboost", "bagging",
)

_HYPERPARAMETER_KEYWORDS: frozenset[str] = frozenset({
    "learning_rate", "lr", "batch_size", "epochs", "num_epochs",
    "max_depth", "n_estimators", "num_estimators", "min_samples_split",
    "min_samples_leaf", "dropout", "weight_decay", "momentum",
    "temperature", "top_p", "top_k", "max_tokens", "seed",
    "hidden_size", "embedding_dim", "num_layers", "n_layers",
    "num_heads", "n_heads", "warmup_steps", "patience",
    "reg_lambda", "reg_alpha",
})

_METRIC_NAME_MAP: dict[str, str] = {
    "accuracy": "accuracy", "acc": "accuracy",
    "top1_accuracy": "accuracy", "top_1_accuracy": "accuracy",
    "precision": "precision", "prec": "precision",
    "macro_precision": "precision", "micro_precision": "precision",
    "recall": "recall", "sensitivity": "recall", "tpr": "recall",
    "macro_recall": "recall", "micro_recall": "recall",
    "f1": "f1", "f1_score": "f1", "f1score": "f1",
    "macro_f1": "f1", "micro_f1": "f1", "weighted_f1": "f1",
    "auc": "auc", "auroc": "auc", "roc_auc": "auc", "auc_roc": "auc",
    "rmse": "rmse", "root_mean_squared_error": "rmse",
    "mae": "mae", "mean_absolute_error": "mae",
    "runtime": "runtime", "time": "runtime", "elapsed": "runtime",
    "elapsed_time": "runtime", "duration": "runtime",
    "memory": "memory", "peak_memory": "memory",
    "memory_usage": "memory",
}

_NUMERIC_DIRECTION_MAP: dict[str, str] = {
    "accuracy": "higher", "precision": "higher", "recall": "higher",
    "f1": "higher", "auc": "higher",
    "rmse": "lower", "mae": "lower",
    "runtime": "lower", "memory": "lower",
}

_SPLIT_ALIASES: frozenset[str] = frozenset({
    "split", "set", "partition", "fold", "phase", "subset",
})

_NORM_RE = re.compile(r"[^0-9a-z_]+")


def _canonical_key(raw: str) -> str:
    return _NORM_RE.sub("_", raw.strip().lower()).strip("_")


def normalize_metric_name(raw: str | None) -> str:
    if not raw:
        return MetricType.CUSTOM.value
    return _METRIC_NAME_MAP.get(_canonical_key(raw),
                                MetricType.CUSTOM.value)


def is_known_metric_name(raw: str) -> bool:
    return normalize_metric_name(raw) != MetricType.CUSTOM.value


def metric_direction(normalized_name: str) -> str | None:
    return _NUMERIC_DIRECTION_MAP.get(normalized_name)


def is_split_column(name: str) -> bool:
    return _canonical_key(name) in _SPLIT_ALIASES


def is_algorithm_name(name: str | None) -> bool:
    if not name:
        return False
    low = name.lower()
    return any(k in low for k in _ALGORITHM_KEYWORDS)


def is_hyperparameter_name(name: str | None) -> bool:
    if not name:
        return False
    return _canonical_key(name) in _HYPERPARAMETER_KEYWORDS


def scan_hyperparameters_from_signature(
    signature: str | None,
) -> tuple[str, ...]:
    """Return sorted hyperparameter names found in a function signature
    like ``f(a, lr=0.1, batch_size=32)``."""
    if not signature:
        return ()
    a = signature.find("(")
    b = signature.rfind(")")
    if a < 0 or b <= a:
        return ()
    inner = signature[a + 1:b]
    found: set[str] = set()
    for token in inner.split(","):
        if "=" not in token:
            continue
        name = token.split("=", 1)[0].strip().lstrip("*").strip()
        if is_hyperparameter_name(name):
            found.add(_canonical_key(name))
    return tuple(sorted(found))


def normalize_fact_value(value: object) -> str | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return repr(value)
    if isinstance(value, str):
        return value.strip()[:2000]
    return str(value)[:2000]


__all__ = [
    "M29_VERSION",
    "TECHNICAL_EXTRACTION_VERSION",
    "RESULT_PARSER_VERSION",
    "EXPERIMENT_KEY_MATCH_VERSION",
    "CONF_EXACT",
    "CONF_PARSER_DERIVED",
    "CONF_DEPENDENCY",
    "CONF_KEYWORD_HEURISTIC",
    "CONF_NAME_PATTERN_HEURISTIC",
    "CONF_AMBIGUOUS",
    "TechnicalFactType",
    "ExperimentResultType",
    "MetricType",
    "FactStatus",
    "ResultStatus",
    "MetricStatus",
    "TechnicalIntelligenceRunStatus",
    "TECHNICAL_FACT_TYPES",
    "EXPERIMENT_RESULT_TYPES",
    "METRIC_TYPES",
    "FACT_STATUSES",
    "RESULT_STATUSES",
    "METRIC_STATUSES",
    "TECHNICAL_INTELLIGENCE_RUN_STATUSES",
    "normalize_metric_name",
    "is_known_metric_name",
    "metric_direction",
    "is_split_column",
    "is_algorithm_name",
    "is_hyperparameter_name",
    "scan_hyperparameters_from_signature",
    "normalize_fact_value",
]
