"""Deterministic model-quality and drift checks for retraining decisions."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np


@dataclass(frozen=True)
class MonitoringThresholds:
    """Thresholds that control alerts and governed retraining."""

    maximum_psi: float
    minimum_roc_auc: float
    minimum_recall: float


def population_stability_index(
    reference_counts: list[int],
    current_counts: list[int],
) -> float:
    """Calculate PSI for aligned histogram buckets."""
    if len(reference_counts) != len(current_counts) or not reference_counts:
        raise ValueError("Reference and current histograms must align and be non-empty")
    if any(value < 0 for value in reference_counts + current_counts):
        raise ValueError("Histogram counts must not be negative")
    if sum(reference_counts) == 0 or sum(current_counts) == 0:
        raise ValueError("Each histogram must contain at least one observation")

    epsilon = 1e-6
    reference = np.array(reference_counts, dtype=float) / sum(reference_counts)
    current = np.array(current_counts, dtype=float) / sum(current_counts)
    reference = np.clip(reference, epsilon, None)
    current = np.clip(current, epsilon, None)
    return float(np.sum((current - reference) * np.log(current / reference)))


def retraining_decision(
    *,
    drift_scores: dict[str, float],
    quality_metrics: dict[str, float] | None,
    thresholds: MonitoringThresholds,
) -> dict[str, Any]:
    """Return explicit alert reasons without bypassing release governance."""
    drifted = sorted(
        feature
        for feature, score in drift_scores.items()
        if score > thresholds.maximum_psi
    )
    quality_failures: list[str] = []
    if quality_metrics is not None:
        for metric, minimum in {
            "roc_auc": thresholds.minimum_roc_auc,
            "recall": thresholds.minimum_recall,
        }.items():
            if metric not in quality_metrics:
                raise ValueError(f"Missing quality metric: {metric}")
            if quality_metrics[metric] < minimum:
                quality_failures.append(metric)
    reasons = [
        *[f"drift:{feature}" for feature in drifted],
        *[f"quality:{metric}" for metric in quality_failures],
    ]
    return {
        "alert": bool(reasons),
        "retraining_required": bool(reasons),
        "reasons": reasons,
        "release_gate_required": True,
    }


def load_monitoring_config(path: Path) -> MonitoringThresholds:
    """Load checked monitoring thresholds."""
    raw = json.loads(path.read_text(encoding="utf-8"))
    try:
        thresholds = raw["thresholds"]
        result = MonitoringThresholds(
            maximum_psi=float(thresholds["maximum_psi"]),
            minimum_roc_auc=float(thresholds["minimum_roc_auc"]),
            minimum_recall=float(thresholds["minimum_recall"]),
        )
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError(
            f"Invalid monitoring configuration in {path}: {error}"
        ) from error
    if result.maximum_psi <= 0:
        raise ValueError("thresholds.maximum_psi must be greater than zero")
    if not 0 <= result.minimum_roc_auc <= 1:
        raise ValueError("thresholds.minimum_roc_auc must be between 0 and 1")
    if not 0 <= result.minimum_recall <= 1:
        raise ValueError("thresholds.minimum_recall must be between 0 and 1")
    return result
