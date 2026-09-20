"""
Reusable deterministic analysis primitives.

Pure calculation helpers for analytical modules. These own
period change, shares, concentration, distributions, outliers,
trends, segment comparisons, and correlation — never narrative
or dashboard packaging.
"""

from .change import (
    overall_change,
    percent_change,
    period_over_period,
    safe_ratio,
)
from .compare import (
    group_delta,
    segment_vs_rest,
    vs_benchmark,
)
from .distribution import (
    numeric_summary,
    percentile_table,
)
from .outliers import (
    flag_iqr,
    flag_threshold,
    flag_zscore,
    outlier_summary,
)
from .relationship import (
    corr_matrix,
    pearson_corr,
)
from .share import (
    add_share,
    concentration_summary,
    top_1_share,
    top_n_share,
)
from .trends import (
    add_rolling_baseline,
    classify_trend_direction,
    relative_deviation,
    window_mean_change,
)

__all__ = [
    "safe_ratio",
    "percent_change",
    "period_over_period",
    "overall_change",
    "add_share",
    "top_n_share",
    "top_1_share",
    "concentration_summary",
    "group_delta",
    "vs_benchmark",
    "segment_vs_rest",
    "numeric_summary",
    "percentile_table",
    "flag_threshold",
    "flag_iqr",
    "flag_zscore",
    "outlier_summary",
    "add_rolling_baseline",
    "relative_deviation",
    "classify_trend_direction",
    "window_mean_change",
    "pearson_corr",
    "corr_matrix",
]
