"""Task-aware drift, quality, and retraining checks for customer intelligence."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from src.customer_intelligence_regression import regression_metrics
from src.monitoring import population_stability_index


@dataclass(frozen=True)
class CustomerMonitoringThresholds:
    """Thresholds for multi-task customer-intelligence monitoring."""

    histogram_bins: int
    minimum_current_rows: int
    maximum_feature_psi: float
    maximum_regression_mae_to_baseline_ratio: float
    maximum_cluster_assignment_psi: float
    maximum_cluster_distance_ratio: float


def load_customer_monitoring_config(path: Path) -> CustomerMonitoringThresholds:
    """Load and validate task-aware monitoring thresholds."""
    if not path.exists():
        raise FileNotFoundError(f"Monitoring configuration does not exist: {path}")
    raw = json.loads(path.read_text(encoding="utf-8"))
    try:
        reference = raw["reference"]
        thresholds = raw["thresholds"]
        config = CustomerMonitoringThresholds(
            histogram_bins=int(reference["histogram_bins"]),
            minimum_current_rows=int(reference["minimum_current_rows"]),
            maximum_feature_psi=float(thresholds["maximum_feature_psi"]),
            maximum_regression_mae_to_baseline_ratio=float(
                thresholds["maximum_regression_mae_to_baseline_ratio"]
            ),
            maximum_cluster_assignment_psi=float(
                thresholds["maximum_cluster_assignment_psi"]
            ),
            maximum_cluster_distance_ratio=float(
                thresholds["maximum_cluster_distance_ratio"]
            ),
        )
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError(
            f"Invalid customer monitoring configuration in {path}: {error}"
        ) from error
    if config.histogram_bins < 2:
        raise ValueError("reference.histogram_bins must be at least two")
    if config.minimum_current_rows <= 0:
        raise ValueError("reference.minimum_current_rows must be positive")
    for name, value in {
        "maximum_feature_psi": config.maximum_feature_psi,
        "maximum_regression_mae_to_baseline_ratio": (
            config.maximum_regression_mae_to_baseline_ratio
        ),
        "maximum_cluster_assignment_psi": config.maximum_cluster_assignment_psi,
        "maximum_cluster_distance_ratio": config.maximum_cluster_distance_ratio,
    }.items():
        if value <= 0:
            raise ValueError(f"thresholds.{name} must be positive")
    return config


def _bucket_counts(values: np.ndarray, cut_points: list[float]) -> list[int]:
    """Count finite values in deterministic buckets including outer ranges."""
    bucket_ids = np.digitize(values, np.asarray(cut_points), right=False)
    counts = np.bincount(bucket_ids, minlength=len(cut_points) + 1)
    return [int(value) for value in counts]


def build_numeric_reference(
    data: pd.DataFrame,
    feature_columns: list[str],
    *,
    histogram_bins: int,
) -> dict[str, Any]:
    """Fit reusable quantile bucket boundaries on reference features."""
    if data.empty:
        raise ValueError("Reference data must contain at least one row")
    missing = set(feature_columns).difference(data.columns)
    if missing:
        raise ValueError(
            "Reference data is missing features: " + ", ".join(sorted(missing))
        )
    features: dict[str, Any] = {}
    quantiles = np.linspace(0.0, 1.0, histogram_bins + 1)[1:-1]
    for feature in feature_columns:
        numeric = pd.to_numeric(data[feature], errors="coerce")
        finite = numeric[np.isfinite(numeric)].to_numpy(dtype=float)
        if finite.size == 0:
            raise ValueError(f"Reference feature has no finite values: {feature}")
        quantile_values = np.asarray(
            np.quantile(finite, quantiles),
            dtype=float,
        ).reshape(-1)
        cut_points = sorted(
            {float(value) for value in quantile_values if np.isfinite(value)}
        )
        features[feature] = {
            "cut_points": cut_points,
            "counts": _bucket_counts(finite, cut_points),
            "missing_rows": int(numeric.isna().sum()),
            "reference_rows": int(len(data)),
        }
    return {
        "histogram_bins": histogram_bins,
        "reference_rows": len(data),
        "features": features,
    }


def numeric_drift_report(
    reference: dict[str, Any],
    current: pd.DataFrame,
    *,
    minimum_current_rows: int,
) -> dict[str, Any]:
    """Apply frozen reference buckets and calculate per-feature PSI."""
    if len(current) < minimum_current_rows:
        raise ValueError(
            "Current data has insufficient rows for drift monitoring: "
            f"{len(current)} < {minimum_current_rows}"
        )
    feature_reports: dict[str, Any] = {}
    for feature, profile in reference["features"].items():
        if feature not in current:
            raise ValueError(f"Current data is missing monitored feature: {feature}")
        numeric = pd.to_numeric(current[feature], errors="coerce")
        finite = numeric[np.isfinite(numeric)].to_numpy(dtype=float)
        if finite.size == 0:
            raise ValueError(f"Current feature has no finite values: {feature}")
        current_counts = _bucket_counts(finite, profile["cut_points"])
        psi = population_stability_index(profile["counts"], current_counts)
        feature_reports[feature] = {
            "psi": psi,
            "reference_counts": profile["counts"],
            "current_counts": current_counts,
            "current_missing_rows": int(numeric.isna().sum()),
        }
    return {
        "reference_rows": int(reference["reference_rows"]),
        "current_rows": int(len(current)),
        "features": feature_reports,
        "maximum_psi": max(report["psi"] for report in feature_reports.values()),
    }


def regression_monitoring_report(
    actual: pd.Series | np.ndarray,
    predictions: np.ndarray,
    baseline_predictions: np.ndarray,
) -> dict[str, float]:
    """Compare matured regression quality with its frozen baseline."""
    model_metrics = regression_metrics(actual, predictions)
    baseline_metrics = regression_metrics(actual, baseline_predictions)
    if baseline_metrics["mae"] <= 0:
        raise ValueError("Regression monitoring baseline MAE must be positive")
    return {
        "mae": model_metrics["mae"],
        "rmse": model_metrics["rmse"],
        "baseline_mae": baseline_metrics["mae"],
        "mae_to_baseline_ratio": model_metrics["mae"] / baseline_metrics["mae"],
    }


def clustering_monitoring_report(
    reference_labels: np.ndarray,
    current_labels: np.ndarray,
    reference_distances: np.ndarray,
    current_distances: np.ndarray,
) -> dict[str, float]:
    """Track assignment mix and distance change for one fixed cluster model."""
    if (
        reference_labels.size == 0
        or current_labels.size == 0
        or reference_distances.size != reference_labels.size
        or current_distances.size != current_labels.size
    ):
        raise ValueError("Clustering monitoring arrays must align and be non-empty")
    cluster_count = int(max(reference_labels.max(), current_labels.max())) + 1
    reference_counts = np.bincount(reference_labels, minlength=cluster_count)
    current_counts = np.bincount(current_labels, minlength=cluster_count)
    reference_mean_distance = float(np.mean(reference_distances))
    if reference_mean_distance <= 0:
        raise ValueError("Reference cluster distance must be positive")
    return {
        "assignment_psi": population_stability_index(
            reference_counts.tolist(),
            current_counts.tolist(),
        ),
        "reference_mean_distance": reference_mean_distance,
        "current_mean_distance": float(np.mean(current_distances)),
        "distance_ratio": float(np.mean(current_distances)) / reference_mean_distance,
    }


def customer_retraining_decision(
    *,
    task_type: str,
    drift_report: dict[str, Any],
    quality_report: dict[str, float],
    thresholds: CustomerMonitoringThresholds,
) -> dict[str, Any]:
    """Return explicit reasons while preserving evaluation and release gates."""
    reasons = [
        f"drift:{feature}"
        for feature, report in drift_report["features"].items()
        if report["psi"] > thresholds.maximum_feature_psi
    ]
    if task_type == "regression":
        if (
            quality_report["mae_to_baseline_ratio"]
            > thresholds.maximum_regression_mae_to_baseline_ratio
        ):
            reasons.append("quality:mae_to_baseline")
    elif task_type == "clustering":
        if quality_report["assignment_psi"] > thresholds.maximum_cluster_assignment_psi:
            reasons.append("quality:cluster_assignment_psi")
        if quality_report["distance_ratio"] > thresholds.maximum_cluster_distance_ratio:
            reasons.append("quality:cluster_distance")
    else:
        raise ValueError(f"Unsupported monitoring task: {task_type}")
    return {
        "task_type": task_type,
        "alert": bool(reasons),
        "retraining_required": bool(reasons),
        "reasons": reasons,
        "evaluation_gate_required": True,
        "release_gate_required": True,
    }
