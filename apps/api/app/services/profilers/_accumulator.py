"""M20 — Streaming column accumulator with bounded top-K."""
from __future__ import annotations

from collections import Counter

from app.core.config import get_settings
from app.domain.data_intelligence import (
    ColumnType,
    aggregate_column_type,
    infer_scalar_type,
)
from app.services.profilers import ColumnStats

# Top-K pruning: when the counter grows past ``limit * _PRUNE_FACTOR``,
# keep only the top ``limit * _PRUNE_KEEP``. Bounds memory to O(limit).
_PRUNE_FACTOR = 4
_PRUNE_KEEP = 2


class ColumnAccumulator:
    def __init__(
        self,
        *,
        name: str,
        ordinal: int,
        distinct_cap: int,
        top_values_limit: int,
        numeric_sample_cap: int = 5000,
    ) -> None:
        self.name = name
        self.ordinal = ordinal
        self._distinct_cap = distinct_cap
        self._top_values_limit = top_values_limit
        self._numeric_sample_cap = numeric_sample_cap
        self._prune_trigger = top_values_limit * _PRUNE_FACTOR
        self._prune_keep = top_values_limit * _PRUNE_KEEP

        self.total = 0
        self.null_count = 0
        self._type_counts: Counter[str] = Counter()
        self._distinct: set[str] = set()
        self._distinct_overflow = False
        self._top_counter: dict[str, int] = {}
        self._numeric_sample: list[float] = []
        self._min: float | None = None
        self._max: float | None = None
        self._welford_n = 0
        self._welford_mean = 0.0
        self._welford_m2 = 0.0
        self._has_numeric = False

    def _bump_top(self, key: str) -> None:
        c = self._top_counter
        c[key] = c.get(key, 0) + 1
        if len(c) > self._prune_trigger:
            top = sorted(
                c.items(), key=lambda kv: -kv[1]
            )[: self._prune_keep]
            self._top_counter = dict(top)

    def add(self, raw: object) -> None:
        self.total += 1
        t = infer_scalar_type(raw)
        if t is ColumnType.NULL:
            self.null_count += 1
            return
        self._type_counts[t.value] += 1
        key = str(raw)
        if not self._distinct_overflow:
            self._distinct.add(key)
            if len(self._distinct) > self._distinct_cap:
                self._distinct_overflow = True
                self._distinct.clear()
        self._bump_top(key)

        if t in (ColumnType.INTEGER, ColumnType.FLOAT):
            try:
                v = float(raw)  # type: ignore[arg-type]
            except (TypeError, ValueError):
                return
            if v != v or v in (float("inf"), float("-inf")):
                return
            self._has_numeric = True
            self._welford_n += 1
            delta = v - self._welford_mean
            self._welford_mean += delta / self._welford_n
            self._welford_m2 += delta * (v - self._welford_mean)
            if self._min is None or v < self._min:
                self._min = v
            if self._max is None or v > self._max:
                self._max = v
            if len(self._numeric_sample) < self._numeric_sample_cap:
                self._numeric_sample.append(v)

    def finalize(self) -> ColumnStats:
        settings = get_settings()
        inferred = aggregate_column_type(dict(self._type_counts))

        distinct_count: int | None
        unique_ratio: float | None
        if self._distinct_overflow:
            distinct_count = None
            unique_ratio = None
        else:
            distinct_count = len(self._distinct)
            unique_ratio = (
                distinct_count / self.total if self.total else 0.0
            )

        if (
            inferred is ColumnType.STRING
            and distinct_count is not None
            and distinct_count >= 2
            and distinct_count <= settings.data_category_max_distinct
            and (unique_ratio is not None and unique_ratio <= 0.5)
        ):
            inferred = ColumnType.CATEGORY

        non_null = self.total - self.null_count
        null_ratio = self.null_count / self.total if self.total else 0.0

        top_values = [
            {"value": k, "count": v}
            for k, v in sorted(
                self._top_counter.items(), key=lambda kv: -kv[1]
            )[: self._top_values_limit]
        ]

        mean: float | None = None
        stddev: float | None = None
        median: float | None = None
        min_value: str | None = None
        max_value: str | None = None

        median_is_approximate = False
        if self._has_numeric and self._welford_n > 0:
            mean = self._welford_mean
            if self._welford_n > 1:
                var = self._welford_m2 / (self._welford_n - 1)
                stddev = var ** 0.5 if var >= 0 else None
            if self._min is not None:
                min_value = str(self._min)
            if self._max is not None:
                max_value = str(self._max)
            if self._numeric_sample:
                s = sorted(self._numeric_sample)
                median = s[len(s) // 2] if s else None
                median_is_approximate = (
                    len(self._numeric_sample) >= self._numeric_sample_cap
                )
        else:
            if top_values:
                keys_sorted = sorted(
                    str(t["value"]) for t in top_values
                )
                min_value = keys_sorted[0][:200]
                max_value = keys_sorted[-1][:200]
        return ColumnStats(
            name=self.name,
            ordinal=self.ordinal,
            inferred_type=inferred.value,
            nullable=self.null_count > 0,
            null_count=self.null_count,
            total_count=self.total,
            distinct_count=distinct_count,
            unique_ratio=unique_ratio,
            min_value=min_value,
            max_value=max_value,
            mean=mean,
            median=median,
            stddev=stddev,
            top_values=top_values,
            meta={
                "non_null_count": non_null,
                "null_ratio": round(null_ratio, 6),
                "distinct_capped": self._distinct_overflow,
                "top_values_approximate": True,
                "median_approximate": median_is_approximate,
            },
        )
